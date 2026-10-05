# -*- coding: UTF-8 -*-
"""Local HTTP server that imitates the OpenAI, Gemini and Anthropic APIs.

It checks the authentication headers and the shape of each request body the
same way the real services do, and records every request for assertions.
"""

import base64
import hashlib
import json
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import _testkey

VALID = {"openai": "sk-test-openai-123456", "gemini": "AIza-test-gemini-123456", "anthropic": "sk-ant-test-123456"}
REQUESTS = []
#: Optional overrides: {"openai": (status, body)} to force an answer.
FORCE = {}
DELAY = {"seconds": 0}
LAST_ATTACHMENTS = {}

#: State of the fake "Sign in with ChatGPT" (auth.openai.com + plan usage).
CHATGPT = {}
ISSUED_CLIENT = "oaiapp_test_nvdaias"
PLAN_SCOPES = "openid profile email offline_access resource.invoke chatgpt.tokens.use.direct"


def resetChatGPT():
	CHATGPT.clear()
	CHATGPT.update({
		"codes": {},  # code -> data of the authorization request
		"access": set(),  # valid access tokens
		"refresh": set(),  # valid refresh tokens
		"used_refresh": set(),
		"revoked": [],
		"authorize": [],  # parameters of every authorization request
		"counter": 0,
		"email": "pessoa@example.com",
		"scope": PLAN_SCOPES,
		"deny": False,  # answer error=access_denied
		"bad_nonce": False,
		"bad_signature": False,
		"wrong_state": False,
		"expires_in": 3600,
		"responses": [],  # bodies received by /responses
		"stream": None,  # forced SSE text
	})


resetChatGPT()


def _b64url(data):
	return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def signJwt(claims, kid=_testkey.KID, alg="RS256", corrupt=False):
	header = {"alg": alg, "typ": "JWT", "kid": kid}
	signingInput = (_b64url(json.dumps(header).encode()) + "." + _b64url(json.dumps(claims).encode())).encode("ascii")
	k = (_testkey.N.bit_length() + 7) // 8
	digestInfo = bytes.fromhex("3031300d060960864801650304020105000420") + hashlib.sha256(signingInput).digest()
	em = b"\x00\x01" + b"\xff" * (k - 3 - len(digestInfo)) + b"\x00" + digestInfo
	sig = pow(int.from_bytes(em, "big"), _testkey.D, _testkey.N).to_bytes(k, "big")
	if corrupt:
		sig = sig[:-1] + bytes([sig[-1] ^ 1])
	return signingInput.decode("ascii") + "." + _b64url(sig)


def fakeBrowser(url, delay=0.05):
	"""Plays the user in the browser: opens the authorization page of the fake
	server and follows it back to NVDAIAs (http://127.0.0.1:PORT/callback)."""
	import urllib.request

	def run():
		time.sleep(delay)
		with urllib.request.urlopen(url, timeout=10) as r:  # the fake authorization page
			location = json.loads(r.read().decode())["location"]
		try:
			with urllib.request.urlopen(location, timeout=10) as r:
				r.read()
		except Exception:
			pass

	threading.Thread(target=run, daemon=True).start()
	return True


class Handler(BaseHTTPRequestHandler):
	def log_message(self, *a):
		pass

	def _redirect(self, url):
		self.send_response(307)
		self.send_header("Location", url)
		self.send_header("Content-Length", "0")
		self.end_headers()

	def _send(self, status, body):
		if status == "redirect":
			return self._redirect(body)
		if status == "raw":
			data = body if isinstance(body, bytes) else body.encode("utf-8")
			self.send_response(200)
			self.send_header("Content-Type", "application/json")
			self.send_header("Content-Length", str(len(data)))
			self.end_headers()
			self.wfile.write(data)
			return
		data = json.dumps(body).encode("utf-8")
		self.send_response(status)
		self.send_header("Content-Type", "application/json")
		self.send_header("Content-Length", str(len(data)))
		self.end_headers()
		self.wfile.write(data)

	def _body(self):
		length = int(self.headers.get("Content-Length") or 0)
		if not length:
			return None
		raw = self.rfile.read(length).decode("utf-8")
		if (self.headers.get("Content-Type") or "").startswith("application/x-www-form-urlencoded"):
			return dict(urllib.parse.parse_qsl(raw, keep_blank_values=True))
		return json.loads(raw)

	def _route(self, method):
		import time
		if DELAY["seconds"]:
			time.sleep(DELAY["seconds"])
		body = self._body() if method == "POST" else None
		path = self.path
		REQUESTS.append({"method": method, "path": path, "headers": dict(self.headers), "body": body})
		if path.startswith("/openai/"):
			return self._openai(method, path[len("/openai"):], body)
		if path.startswith("/gemini/"):
			return self._gemini(method, path[len("/gemini"):], body)
		if path.startswith("/anthropic/"):
			return self._anthropic(method, path[len("/anthropic"):], body)
		if path.startswith("/chatgpt/auth/"):
			return self._chatgptAuth(method, path[len("/chatgpt/auth"):], body)
		if path.startswith("/chatgpt/v1/"):
			return self._chatgptApi(method, path[len("/chatgpt/v1"):], body)
		self._send(404, {"error": "unknown"})

	def do_GET(self):
		self._route("GET")

	def do_POST(self):
		self._route("POST")

	# OpenAI ------------------------------------------------------------------
	def _openai(self, method, path, body):
		if FORCE.get("openai"):
			return self._send(*FORCE["openai"])
		if self.headers.get("Authorization") != "Bearer " + VALID["openai"]:
			return self._send(401, {"error": {"message": "Incorrect API key provided: sk-***.", "type": "invalid_request_error", "code": "invalid_api_key"}})
		if method == "GET" and path == "/v1/models":
			return self._send(200, {"object": "list", "data": [{"id": i} for i in ("gpt-5-mini", "gpt-5", "whisper-1", "text-embedding-3-small", "gpt-4o-realtime-preview")]})
		if method == "POST" and path == "/v1/chat/completions":
			assert body["model"], "model missing"
			msgs = body["messages"]
			assert "temperature" not in body and "max_tokens" not in body
			if msgs[0]["role"] == "system":
				msgs = msgs[1:]
			assert msgs[-1]["role"] == "user"
			last = msgs[-1]["content"]
			if isinstance(last, list):
				kinds = []
				for part in last[:-1]:
					if part["type"] == "image_url":
						assert part["image_url"]["url"].startswith("data:image/")
						kinds.append("imagem")
					elif part["type"] == "file":
						assert part["file"]["file_data"].startswith("data:application/pdf;base64,") and part["file"]["filename"]
						kinds.append("pdf")
					else:
						assert part["type"] == "text" and part["text"].startswith("<file name=")
						kinds.append("texto")
				assert last[-1]["type"] == "text"
				LAST_ATTACHMENTS["openai"] = kinds
				text = "**Imagem**: um botão azul. Anexos: %s. (%d mensagens)" % (",".join(kinds), len(msgs))
			else:
				text = "# Resposta\n\nOlá! Você perguntou: *%s*. (%d mensagens)" % (last, len(msgs))
			return self._send(200, {"choices": [{"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": "stop"}]})
		self._send(404, {"error": {"message": "not found"}})

	# Gemini ------------------------------------------------------------------
	def _gemini(self, method, path, body):
		if FORCE.get("gemini"):
			return self._send(*FORCE["gemini"])
		if self.headers.get("x-goog-api-key") != VALID["gemini"]:
			return self._send(400, {"error": {"code": 400, "message": "API key not valid. Please pass a valid API key.", "status": "INVALID_ARGUMENT", "details": [{"reason": "API_KEY_INVALID"}]}})
		if method == "GET" and path.startswith("/v1beta/models"):
			return self._send(200, {"models": [
				{"name": "models/gemini-2.5-flash", "supportedGenerationMethods": ["generateContent", "countTokens"]},
				{"name": "models/gemini-2.5-pro", "supportedGenerationMethods": ["generateContent"]},
				{"name": "models/text-embedding-004", "supportedGenerationMethods": ["embedContent"]},
			]})
		if method == "POST" and path.endswith(":generateContent"):
			model = path.split("/models/")[1].split(":")[0]
			if model not in ("gemini-2.5-flash", "gemini-2.5-pro"):
				return self._send(404, {"error": {"code": 404, "message": "models/%s is not found for API version v1beta" % model, "status": "NOT_FOUND"}})
			contents = body["contents"]
			assert contents[-1]["role"] == "user"
			for c in contents:
				assert c["role"] in ("user", "model")
			assert body["systemInstruction"]["parts"][0]["text"]
			parts = contents[-1]["parts"]
			kinds = []
			for part in parts[:-1]:
				if "inline_data" in part:
					assert part["inline_data"]["data"]
					kinds.append(part["inline_data"]["mime_type"])
				else:
					assert part["text"].startswith("<file name=")
					kinds.append("texto")
			LAST_ATTACHMENTS["gemini"] = kinds
			text = "Resposta do Gemini para: %s (%d mensagens)" % (parts[-1]["text"], len(contents))
			return self._send(200, {"candidates": [{"content": {"role": "model", "parts": [{"text": "pensando...", "thought": True}, {"text": text}]}, "finishReason": "STOP"}]})
		self._send(404, {"error": {"message": "not found"}})

	# Anthropic ---------------------------------------------------------------
	def _anthropic(self, method, path, body):
		if FORCE.get("anthropic"):
			return self._send(*FORCE["anthropic"])
		if self.headers.get("x-api-key") != VALID["anthropic"]:
			return self._send(401, {"type": "error", "error": {"type": "authentication_error", "message": "invalid x-api-key"}})
		if self.headers.get("anthropic-version") != "2023-06-01":
			return self._send(400, {"type": "error", "error": {"type": "invalid_request_error", "message": "anthropic-version header is required"}})
		if method == "GET" and path.startswith("/v1/models"):
			return self._send(200, {"data": [{"id": "claude-sonnet-5-5", "type": "model"}, {"id": "claude-haiku-4-5-20251001", "type": "model"}], "has_more": False, "last_id": "claude-haiku-4-5-20251001"})
		if method == "POST" and path == "/v1/messages":
			assert isinstance(body["max_tokens"], int)
			msgs = body["messages"]
			assert msgs[0]["role"] == "user" and msgs[-1]["role"] == "user"
			for a, b in zip(msgs, msgs[1:]):
				assert a["role"] != b["role"], "roles must alternate"
			content = msgs[-1]["content"]
			kinds = []
			for c in content[:-1]:
				if c["type"] == "image":
					assert c["source"]["media_type"] in ("image/png", "image/jpeg", "image/gif", "image/webp")
				elif c["type"] == "document":
					assert c["source"]["media_type"] == "application/pdf"
				else:
					assert c["type"] == "text"
				kinds.append(c["type"])
			LAST_ATTACHMENTS["anthropic"] = kinds
			assert content[-1]["type"] == "text"
			text = content[-1]["text"]
			return self._send(200, {"type": "message", "role": "assistant", "content": [{"type": "text", "text": "Claude responde: %s (%d mensagens)" % (text, len(msgs))}], "stop_reason": "end_turn"})
		self._send(404, {"type": "error", "error": {"type": "not_found_error", "message": "not found"}})

	# Sign in with ChatGPT ------------------------------------------------------
	def _issuer(self):
		return "http://%s/chatgpt/auth" % self.headers.get("Host")

	def _chatgptAuth(self, method, path, body):
		issuer = self._issuer()
		parts = urllib.parse.urlsplit(path)
		if method == "GET" and parts.path == "/.well-known/openid-configuration":
			return self._send(200, {
				"issuer": issuer,
				"authorization_endpoint": issuer + "/api/accounts/authorize",
				"token_endpoint": issuer + "/api/accounts/oauth/token",
				"jwks_uri": issuer + "/jwks",
				"revocation_endpoint": issuer + "/revoke",
			})
		if method == "GET" and parts.path == "/jwks":
			n = _testkey.N.to_bytes((_testkey.N.bit_length() + 7) // 8, "big")
			return self._send(200, {"keys": [{"kty": "RSA", "use": "sig", "alg": "RS256", "kid": _testkey.KID, "n": _b64url(n), "e": _b64url(_testkey.E.to_bytes(3, "big"))}]})
		if method == "GET" and parts.path == "/api/accounts/authorize":
			q = dict(urllib.parse.parse_qsl(parts.query))
			CHATGPT["authorize"].append(q)
			assert q["response_type"] == "code" and q["code_challenge_method"] == "S256"
			assert q["scope"] == PLAN_SCOPES and q["resource"] == "https://api.openai.com/v1"
			assert q["redirect_uri"].startswith("http://127.0.0.1:") and q["redirect_uri"].endswith("/callback")
			assert q["ext_agent_host_id"].startswith("urn:uuid:")
			assert q["client_id"] in ("dynamic_agent_client", ISSUED_CLIENT)
			assert ("agent_name_hint" in q) == (q["client_id"] == "dynamic_agent_client")
			state = "wrong-state" if CHATGPT["wrong_state"] else q["state"]
			if CHATGPT["deny"]:
				query = {"error": "access_denied", "state": state}
			else:
				CHATGPT["counter"] += 1
				code = "code-%d" % CHATGPT["counter"]
				CHATGPT["codes"][code] = q
				query = {"code": code, "state": state, "client_id": ISSUED_CLIENT, "scope": CHATGPT["scope"]}
			return self._send(200, {"location": q["redirect_uri"] + "?" + urllib.parse.urlencode(query)})
		if method == "POST" and parts.path == "/api/accounts/oauth/token":
			assert "client_secret" not in body
			if body.get("resource") != "https://api.openai.com/v1" or body.get("client_id") != ISSUED_CLIENT:
				return self._send(401, {"error": "invalid_client"})
			if body.get("grant_type") == "authorization_code":
				req = CHATGPT["codes"].pop(body.get("code"), None)
				if req is None or body.get("redirect_uri") != req["redirect_uri"]:
					return self._send(400, {"error": "invalid_grant"})
				challenge = _b64url(hashlib.sha256(body.get("code_verifier", "").encode()).digest())
				if challenge != req["code_challenge"]:
					return self._send(400, {"error": "invalid_grant", "error_description": "PKCE"})
				nonce = "other" if CHATGPT["bad_nonce"] else req["nonce"]
				return self._send(200, self._tokens(issuer, nonce))
			if body.get("grant_type") == "refresh_token":
				rt = body.get("refresh_token")
				if rt in CHATGPT["used_refresh"]:
					return self._send(400, {"error": "refresh_token_reused"})
				if rt not in CHATGPT["refresh"]:
					return self._send(400, {"error": "invalid_grant"})
				CHATGPT["refresh"].discard(rt)
				CHATGPT["used_refresh"].add(rt)
				return self._send(200, self._tokens(issuer, None))
			return self._send(400, {"error": "unsupported_grant_type"})
		if method == "POST" and parts.path == "/revoke":
			CHATGPT["revoked"].append(body)
			CHATGPT["refresh"].discard(body.get("token"))
			return self._send("raw", b"")
		self._send(404, {"error": "not found"})

	def _tokens(self, issuer, nonce):
		CHATGPT["counter"] += 1
		n = CHATGPT["counter"]
		access, refresh = "at-%d" % n, "rt-%d" % n
		CHATGPT["access"].add(access)
		CHATGPT["refresh"].add(refresh)
		out = {
			"access_token": access, "refresh_token": refresh, "token_type": "Bearer",
			"expires_in": CHATGPT["expires_in"], "scope": CHATGPT["scope"],
			"earliest_refresh_at": int(time.time()) + 60,
		}
		if nonce is not None:
			claims = {"iss": issuer, "aud": ISSUED_CLIENT, "sub": "user-123", "email": CHATGPT["email"],
				"exp": int(time.time()) + 3600, "iat": int(time.time()), "nonce": nonce}
			out["id_token"] = signJwt(claims, corrupt=CHATGPT["bad_signature"])
		return out

	def _sendSse(self, text):
		data = text.encode("utf-8")
		self.send_response(200)
		self.send_header("Content-Type", "text/event-stream")
		self.send_header("Content-Length", str(len(data)))
		self.end_headers()
		self.wfile.write(data)

	def _chatgptApi(self, method, path, body):
		if FORCE.get("chatgpt"):
			status, payload = FORCE["chatgpt"]
			if status == "sse":
				return self._sendSse(payload)
			return self._send(status, payload)
		auth = self.headers.get("Authorization") or ""
		if not auth.startswith("Bearer ") or auth[7:] not in CHATGPT["access"]:
			return self._send(401, {"error": {"message": "invalid token", "code": "invalid_api_key"}})
		if method == "GET" and path == "/models":
			return self._send(200, {"models": [
				{"slug": "gpt-5.5", "display_name": "GPT-5.5", "visibility": "list"},
				{"slug": "gpt-internal", "display_name": "Hidden", "visibility": "hide"},
				{"slug": "gpt-5.5-mini", "display_name": "GPT-5.5 mini", "visibility": "list"},
			]})
		if method == "POST" and path == "/responses":
			CHATGPT["responses"].append(body)
			assert self.headers.get("Accept") == "text/event-stream"
			assert body["store"] is False and body["stream"] is True
			for field in ("temperature", "max_output_tokens", "metadata", "user", "previous_response_id", "top_p", "truncation"):
				assert field not in body, field
			assert body["model"] in ("gpt-5.5", "gpt-5.5-mini"), body["model"]
			items = body["input"]
			for item in items:
				assert item["role"] in ("user", "assistant"), "system messages are rejected"
			last = items[-1]
			assert last["role"] == "user"
			kinds = []
			for part in last["content"][:-1]:
				if part["type"] == "input_image":
					assert part["image_url"].startswith("data:image/")
					kinds.append("imagem")
				elif part["type"] == "input_file":
					assert part["file_data"].startswith("data:application/pdf;base64,") and part["filename"]
					kinds.append("pdf")
				else:
					assert part["type"] == "input_text" and part["text"].startswith("<file name=")
					kinds.append("texto")
			assert last["content"][-1]["type"] == "input_text"
			LAST_ATTACHMENTS["chatgpt"] = kinds
			if CHATGPT["stream"]:
				return self._sendSse(CHATGPT["stream"])
			question = last["content"][-1]["text"]
			answer = "Plano ChatGPT responde: %s (%d mensagens)" % (question, len(items))
			half = len(answer) // 2
			events = [
				{"type": "response.created", "response": {"id": "resp_1", "status": "in_progress"}},
				{"type": "response.output_text.delta", "delta": answer[:half]},
				{"type": "response.output_text.delta", "delta": answer[half:]},
				{"type": "response.output_text.done", "text": answer},
				{"type": "response.completed", "response": {"id": "resp_1", "status": "completed"}},
			]
			return self._sendSse("".join("event: %s\ndata: %s\n\n" % (e["type"], json.dumps(e)) for e in events))
		self._send(404, {"error": {"message": "not found"}})


def start():
	server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
	t = threading.Thread(target=server.serve_forever, daemon=True)
	t.start()
	return server, "http://127.0.0.1:%d" % server.server_address[1]
