# -*- coding: UTF-8 -*-
# NVDAIAs - chatgptPlan.py
# "Sign in with ChatGPT": uses the user's ChatGPT plan (Plus, Pro...) instead of an
# API key, following OpenAI's guide for open-source and locally run apps
# (developers.openai.com/siwc/token-sharing-open-source).
# Copyright (C) 2026 Wellington Cruz
# This file is covered by the GNU General Public License, version 2.
#
# Flow: OAuth 2.0 authorization code with PKCE in the default browser, answer
# received by a small server that listens only on 127.0.0.1, tokens exchanged
# directly with auth.openai.com, ID token checked (RS256 signature, issuer,
# audience, expiry and nonce), session stored encrypted with DPAPI, access token
# refreshed when needed, refresh token revoked on sign out.
#
# Like providers.py, this module uses only the Python standard library and does
# not import NVDA modules, so it can be unit tested outside NVDA. NVDA ships only
# the parts of the standard library it uses itself, so this module avoids
# secrets, hmac, http.server and socketserver (see tests: NVDA_STDLIB).

import base64
import hashlib
import html
import json
import os
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

from .providers import USER_AGENT, BaseProvider, ProviderError, _extractErrorMessage, _urlopen

ISSUER = "https://auth.openai.com"
API_BASE = "https://api.openai.com/v1"
#: Resource the tokens are issued for (always the production API address).
RESOURCE = "https://api.openai.com/v1"
SCOPES = "openid profile email offline_access resource.invoke chatgpt.tokens.use.direct"
PLAN_SCOPE = "chatgpt.tokens.use.direct"
DYNAMIC_CLIENT = "dynamic_agent_client"
AGENT_NAME = "NVDAIAs"
#: ChatGPT page where the user sees and manages the plan usage.
USAGE_URL = "https://chatgpt.com/settings/usage"
#: Keys used in the credential store (encrypted with DPAPI like the API tokens).
SESSION_KEY = "openai_plan"
REGISTRATION_KEY = "openai_plan_registration"
#: Refresh the access token this many seconds before it expires.
REFRESH_MARGIN = 120
#: Clock difference accepted when checking the ID token.
CLOCK_SKEW = 300
#: How long to wait for the user to finish signing in in the browser.
SIGN_IN_TIMEOUT = 300

#: Refresh errors that mean the session is over and the user must sign in again.
REFRESH_ERRORS = frozenset((
	"invalid_grant", "invalid_refresh_token", "token_expired",
	"refresh_token_expired", "refresh_token_invalidated", "refresh_token_reused",
))

#: Responses API error codes of ChatGPT plan usage -> ProviderError kind.
PLAN_ERRORS = {
	"subscription_sharing_usage_limit_exceeded": "planLimit",
	"subscription_sharing_user_not_eligible": "planNotEligible",
	"subscription_sharing_route_not_supported": "planNotEligible",
	"chatpass_v2_scope_not_authorized": "planNotEligible",
	"chatpass_v2_invalid_authorization_context": "planNotEligible",
	"subscription_sharing_invalid_user": "signin",
	"subscription_sharing_usage_unavailable": "server",
	"subscription_sharing_user_unavailable": "server",
	"subscription_sharing_unsupported_capability": "unsupported",
}


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def b64url(data):
	return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def b64urlDecode(text):
	if isinstance(text, str):
		text = text.encode("ascii")
	return base64.urlsafe_b64decode(text + b"=" * (-len(text) % 4))


def constantTimeEqual(a, b):
	"""Comparison that takes the same time wherever the first difference is."""
	if isinstance(a, str):
		a = a.encode("utf-8")
	if isinstance(b, str):
		b = b.encode("utf-8")
	result = len(a) ^ len(b)
	for x, y in zip(a, b if len(a) == len(b) else a):
		result |= x ^ y
	return result == 0


def randomToken(nbytes=32):
	return b64url(os.urandom(nbytes))


def pkcePair():
	"""Returns (verifier, challenge) for PKCE with S256."""
	verifier = b64url(os.urandom(48))
	challenge = b64url(hashlib.sha256(verifier.encode("ascii")).digest())
	return verifier, challenge


def newHostId():
	"""Opaque and stable identifier of this computer for OpenAI (never the e-mail or user name)."""
	return "urn:uuid:" + str(uuid.uuid4())


def scopeSet(scope):
	if isinstance(scope, (list, tuple, set, frozenset)):
		return set(scope)
	return set((scope or "").split())


def _trustedUrl(url, issuer):
	"""Addresses announced by the authorization server are only used when they
	belong to it: the same origin, or HTTPS on an openai.com host."""
	a = urllib.parse.urlsplit(url)
	b = urllib.parse.urlsplit(issuer)
	if (a.scheme, a.hostname, a.port) == (b.scheme, b.hostname, b.port):
		return True
	host = (a.hostname or "").lower()
	return a.scheme == "https" and (host == "openai.com" or host.endswith(".openai.com"))


# ---------------------------------------------------------------------------
# JWT (ID token) checks
# ---------------------------------------------------------------------------

#: DER prefix of the SHA-256 DigestInfo used by RSASSA-PKCS1-v1_5.
_SHA256_PREFIX = bytes.fromhex("3031300d060960864801650304020105000420")


def verifyRs256(signingInput, signature, n, e):
	"""RSASSA-PKCS1-v1_5 with SHA-256 (JWT "RS256"), standard library only."""
	k = (n.bit_length() + 7) // 8
	if k < 256 or len(signature) != k:  # at least 2048-bit keys
		return False
	s = int.from_bytes(signature, "big")
	if s >= n:
		return False
	em = pow(s, e, n).to_bytes(k, "big")
	digestInfo = _SHA256_PREFIX + hashlib.sha256(signingInput).digest()
	expected = b"\x00\x01" + b"\xff" * (k - 3 - len(digestInfo)) + b"\x00" + digestInfo
	return constantTimeEqual(em, expected)


def decodeJwt(token):
	"""Returns (header, claims, signingInput, signature). Does not verify anything."""
	try:
		h, p, s = token.split(".")
		header = json.loads(b64urlDecode(h))
		claims = json.loads(b64urlDecode(p))
		signature = b64urlDecode(s)
	except Exception:
		raise ProviderError("signin", "invalid ID token")
	if not isinstance(header, dict) or not isinstance(claims, dict):
		raise ProviderError("signin", "invalid ID token")
	return header, claims, (h + "." + p).encode("ascii"), signature


def validateIdToken(token, keys, issuer, clientId, nonce, now=None):
	"""Checks the ID token and returns its claims.

	``keys`` maps the key id (kid) to (n, e). The signature is required for RS256,
	the algorithm OpenAI publishes. The token is received directly from the token
	endpoint over verified TLS, so for any other algorithm (none is accepted) the
	TLS channel is the proof of origin, as OpenID Connect Core 3.1.3.7 allows."""
	header, claims, signingInput, signature = decodeJwt(token)
	alg = header.get("alg")
	if alg in (None, "none", "None", "NONE") or str(alg).startswith("HS"):
		raise ProviderError("signin", "ID token algorithm not accepted")
	if alg == "RS256":
		key = keys.get(header.get("kid")) if header.get("kid") else (next(iter(keys.values())) if len(keys) == 1 else None)
		if key is None or not verifyRs256(signingInput, signature, key[0], key[1]):
			raise ProviderError("signin", "ID token signature is not valid")
	now = time.time() if now is None else now
	if claims.get("iss") != issuer:
		raise ProviderError("signin", "ID token issuer is not valid")
	aud = claims.get("aud")
	audiences = aud if isinstance(aud, list) else [aud]
	if clientId not in audiences:
		raise ProviderError("signin", "ID token audience is not valid")
	if len(audiences) > 1 and claims.get("azp") not in (None, clientId):
		raise ProviderError("signin", "ID token audience is not valid")
	try:
		exp = float(claims.get("exp"))
	except (TypeError, ValueError):
		raise ProviderError("signin", "ID token without expiry")
	if exp + CLOCK_SKEW < now:
		raise ProviderError("signin", "ID token expired")
	if not nonce or not constantTimeEqual(str(claims.get("nonce") or ""), nonce):
		raise ProviderError("signin", "ID token nonce is not valid")
	if not claims.get("sub"):
		raise ProviderError("signin", "ID token without subject")
	return claims


def jwksToKeys(jwks):
	keys = {}
	for k in (jwks or {}).get("keys", []):
		if not isinstance(k, dict) or k.get("kty") != "RSA" or k.get("use", "sig") != "sig":
			continue
		try:
			n = int.from_bytes(b64urlDecode(k["n"]), "big")
			e = int.from_bytes(b64urlDecode(k["e"]), "big")
		except Exception:
			continue
		keys[k.get("kid")] = (n, e)
	return keys


# ---------------------------------------------------------------------------
# OAuth client (auth.openai.com)
# ---------------------------------------------------------------------------

class OAuthClient:
	"""Talks to the OpenAI authorization server. ``opener(req, timeout)`` lets tests
	use a fake transport; ``issuer`` lets tests use a local server."""

	def __init__(self, issuer=None, opener=None, timeout=30):
		self.issuer = (issuer or ISSUER).rstrip("/")
		self._opener = opener
		self.timeout = timeout
		self._discovery = None
		self._keys = None

	@property
	def authorizeUrl(self):
		return self.issuer + "/api/accounts/authorize"

	@property
	def tokenUrl(self):
		return self.issuer + "/api/accounts/oauth/token"

	def _http(self, method, url, form=None):
		data = urllib.parse.urlencode(form).encode("utf-8") if form is not None else None
		headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
		if data is not None:
			headers["Content-Type"] = "application/x-www-form-urlencoded"
		req = urllib.request.Request(url, data=data, headers=headers, method=method)
		try:
			if self._opener is not None:
				raw = self._opener(req, self.timeout)
			else:
				raw = _urlopen(req, self.timeout)
		except urllib.error.HTTPError as e:
			try:
				payload = json.loads(e.read().decode("utf-8", "replace"))
			except Exception:
				payload = None
			code = ""
			if isinstance(payload, dict):
				err = payload.get("error")
				code = err.get("code", "") if isinstance(err, dict) else (err or "")
			err = ProviderError("signin" if e.code in (400, 401) else "server", str(code or _extractErrorMessage(payload) or "HTTP %d" % e.code)[:200], e.code)
			err.code = code
			raise err
		except (socket.timeout, TimeoutError):
			raise ProviderError("timeout", "timeout")
		except urllib.error.URLError as e:
			reason = getattr(e, "reason", e)
			if isinstance(reason, (socket.timeout, TimeoutError)):
				raise ProviderError("timeout", str(reason))
			raise ProviderError("network", str(reason))
		except (ConnectionError, OSError) as e:
			raise ProviderError("network", str(e))
		if not raw:
			return {}
		try:
			return json.loads(raw.decode("utf-8"))
		except Exception:
			raise ProviderError("server", "invalid JSON response")

	def discovery(self):
		if self._discovery is None:
			data = self._http("GET", self.issuer + "/.well-known/openid-configuration")
			if not isinstance(data, dict):
				raise ProviderError("server", "invalid OpenID configuration")
			# Only addresses of the same authorization server are trusted.
			for name in ("jwks_uri", "revocation_endpoint"):
				url = data.get(name)
				if url and not _trustedUrl(url, self.issuer):
					raise ProviderError("server", "unexpected %s" % name)
			self._discovery = data
		return self._discovery

	def keys(self, refresh=False):
		if self._keys is None or refresh:
			uri = self.discovery().get("jwks_uri")
			if not uri:
				raise ProviderError("server", "no jwks_uri")
			self._keys = jwksToKeys(self._http("GET", uri))
		return self._keys

	def validateIdToken(self, token, clientId, nonce, now=None):
		keys = self.keys()
		header = decodeJwt(token)[0]
		if header.get("alg") == "RS256" and header.get("kid") and header.get("kid") not in keys:
			keys = self.keys(refresh=True)  # keys were rotated
		return validateIdToken(token, keys, self.issuer, clientId, nonce, now)

	def buildAuthorizeUrl(self, clientId, hostId, redirectUri, state, nonce, challenge, loginHint=None):
		params = [("client_id", clientId)]
		if clientId == DYNAMIC_CLIENT:
			params.append(("agent_name_hint", AGENT_NAME))
		params += [
			("ext_agent_host_id", hostId),
			("response_type", "code"),
			("redirect_uri", redirectUri),
			("scope", SCOPES),
			("resource", RESOURCE),
			("state", state),
			("nonce", nonce),
			("code_challenge_method", "S256"),
			("code_challenge", challenge),
		]
		if loginHint:
			params.append(("login_hint", loginHint))
		return self.authorizeUrl + "?" + urllib.parse.urlencode(params, quote_via=urllib.parse.quote)

	def exchangeCode(self, clientId, code, verifier, redirectUri):
		return self._http("POST", self.tokenUrl, {
			"grant_type": "authorization_code",
			"client_id": clientId,
			"code": code,
			"code_verifier": verifier,
			"redirect_uri": redirectUri,
			"resource": RESOURCE,
		})

	def refresh(self, clientId, refreshToken):
		return self._http("POST", self.tokenUrl, {
			"grant_type": "refresh_token",
			"client_id": clientId,
			"refresh_token": refreshToken,
			"resource": RESOURCE,
		})

	def revoke(self, clientId, refreshToken):
		url = self.discovery().get("revocation_endpoint")
		if not url:
			return False
		self._http("POST", url, {"token": refreshToken, "token_type_hint": "refresh_token", "client_id": clientId})
		return True


# ---------------------------------------------------------------------------
# Loopback receiver (http://127.0.0.1:PORT/callback)
# ---------------------------------------------------------------------------

_PAGE = (
	"<!DOCTYPE html><html><head><meta charset=\"utf-8\"><title>{title}</title></head>"
	"<body><main><h1>{title}</h1><p>{text}</p></main></body></html>"
)


_REASONS = {200: "OK", 400: "Bad Request", 404: "Not Found", 405: "Method Not Allowed"}
#: Biggest request accepted by the loopback listener.
_MAX_REQUEST = 16 * 1024


class LoopbackReceiver:
	"""Waits for the browser to come back to http://127.0.0.1:PORT/callback.

	A tiny HTTP listener written on plain sockets: NVDA ships only the parts of
	the Python standard library it uses itself, and http.server/socketserver
	are not guaranteed to be there. It listens only on 127.0.0.1, answers only
	GET /callback with the right state, and never logs the address (it carries
	the authorization code)."""

	#: Texts of the pages shown in the browser (the add-on passes them translated).
	DEFAULT_PAGES = {
		"done": "Signed in. You can close this tab and go back to NVDA.",
		"error": "Sign-in was not completed. You can close this tab and go back to NVDA.",
		"invalid": "This address does not belong to the current sign-in.",
	}

	def __init__(self, state, pages=None):
		self.state = state
		self.pages = dict(self.DEFAULT_PAGES, **(pages or {}))
		self.result = None
		self._event = threading.Event()
		self._closed = False
		self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self._sock.bind(("127.0.0.1", 0))
		self._sock.listen(8)
		self._sock.settimeout(0.3)
		self.address = self._sock.getsockname()
		self._thread = threading.Thread(target=self._serve, name="NVDAIAs-signin", daemon=True)
		self._thread.start()

	@property
	def port(self):
		return self.address[1]

	@property
	def redirectUri(self):
		return "http://127.0.0.1:%d/callback" % self.port

	def _serve(self):
		while not self._closed:
			try:
				conn, _peer = self._sock.accept()
			except socket.timeout:
				continue
			except OSError:
				break
			try:
				self._handle(conn)
			except Exception:  # a broken request never stops the sign-in
				pass
			finally:
				try:
					conn.close()
				except OSError:
					pass

	def _handle(self, conn):
		conn.settimeout(5)
		data = b""
		while b"\r\n\r\n" not in data and b"\n\n" not in data:
			chunk = conn.recv(4096)
			if not chunk:
				break
			data += chunk
			if len(data) > _MAX_REQUEST:
				break
		line = data.split(b"\n", 1)[0].decode("latin-1").strip()
		parts = line.split(" ")
		if len(parts) < 2:
			return self._reply(conn, 400, self.pages["invalid"])
		method, target = parts[0], parts[1]
		url = urllib.parse.urlsplit(target)
		if url.path != "/callback":
			return self._reply(conn, 404, "Not found.")
		if method != "GET":
			return self._reply(conn, 405, "Not allowed.")
		params = {k: v[0] for k, v in urllib.parse.parse_qs(url.query, keep_blank_values=True).items()}
		# A request with another state does not come from this sign-in: ignore it.
		if not constantTimeEqual(params.get("state", ""), self.state):
			return self._reply(conn, 400, self.pages["invalid"])
		self._reply(conn, 200, self.pages["error"] if params.get("error") else self.pages["done"])
		self._finish(params)

	@staticmethod
	def _reply(conn, status, text):
		body = _PAGE.format(title="NVDAIAs", text=html.escape(text)).encode("utf-8")
		head = (
			"HTTP/1.1 %d %s\r\n"
			"Content-Type: text/html; charset=utf-8\r\n"
			"Content-Length: %d\r\n"
			"Cache-Control: no-store\r\n"
			"Referrer-Policy: no-referrer\r\n"
			"Connection: close\r\n\r\n"
		) % (status, _REASONS.get(status, "Error"), len(body))
		conn.sendall(head.encode("ascii") + body)

	def _finish(self, params):
		if self.result is None:
			self.result = params
			self._event.set()

	def wait(self, timeout, cancelEvent=None):
		"""Returns the callback parameters. Raises ProviderError timeout or cancelled."""
		deadline = time.monotonic() + timeout
		while True:
			if cancelEvent is not None and cancelEvent.is_set():
				raise ProviderError("cancelled", "sign-in cancelled")
			if self._event.wait(0.2):
				return self.result
			if time.monotonic() >= deadline:
				raise ProviderError("timeout", "sign-in")

	def close(self):
		self._closed = True
		try:
			self._sock.close()
		except OSError:
			pass


# ---------------------------------------------------------------------------
# Session storage and refresh
# ---------------------------------------------------------------------------

class PlanStore:
	"""Session and registration kept in the credential store (DPAPI)."""

	def __init__(self, credentialStore):
		self.credentials = credentialStore

	def _getJson(self, key):
		raw = self.credentials.get(key)
		if not raw:
			return {}
		try:
			data = json.loads(raw)
		except ValueError:
			return {}
		return data if isinstance(data, dict) else {}

	def session(self):
		return self._getJson(SESSION_KEY)

	def saveSession(self, session):
		self.credentials.set(SESSION_KEY, json.dumps(session))

	def clearSession(self):
		self.credentials.remove(SESSION_KEY)

	def registration(self):
		"""client_id issued by OpenAI, this computer's host id and the last e-mail."""
		return self._getJson(REGISTRATION_KEY)

	def saveRegistration(self, registration):
		self.credentials.set(REGISTRATION_KEY, json.dumps(registration))


class PlanSession:
	"""The signed-in ChatGPT account. Thread safe: refreshes are serialised."""

	def __init__(self, store, client=None, clock=time.time):
		self.store = store
		self.client = client or OAuthClient()
		self.clock = clock
		self._lock = threading.RLock()

	# State -----------------------------------------------------------------

	def signedIn(self):
		s = self.store.session()
		return bool(s.get("refresh_token") and s.get("access_token") and s.get("client_id"))

	def email(self):
		return self.store.session().get("email", "")

	def hostId(self):
		with self._lock:
			reg = self.store.registration()
			if not reg.get("ext_agent_host_id"):
				reg["ext_agent_host_id"] = newHostId()
				self.store.saveRegistration(reg)
			return reg["ext_agent_host_id"]

	# Sign in -----------------------------------------------------------------

	def signIn(self, openBrowser, cancelEvent=None, timeout=SIGN_IN_TIMEOUT, pages=None):
		"""Runs the whole browser sign-in and stores the session. Returns it.

		``openBrowser(url)`` must open the address in the default browser and
		return False when it could not."""
		hostId = self.hostId()
		reg = self.store.registration()
		clientId = reg.get("client_id") or DYNAMIC_CLIENT
		state = randomToken()
		nonce = randomToken()
		verifier, challenge = pkcePair()
		receiver = LoopbackReceiver(state, pages)
		try:
			url = self.client.buildAuthorizeUrl(clientId, hostId, receiver.redirectUri, state, nonce, challenge, loginHint=reg.get("email"))
			if openBrowser(url) is False:
				raise ProviderError("browser", url)
			params = receiver.wait(timeout, cancelEvent)
		finally:
			receiver.close()
		if params.get("error"):
			if params["error"] == "access_denied":
				raise ProviderError("denied", "access_denied")
			if clientId != DYNAMIC_CLIENT:
				# The saved registration was not accepted: next time register again.
				reg.pop("client_id", None)
				self.store.saveRegistration(reg)
			raise ProviderError("signin", str(params["error"])[:100])
		code = params.get("code")
		issued = params.get("client_id") or clientId
		if not code or issued == DYNAMIC_CLIENT:
			raise ProviderError("signin", "incomplete answer from the sign-in page")
		# Keep the issued client id before anything else, to reuse it next time.
		reg["client_id"] = issued
		self.store.saveRegistration(reg)
		if cancelEvent is not None and cancelEvent.is_set():
			raise ProviderError("cancelled", "sign-in cancelled")
		tokens = self.client.exchangeCode(issued, code, verifier, receiver.redirectUri)
		session = self._sessionFromTokens(tokens, issued, hostId, nonce)
		with self._lock:
			self.store.saveSession(session)
			reg["email"] = session.get("email", "")
			self.store.saveRegistration(reg)
		return session

	def _sessionFromTokens(self, tokens, clientId, hostId, nonce):
		if not isinstance(tokens, dict) or not tokens.get("access_token") or not tokens.get("refresh_token") or not tokens.get("id_token"):
			raise ProviderError("signin", "incomplete token answer")
		scopes = scopeSet(tokens.get("scope"))
		if PLAN_SCOPE not in scopes:
			raise ProviderError("planNotEligible", "scope %s not granted" % PLAN_SCOPE)
		claims = self.client.validateIdToken(tokens["id_token"], clientId, nonce, now=self.clock())
		now = self.clock()
		return {
			"email": claims.get("email", ""),
			"issuer": claims.get("iss"),
			"subject": claims.get("sub"),
			"client_id": clientId,
			"ext_agent_host_id": hostId,
			"id_token": tokens["id_token"],
			"access_token": tokens["access_token"],
			"refresh_token": tokens["refresh_token"],
			"token_type": tokens.get("token_type", "Bearer"),
			"scopes": sorted(scopes),
			"expires_at": now + _seconds(tokens.get("expires_in"), 3600),
			"earliest_refresh_at": _timestamp(tokens.get("earliest_refresh_at")),
			"saved_at": now,
		}

	# Tokens ----------------------------------------------------------------

	def accessToken(self, force=False):
		"""Valid access token, refreshed when it is about to expire (or ``force``)."""
		with self._lock:
			s = self.store.session()
			if not s.get("access_token") or not s.get("refresh_token"):
				raise ProviderError("signin", "not signed in")
			now = self.clock()
			expired = now >= float(s.get("expires_at") or 0) - REFRESH_MARGIN
			if force or expired:
				early = float(s.get("earliest_refresh_at") or 0)
				if not force and not now >= float(s.get("expires_at") or 0) and now < early:
					return s["access_token"]
				s = self._refresh(s)
			return s["access_token"]

	def _refresh(self, s):
		try:
			tokens = self.client.refresh(s["client_id"], s["refresh_token"])
		except ProviderError as e:
			code = getattr(e, "code", "")
			if code in REFRESH_ERRORS:
				self.store.clearSession()
				raise ProviderError("signin", code, e.status)
			if code == "invalid_client":
				self.store.clearSession()
				reg = self.store.registration()
				reg.pop("client_id", None)
				self.store.saveRegistration(reg)
				raise ProviderError("signin", code, e.status)
			raise
		if not isinstance(tokens, dict) or not tokens.get("access_token"):
			raise ProviderError("server", "invalid refresh answer")
		now = self.clock()
		s = dict(s)
		s["access_token"] = tokens["access_token"]
		if tokens.get("refresh_token"):
			s["refresh_token"] = tokens["refresh_token"]  # rotating refresh token
		if tokens.get("id_token"):
			s["id_token"] = tokens["id_token"]
		if tokens.get("scope"):
			s["scopes"] = sorted(scopeSet(tokens["scope"]))
		s["expires_at"] = now + _seconds(tokens.get("expires_in"), 3600)
		s["earliest_refresh_at"] = _timestamp(tokens.get("earliest_refresh_at"))
		s["saved_at"] = now
		self.store.saveSession(s)
		if PLAN_SCOPE not in set(s.get("scopes") or ()):
			raise ProviderError("planNotEligible", "scope %s not granted" % PLAN_SCOPE)
		return s

	def endSession(self):
		"""Deletes the stored session at once and returns it (to be revoked)."""
		with self._lock:
			s = self.store.session()
			self.store.clearSession()
		return s

	def revoke(self, s):
		"""Revokes the refresh token of a session (best effort, talks to OpenAI).
		Returns True when OpenAI confirmed the revocation."""
		if not s or not s.get("refresh_token") or not s.get("client_id"):
			return False
		try:
			return self.client.revoke(s["client_id"], s["refresh_token"])
		except ProviderError:
			return False

	def signOut(self):
		"""Deletes the session and revokes its refresh token."""
		return self.revoke(self.endSession())


def _seconds(value, default):
	try:
		value = float(value)
	except (TypeError, ValueError):
		return default
	return value if 0 < value < 10 * 365 * 86400 else default


def _timestamp(value):
	"""earliest_refresh_at may come as seconds since 1970 or as an ISO date."""
	if value in (None, ""):
		return 0
	try:
		return float(value)
	except (TypeError, ValueError):
		pass
	try:
		import datetime
		text = str(value).replace("Z", "+00:00")
		return datetime.datetime.fromisoformat(text).timestamp()
	except Exception:
		return 0


# ---------------------------------------------------------------------------
# Provider: Responses API with the ChatGPT plan
# ---------------------------------------------------------------------------

def planErrorKind(code, status):
	if code in PLAN_ERRORS:
		return PLAN_ERRORS[code]
	if status == 401:
		return "signin"
	if status == 403:
		return "planNotEligible"
	if status == 429:
		return "planLimit"
	if status == 404:
		return "model"
	if status and (status >= 500 or 300 <= status < 400):
		return "server"
	return "other"


class ChatGPTPlanProvider(BaseProvider):
	"""ChatGPT using the user's plan. Same id as the API key provider ("openai"):
	it is the same AI, only the way of paying changes."""

	id = "openai"
	name = "ChatGPT"
	usesPlan = True
	tokenUrl = "https://platform.openai.com/api-keys"
	defaultBaseUrl = API_BASE
	defaultModel = ""
	suggestedModels = ()

	def __init__(self, session, model=None, timeout=120, maxTokens=4096, baseUrl=None, opener=None):
		# The API key slot only marks the provider as usable; the real
		# credential is the access token of the session.
		super().__init__("chatgpt-plan", model=model or "", timeout=timeout, maxTokens=maxTokens, baseUrl=baseUrl, opener=opener)
		self.session = session
		self._token = ""

	def _headers(self):
		return {"Authorization": "Bearer " + self._token}

	def _httpError(self, status, payload):
		code = ""
		detail = ""
		if isinstance(payload, dict):
			err = payload.get("error")
			if isinstance(err, dict):
				code = err.get("code") or ""
				if code == "subscription_sharing_unsupported_capability":
					detail = err.get("param") or err.get("message") or code
				else:
					detail = err.get("message") or code
			elif isinstance(payload.get("detail"), str):
				detail = payload["detail"]
		detail = str(detail or code or "HTTP %d" % status)[:300]
		err =ProviderError(planErrorKind(code, status), detail, status)
		err.code = code
		return err

	def _authed(self, method, path, body=None, query=None, stream=False):
		for attempt in (0, 1):
			self._token = self.session.accessToken(force=attempt == 1)
			try:
				if stream:
					return self._requestRaw(method, path, body, query, accept="text/event-stream")
				return self._request(method, path, body, query)
			except ProviderError as e:
				# 401 once: the access token may have just been revoked or rotated.
				if e.status == 401 and attempt == 0 and getattr(e, "code", "") != "subscription_sharing_invalid_user":
					continue
				raise
			finally:
				self._token = ""

	def buildBody(self, messages, systemPrompt=""):
		items = []
		for m in messages:
			if m.role == "assistant":
				items.append({"role": "assistant", "content": m.text})
				continue
			content = []
			for a in m.attachments:
				if a.kind == "image":
					content.append({"type": "input_image", "image_url": a.dataUrl()})
				elif a.kind == "pdf":
					content.append({"type": "input_file", "filename": a.name, "file_data": a.dataUrl()})
				elif a.kind == "text":
					content.append({"type": "input_text", "text": a.asPromptText()})
				else:
					# Audio and video are not supported with the ChatGPT plan.
					raise ProviderError("attachment", a.name)
			content.append({"type": "input_text", "text": m.text})
			items.append({"role": "user", "content": content})
		# Only the fields allowed by the plan usage preview are sent
		# (no temperature, max_output_tokens, metadata, user...).
		body = {"model": self.model, "input": items, "store": False, "stream": True}
		if systemPrompt:
			body["instructions"] = systemPrompt
		return body

	def chat(self, messages, systemPrompt=""):
		if not self.model:
			models = self.listModels()
			if not models:
				raise ProviderError("model", "no model available")
			self.model = models[0]
		raw = self._authed("POST", "/responses", self.buildBody(messages, systemPrompt), stream=True)
		return parseStream(raw)

	def listModels(self):
		data = self._authed("GET", "/models")
		out = []
		items = data.get("models") if isinstance(data, dict) else None
		if isinstance(items, list):
			for m in items:
				if isinstance(m, dict) and m.get("visibility", "list") == "list" and m.get("slug"):
					out.append(m["slug"])
		elif isinstance(data, dict):
			out = [m.get("id") for m in data.get("data", []) if isinstance(m, dict) and m.get("id")]
		seen = set()
		return [m for m in out if not (m in seen or seen.add(m))]

	def testConnection(self):
		models = self.listModels()
		return models, (not self.model or not models or self.model in models)


def _streamError(err, fallbackKind="server"):
	err = err if isinstance(err, dict) else {}
	code = err.get("code") or ""
	detail = err.get("param") if code == "subscription_sharing_unsupported_capability" else None
	detail = str(detail or err.get("message") or code or "error")[:300]
	kind = PLAN_ERRORS.get(code, fallbackKind)
	e = ProviderError(kind, detail)
	e.code = code
	return e


def parseStream(raw):
	"""Reads the server-sent events of the Responses API. The answer only counts
	as successful after ``response.completed``."""
	text = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else raw
	deltas = []
	doneTexts = []
	refusal = []
	completed = None
	for block in text.replace("\r\n", "\n").split("\n\n"):
		dataLines = [line[5:].lstrip() for line in block.split("\n") if line.startswith("data:")]
		if not dataLines:
			continue
		data = "\n".join(dataLines)
		if data.strip() == "[DONE]":
			continue
		try:
			event = json.loads(data)
		except ValueError:
			continue
		if not isinstance(event, dict):
			continue
		kind = event.get("type", "")
		if kind == "response.output_text.delta":
			deltas.append(str(event.get("delta", "")))
		elif kind == "response.output_text.done":
			doneTexts.append(str(event.get("text", "")))
		elif kind in ("response.refusal.delta",):
			refusal.append(str(event.get("delta", "")))
		elif kind == "response.completed":
			completed = event.get("response") or {}
		elif kind == "response.failed":
			raise _streamError((event.get("response") or {}).get("error"))
		elif kind == "error":
			raise _streamError(event.get("error") if isinstance(event.get("error"), dict) else event)
		elif kind == "response.incomplete":
			reason = ((event.get("response") or {}).get("incomplete_details") or {}).get("reason", "")
			raise ProviderError("server", "incomplete answer (%s)" % reason if reason else "incomplete answer")
	if completed is None:
		raise ProviderError("server", "the answer ended before response.completed")
	answer = "".join(deltas) or "".join(doneTexts) or _outputText(completed)
	if not answer.strip():
		if refusal:
			raise ProviderError("blocked", "".join(refusal)[:300])
		raise ProviderError("server", "empty answer")
	return answer.strip()


def _outputText(response):
	parts = []
	for item in (response or {}).get("output") or []:
		if isinstance(item, dict) and item.get("type") == "message":
			for c in item.get("content") or []:
				if isinstance(c, dict) and c.get("type") == "output_text":
					parts.append(c.get("text", ""))
	return "".join(parts)
