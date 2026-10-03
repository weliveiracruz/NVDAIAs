# -*- coding: UTF-8 -*-
# NVDAIAs - core.py
# Configuration, credentials and the chat session shared by all windows.
# Copyright (C) 2026 Wellington Cruz
# This file is covered by the GNU General Public License, version 2.

import re
import threading

import addonHandler
import config
import globalVars
import tones
import ui
import wx
from logHandler import log

from .conversation import ChatEntry, Conversation
from .credentials import CredentialStore
from .providers import PROVIDERS, PROVIDER_IDS, ProviderError, getProviderClass
from . import textutils

addonHandler.initTranslation()

CONFIG_SECTION = "NVDAIAs"

confspec = {
	"provider": 'option("openai", "gemini", "anthropic", default="openai")',
	"model_openai": 'string(default="")',
	"model_gemini": 'string(default="")',
	"model_anthropic": 'string(default="")',
	# Newlines are stored escaped (see getSystemPrompt / setSystemPrompt).
	"systemPrompt": 'string(default="")',
	"speakResponses": "boolean(default=True)",
	"waitingBeeps": "boolean(default=True)",
	"stripMarkdown": "boolean(default=True)",
	"maxTokens": "integer(default=4096, min=256, max=64000)",
	"timeout": "integer(default=120, min=10, max=600)",
	"visualTheme": "boolean(default=True)",
	"largeText": "boolean(default=False)",
}


def initConfig():
	config.conf.spec[CONFIG_SECTION] = confspec


def conf():
	return config.conf[CONFIG_SECTION]


def providerLabel(providerId):
	labels = {
		# Translators: name of the OpenAI provider, shown in combo boxes.
		"openai": _("ChatGPT (OpenAI)"),
		# Translators: name of the Google provider, shown in combo boxes.
		"gemini": _("Gemini (Google)"),
		# Translators: name of the Anthropic provider, shown in combo boxes.
		"anthropic": _("Claude (Anthropic)"),
	}
	return labels.get(providerId, providerId)


def defaultSystemPrompt():
	# Translators: default instructions sent to the AI with every question.
	return _(
		"You are a helpful assistant. The user is blind and reads your answers with the NVDA screen reader. "
		"Always answer in the same language as the user's question. Be clear and direct, prefer short "
		"paragraphs and simple lists, and avoid tables, emojis and decorative symbols."
	)


def getSystemPrompt(effective=True):
	raw = conf()["systemPrompt"]
	text = re.sub(r"\\(.)", lambda m: "\n" if m.group(1) == "n" else m.group(1), raw) if raw else ""
	if effective and not text.strip():
		return defaultSystemPrompt()
	return text


def setSystemPrompt(text):
	text = (text or "").strip()
	conf()["systemPrompt"] = text.replace("\\", "\\\\").replace("\r\n", "\n").replace("\n", "\\n")


def getModel(providerId):
	return conf()["model_" + providerId].strip() or getProviderClass(providerId).defaultModel


def setModel(providerId, model):
	model = (model or "").strip()
	cls = getProviderClass(providerId)
	conf()["model_" + providerId] = "" if model == cls.defaultModel else model


#: Models listed by each provider during this NVDA session (filled by "Update models").
modelCache = {}

_store = None


def store():
	global _store
	if _store is None:
		_store = CredentialStore(globalVars.appArgs.configPath)
	return _store


def makeProvider(providerId, token=None, model=None):
	cls = getProviderClass(providerId)
	c = conf()
	return cls(
		token if token is not None else store().get(providerId),
		model=model or getModel(providerId),
		timeout=c["timeout"],
		maxTokens=c["maxTokens"],
	)


def connectedProviders():
	return [p for p in PROVIDER_IDS if store().has(p)]


def errorMessage(err, providerName):
	"""Friendly, translated message for a ProviderError."""
	kind = getattr(err, "kind", "other")
	detail = getattr(err, "detail", "") or str(err)
	if kind == "auth":
		# Translators: error when the API token is invalid. {name} is ChatGPT, Gemini or Claude.
		msg = _("{name} did not accept the token. Check the token in NVDAIAs settings or generate a new one.")
	elif kind == "quota":
		# Translators: error when the account has no credit or hit the rate limit.
		msg = _("{name}: usage limit reached or no credit available in the account. Wait a little or check the billing of your account.")
	elif kind == "network":
		# Translators: error when there is no internet connection.
		msg = _("Could not connect to {name}. Check your internet connection.")
	elif kind == "timeout":
		# Translators: error when the AI takes too long to answer.
		msg = _("{name} took too long to answer. Try again or increase the time limit in the settings.")
	elif kind == "model":
		# Translators: error when the selected model does not exist.
		msg = _("{name}: the selected model is not available for your account. Choose another model.")
	elif kind == "blocked":
		# Translators: error when the AI refused or blocked the answer.
		msg = _("{name} did not answer this question (blocked by the provider).")
	elif kind == "server":
		# Translators: error when the provider has a temporary problem.
		msg = _("{name} had a temporary problem. Try again in a few moments.")
	else:
		# Translators: generic error from the AI provider.
		msg = _("{name} returned an error.")
	msg = msg.format(name=providerName)
	if detail and kind not in ("network", "timeout"):
		# Translators: technical details appended to an error message.
		msg += " " + _("Details: {detail}").format(detail=detail[:300])
	elif detail and kind == "network":
		msg += " (%s)" % detail[:200]
	return msg


def runInBackground(work, onSuccess, onError):
	"""Runs ``work`` in a thread and calls back on the GUI thread."""

	def run():
		try:
			result = work()
		except ProviderError as e:
			wx.CallAfter(onError, e)
		except Exception as e:  # unexpected
			log.error("NVDAIAs: unexpected error", exc_info=True)
			wx.CallAfter(onError, ProviderError("other", str(e)))
		else:
			wx.CallAfter(onSuccess, result)

	t = threading.Thread(target=run, name="NVDAIAs-request", daemon=True)
	t.start()
	return t


class _BeepTimer(wx.Timer):
	def Notify(self):
		tones.beep(500, 40)


class NoTokenError(Exception):
	pass


class ChatSession:
	"""Holds the conversation (kept while NVDA runs) and sends questions."""

	def __init__(self):
		self.conversation = Conversation()
		self.busy = False
		self._requestId = 0
		self._pendingEntry = None
		self._beepTimer = None
		#: Callbacks: onBusyChanged(busy), onAnswer(entry), onError(message, questionText)
		self.listeners = []

	def _emit(self, name, *args):
		for listener in list(self.listeners):
			func = getattr(listener, name, None)
			if func:
				try:
					func(*args)
				except RuntimeError:
					# wx window already destroyed
					pass
				except Exception:
					log.error("NVDAIAs: listener error", exc_info=True)

	def _setBusy(self, busy):
		self.busy = busy
		if busy and conf()["waitingBeeps"]:
			if self._beepTimer is None:
				self._beepTimer = _BeepTimer()
			self._beepTimer.Start(1500)
		elif self._beepTimer is not None:
			self._beepTimer.Stop()
		self._emit("onBusyChanged", busy)

	def send(self, text, image=None, imageMime="image/png", providerId=None):
		"""Sends a question. Raises NoTokenError when the provider is not connected."""
		text = (text or "").strip()
		if not text or self.busy:
			return False
		providerId = providerId or conf()["provider"]
		token = store().get(providerId)
		if not token:
			raise NoTokenError(providerId)
		provider = makeProvider(providerId, token)
		systemPrompt = getSystemPrompt()
		entry = self.conversation.add(ChatEntry("user", text, image=image, imageMime=imageMime))
		messages = self.conversation.apiMessages()
		self._pendingEntry = entry
		self._requestId += 1
		requestId = self._requestId
		providerName = provider.name
		model = provider.model
		self._setBusy(True)

		def ok(answer):
			if requestId != self._requestId:
				return  # cancelled
			self._pendingEntry = None
			self._setBusy(False)
			answerEntry = self.conversation.add(ChatEntry("assistant", answer, providerName=providerName, model=model))
			tones.beep(880, 60)
			if conf()["speakResponses"]:
				ui.message(self.speechText(answer))
			self._emit("onAnswer", answerEntry)

		def fail(err):
			if requestId != self._requestId:
				return
			self._pendingEntry = None
			self._setBusy(False)
			self.conversation.remove(entry)
			message = errorMessage(err, providerName)
			log.debugWarning("NVDAIAs: %s error: %s" % (providerName, getattr(err, "detail", err)))
			tones.beep(220, 120)
			ui.message(message)
			self._emit("onError", message, text)

		runInBackground(lambda: provider.chat(messages, systemPrompt), ok, fail)
		return True

	def cancel(self):
		"""Cancels the pending question. Returns its text."""
		if not self.busy:
			return None
		self._requestId += 1
		entry = self._pendingEntry
		self._pendingEntry = None
		if entry is not None:
			self.conversation.remove(entry)
		self._setBusy(False)
		return entry.text if entry else None

	def newConversation(self):
		self.cancel()
		self.conversation.clear()

	@staticmethod
	def speechText(text):
		return textutils.toPlainText(text) if conf()["stripMarkdown"] else text

	def terminate(self):
		self._requestId += 1
		if self._beepTimer is not None:
			self._beepTimer.Stop()
			self._beepTimer = None
		self.listeners = []


__all__ = [
	"PROVIDERS", "PROVIDER_IDS", "ProviderError", "ChatSession", "NoTokenError",
	"initConfig", "conf", "store", "makeProvider", "providerLabel", "errorMessage",
]
