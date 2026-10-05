# -*- coding: UTF-8 -*-
# NVDAIAs - providers.py
# Clients for the ChatGPT (OpenAI), Gemini (Google) and Claude (Anthropic) APIs.
# Copyright (C) 2026 Wellington Cruz
# This file is covered by the GNU General Public License, version 2.
#
# This module deliberately depends only on the Python standard library, so it
# works inside NVDA (no extra packages) and can be unit tested outside NVDA.

import json
import ssl
import socket
import urllib.error
import urllib.parse
import urllib.request

from .attachments import Attachment

USER_AGENT = "NVDAIAs-NVDA-addon/1.0"


class ProviderError(Exception):
	"""Error raised by a provider. ``kind`` lets the user interface choose a friendly message.

	kind is one of: "auth", "quota", "network", "timeout", "model", "blocked", "server",
	"attachment" (the AI cannot read an attached file; detail is the file name), "other".
	"""

	def __init__(self, kind, detail="", status=None):
		super().__init__(detail or kind)
		self.kind = kind
		self.detail = detail
		self.status = status


class Message:
	"""One message of a conversation as sent to an API."""

	def __init__(self, role, text, image=None, imageMime="image/png", attachments=None):
		# role: "user" or "assistant"
		self.role = role
		self.text = text
		self.attachments = list(attachments or [])
		if image:
			self.attachments.insert(0, Attachment.image(image, mime=imageMime))


def _extractErrorMessage(data):
	"""Gets a human readable message out of the error bodies used by the three APIs."""
	if isinstance(data, dict):
		err = data.get("error")
		if isinstance(err, dict):
			return str(err.get("message") or err.get("type") or err)
		if isinstance(err, str):
			return err
		if "message" in data:
			return str(data["message"])
	return ""


class BaseProvider:
	id = ""
	name = ""
	#: Page where the user creates an API key (token).
	tokenUrl = ""
	defaultBaseUrl = ""
	defaultModel = ""
	suggestedModels = ()

	def __init__(self, apiKey, model=None, timeout=120, maxTokens=4096, baseUrl=None, opener=None):
		self.apiKey = (apiKey or "").strip()
		self.model = (model or self.defaultModel).strip()
		self.timeout = timeout
		self.maxTokens = maxTokens
		self.baseUrl = (baseUrl or self.defaultBaseUrl).rstrip("/")
		# ``opener`` allows tests to inject a fake transport.
		self._opener = opener

	# Transport -------------------------------------------------------------

	def _headers(self):
		raise NotImplementedError

	def _request(self, method, path, body=None, query=None):
		raw = self._requestRaw(method, path, body, query)
		try:
			return json.loads(raw.decode("utf-8"))
		except Exception:
			raise ProviderError("server", "invalid JSON response")

	def _requestRaw(self, method, path, body=None, query=None, accept="application/json"):
		"""Sends the request and returns the raw answer (bytes)."""
		if not self.apiKey:
			raise ProviderError("auth", "missing token")
		url = self.baseUrl + path
		if query:
			url += "?" + urllib.parse.urlencode(query)
		headers = {"User-Agent": USER_AGENT, "Accept": accept}
		headers.update(self._headers())
		data = None
		if body is not None:
			data = json.dumps(body).encode("utf-8")
			headers["Content-Type"] = "application/json"
		req = urllib.request.Request(url, data=data, headers=headers, method=method)
		try:
			raw = self._open(req)
		except urllib.error.HTTPError as e:
			try:
				payload = json.loads(e.read().decode("utf-8", "replace"))
			except Exception:
				payload = None
			raise self._httpError(e.code, payload)
		except (socket.timeout, TimeoutError):
			raise ProviderError("timeout", "timeout")
		except urllib.error.URLError as e:
			reason = getattr(e, "reason", e)
			if isinstance(reason, (socket.timeout, TimeoutError)):
				raise ProviderError("timeout", str(reason))
			raise ProviderError("network", str(reason))
		except (ConnectionError, OSError) as e:
			raise ProviderError("network", str(e))
		return raw

	def _open(self, req):
		if self._opener is not None:
			return self._opener(req, self.timeout)
		return _urlopen(req, self.timeout)

	def _httpError(self, status, payload):
		detail = _extractErrorMessage(payload) or "HTTP %d" % status
		low = detail.lower()
		if status in (401, 403) or "api key" in low or "api_key" in low or "authentication" in low:
			kind = "auth"
		elif status == 429 or "quota" in low or "rate limit" in low or "credit" in low or "billing" in low:
			kind = "quota"
		elif status == 404 or "model" in low and ("not found" in low or "does not exist" in low or "not supported" in low):
			kind = "model"
		elif status >= 500 or 300 <= status < 400:
			kind = "server"
		else:
			kind = "other"
		return ProviderError(kind, detail, status)

	# Public API ------------------------------------------------------------

	def chat(self, messages, systemPrompt=""):
		"""Sends the conversation and returns the answer text."""
		raise NotImplementedError

	def listModels(self):
		"""Returns the list of model ids available for this key."""
		raise NotImplementedError

	def testConnection(self):
		"""Checks the key without spending tokens (lists the models).

		Returns (models, modelFound).
		"""
		models = self.listModels()
		found = not models or self.model in models
		return models, found


_sslContext = None


def _getSslContext():
	"""SSL context trusting the Windows certificate store and, when available, the
	Mozilla bundle shipped with NVDA (certifi). Windows downloads some root
	certificates only on demand, so the certifi bundle avoids spurious
	"certificate verify failed" errors on freshly installed systems."""
	global _sslContext
	if _sslContext is None:
		context = ssl.create_default_context()
		try:
			import certifi
			context.load_verify_locations(cafile=certifi.where())
		except Exception:
			pass
		_sslContext = context
	return _sslContext


#: Biggest answer accepted from an API (protects NVDA's memory).
MAX_RESPONSE_BYTES = 32 * 1024 * 1024
_LOCAL_HOSTS = ("127.0.0.1", "localhost", "::1")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
	"""The APIs never redirect. Following a redirect would send the API key
	(Authorization / x-api-key headers) to another address, so it is refused."""

	def redirect_request(self, req, fp, code, msg, headers, newurl):
		return None


_opener = None


def _getOpener():
	global _opener
	if _opener is None:
		_opener = urllib.request.build_opener(
			urllib.request.HTTPSHandler(context=_getSslContext()),
			_NoRedirect(),
		)
	return _opener


def _checkUrl(url):
	"""Only HTTPS is allowed (plain HTTP only to this computer, used by the tests)."""
	parts = urllib.parse.urlsplit(url)
	if parts.scheme == "https" or (parts.scheme == "http" and parts.hostname in _LOCAL_HOSTS):
		return
	raise ProviderError("network", "refused address: %s://%s" % (parts.scheme, parts.hostname or ""))


def _urlopen(req, timeout):
	_checkUrl(req.full_url)
	# The scheme was checked above: only https (or http to this computer).
	with _getOpener().open(req, timeout=timeout) as resp:  # nosec B310
		data = resp.read(MAX_RESPONSE_BYTES + 1)
	if len(data) > MAX_RESPONSE_BYTES:
		raise ProviderError("server", "answer too large")
	return data


# ---------------------------------------------------------------------------
# ChatGPT / OpenAI
# ---------------------------------------------------------------------------

class OpenAIProvider(BaseProvider):
	id = "openai"
	name = "ChatGPT"
	tokenUrl = "https://platform.openai.com/api-keys"
	defaultBaseUrl = "https://api.openai.com/v1"
	defaultModel = "gpt-5-mini"
	suggestedModels = ("gpt-5-mini", "gpt-5", "gpt-5-nano", "gpt-4.1-mini", "gpt-4o-mini")

	def _headers(self):
		return {"Authorization": "Bearer " + self.apiKey}

	def buildBody(self, messages, systemPrompt=""):
		out = []
		if systemPrompt:
			out.append({"role": "system", "content": systemPrompt})
		for m in messages:
			if m.attachments:
				content = []
				for a in m.attachments:
					if a.kind == "image":
						content.append({"type": "image_url", "image_url": {"url": a.dataUrl()}})
					elif a.kind == "pdf":
						content.append({"type": "file", "file": {"filename": a.name, "file_data": a.dataUrl()}})
					elif a.kind == "text":
						content.append({"type": "text", "text": a.asPromptText()})
					else:
						raise ProviderError("attachment", a.name)
				content.append({"type": "text", "text": m.text})
			else:
				content = m.text
			out.append({"role": m.role, "content": content})
		# temperature and max tokens are intentionally not sent: recent reasoning models reject them.
		return {"model": self.model, "messages": out}

	def chat(self, messages, systemPrompt=""):
		data = self._request("POST", "/chat/completions", self.buildBody(messages, systemPrompt))
		try:
			choice = data["choices"][0]
			msg = choice["message"]
		except (KeyError, IndexError, TypeError):
			raise ProviderError("server", _extractErrorMessage(data) or "unexpected response")
		text = msg.get("content")
		if isinstance(text, list):
			text = "".join(p.get("text", "") for p in text if isinstance(p, dict))
		if not text:
			refusal = msg.get("refusal")
			if refusal:
				raise ProviderError("blocked", refusal)
			raise ProviderError("server", "empty answer (finish_reason: %s)" % choice.get("finish_reason"))
		return text.strip()

	def listModels(self):
		data = self._request("GET", "/models")
		ids = [m.get("id", "") for m in data.get("data", []) if isinstance(m, dict)]
		chatLike = [
			i for i in ids
			if (i.startswith("gpt-") or i.startswith("chatgpt-") or i[:2] in ("o1", "o3", "o4"))
			and not any(x in i for x in ("audio", "realtime", "transcribe", "tts", "image", "search", "embedding"))
		]
		return sorted(chatLike or ids)


# ---------------------------------------------------------------------------
# Gemini / Google
# ---------------------------------------------------------------------------

class GeminiProvider(BaseProvider):
	id = "gemini"
	name = "Gemini"
	tokenUrl = "https://aistudio.google.com/app/apikey"
	defaultBaseUrl = "https://generativelanguage.googleapis.com/v1beta"
	defaultModel = "gemini-2.5-flash"
	suggestedModels = ("gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.5-pro", "gemini-3-flash-preview")

	def _headers(self):
		return {"x-goog-api-key": self.apiKey}

	def buildBody(self, messages, systemPrompt=""):
		contents = []
		for m in messages:
			parts = []
			for a in m.attachments:
				if a.kind == "text":
					parts.append({"text": a.asPromptText()})
				else:
					parts.append({"inline_data": {"mime_type": a.mime, "data": a.base64()}})
			parts.append({"text": m.text})
			contents.append({"role": "model" if m.role == "assistant" else "user", "parts": parts})
		body = {"contents": contents}
		if systemPrompt:
			body["systemInstruction"] = {"parts": [{"text": systemPrompt}]}
		return body

	def chat(self, messages, systemPrompt=""):
		model = self.model[7:] if self.model.startswith("models/") else self.model
		path = "/models/%s:generateContent" % urllib.parse.quote(model, safe="-._")
		data = self._request("POST", path, self.buildBody(messages, systemPrompt))
		candidates = data.get("candidates") or []
		if not candidates:
			feedback = data.get("promptFeedback") or {}
			raise ProviderError("blocked", feedback.get("blockReason") or "no answer")
		cand = candidates[0]
		parts = (cand.get("content") or {}).get("parts") or []
		text = "".join(p.get("text", "") for p in parts if isinstance(p, dict) and not p.get("thought"))
		if not text.strip():
			reason = cand.get("finishReason", "")
			raise ProviderError("blocked" if reason in ("SAFETY", "RECITATION", "PROHIBITED_CONTENT", "BLOCKLIST") else "server", "finishReason: %s" % reason)
		return text.strip()

	def listModels(self):
		models = []
		token = None
		for _page in range(10):
			query = {"pageSize": 1000}
			if token:
				query["pageToken"] = token
			data = self._request("GET", "/models", query=query)
			for m in data.get("models", []):
				if "generateContent" in (m.get("supportedGenerationMethods") or []):
					name = m.get("name", "")
					models.append(name[7:] if name.startswith("models/") else name)
			token = data.get("nextPageToken")
			if not token:
				break
		return sorted(set(models))

	def _httpError(self, status, payload):
		err = super()._httpError(status, payload)
		# Gemini answers an invalid key with HTTP 400 + API_KEY_INVALID.
		if status == 400 and "API_KEY_INVALID" in json.dumps(payload or {}):
			err.kind = "auth"
		return err


# ---------------------------------------------------------------------------
# Claude / Anthropic
# ---------------------------------------------------------------------------

class AnthropicProvider(BaseProvider):
	id = "anthropic"
	name = "Claude"
	tokenUrl = "https://console.anthropic.com/settings/keys"
	defaultBaseUrl = "https://api.anthropic.com/v1"
	defaultModel = "claude-sonnet-5-5"
	suggestedModels = ("claude-sonnet-5-5", "claude-opus-5-5", "claude-haiku-4-5-20251001")
	apiVersion = "2023-06-01"

	def _headers(self):
		return {"x-api-key": self.apiKey, "anthropic-version": self.apiVersion}

	def buildBody(self, messages, systemPrompt=""):
		out = []
		for m in messages:
			content = []
			for a in m.attachments:
				if a.kind == "image":
					content.append({"type": "image", "source": {"type": "base64", "media_type": a.mime, "data": a.base64()}})
				elif a.kind == "pdf":
					content.append({"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": a.base64()}, "title": a.name})
				elif a.kind == "text":
					content.append({"type": "text", "text": a.asPromptText()})
				else:
					raise ProviderError("attachment", a.name)
			content.append({"type": "text", "text": m.text})
			# The Messages API requires alternating roles: merge consecutive messages of the same role.
			if out and out[-1]["role"] == m.role:
				out[-1]["content"].extend(content)
			else:
				out.append({"role": m.role, "content": content})
		body = {"model": self.model, "max_tokens": int(self.maxTokens), "messages": out}
		if systemPrompt:
			body["system"] = systemPrompt
		return body

	def chat(self, messages, systemPrompt=""):
		data = self._request("POST", "/messages", self.buildBody(messages, systemPrompt))
		blocks = data.get("content") or []
		text = "".join(b.get("text", "") for b in blocks if isinstance(b, dict) and b.get("type") == "text")
		if not text.strip():
			raise ProviderError("blocked" if data.get("stop_reason") == "refusal" else "server", "stop_reason: %s" % data.get("stop_reason"))
		if data.get("stop_reason") == "max_tokens":
			text += "\n\n[…]"
		return text.strip()

	def listModels(self):
		models = []
		after = None
		for _page in range(10):
			query = {"limit": 1000}
			if after:
				query["after_id"] = after
			data = self._request("GET", "/models", query=query)
			models.extend(m.get("id", "") for m in data.get("data", []) if isinstance(m, dict))
			if not data.get("has_more"):
				break
			after = data.get("last_id")
		return sorted(set(models))

	def _httpError(self, status, payload):
		err = super()._httpError(status, payload)
		errType = ""
		if isinstance(payload, dict) and isinstance(payload.get("error"), dict):
			errType = payload["error"].get("type", "")
		if errType in ("authentication_error", "permission_error"):
			err.kind = "auth"
		elif errType == "rate_limit_error":
			err.kind = "quota"
		elif errType == "overloaded_error" or status == 529:
			err.kind = "server"
		elif errType == "not_found_error":
			err.kind = "model"
		return err


PROVIDERS = (OpenAIProvider, GeminiProvider, AnthropicProvider)
PROVIDER_IDS = tuple(p.id for p in PROVIDERS)


def getProviderClass(providerId):
	for p in PROVIDERS:
		if p.id == providerId:
			return p
	raise KeyError(providerId)
