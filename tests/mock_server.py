# -*- coding: UTF-8 -*-
"""Local HTTP server that imitates the OpenAI, Gemini and Anthropic APIs.

It checks the authentication headers and the shape of each request body the
same way the real services do, and records every request for assertions.
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

VALID = {"openai": "sk-test-openai-123456", "gemini": "AIza-test-gemini-123456", "anthropic": "sk-ant-test-123456"}
REQUESTS = []
#: Optional overrides: {"openai": (status, body)} to force an answer.
FORCE = {}
DELAY = {"seconds": 0}
LAST_ATTACHMENTS = {}


class Handler(BaseHTTPRequestHandler):
	def log_message(self, *a):
		pass

	def _send(self, status, body):
		data = json.dumps(body).encode("utf-8")
		self.send_response(status)
		self.send_header("Content-Type", "application/json")
		self.send_header("Content-Length", str(len(data)))
		self.end_headers()
		self.wfile.write(data)

	def _body(self):
		length = int(self.headers.get("Content-Length") or 0)
		return json.loads(self.rfile.read(length).decode("utf-8")) if length else None

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


def start():
	server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
	t = threading.Thread(target=server.serve_forever, daemon=True)
	t.start()
	return server, "http://127.0.0.1:%d" % server.server_address[1]
