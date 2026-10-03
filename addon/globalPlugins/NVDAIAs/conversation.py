# -*- coding: UTF-8 -*-
# NVDAIAs - conversation.py
# Conversation model, independent of the user interface.
# Copyright (C) 2026 Wellington Cruz
# This file is covered by the GNU General Public License, version 2.

import base64
import time
import uuid

from .attachments import Attachment
from .providers import Message


class ChatEntry:
	def __init__(self, role, text, providerName="", model="", image=None, imageMime="image/png", timestamp=None, attachments=None):
		self.role = role  # "user" or "assistant"
		self.text = text
		self.providerName = providerName
		self.model = model
		self.attachments = list(attachments or [])
		if image:
			self.attachments.insert(0, Attachment.image(image, mime=imageMime))
		self.timestamp = timestamp if timestamp is not None else time.time()

	@property
	def time(self):
		return time.localtime(self.timestamp)

	@property
	def image(self):
		"""Bytes of the first image attached (screenshots), or None."""
		for a in self.attachments:
			if a.kind == "image":
				return a.data
		return None

	def attachmentNames(self):
		return [a.name for a in self.attachments]

	def toDict(self):
		data = {"role": self.role, "text": self.text, "time": self.timestamp}
		if self.providerName:
			data["provider"] = self.providerName
		if self.model:
			data["model"] = self.model
		if self.attachments:
			data["attachments"] = [a.toDict() for a in self.attachments]
		return data

	@classmethod
	def fromDict(cls, data):
		attachments = [Attachment.fromDict(a) for a in data.get("attachments") or []]
		legacyImage = data.get("image")  # conversations saved by version 1.2.0
		if legacyImage:
			attachments.insert(0, Attachment.image(base64.b64decode(legacyImage), mime=data.get("imageMime", "image/png")))
		return cls(
			data["role"],
			data.get("text", ""),
			providerName=data.get("provider", ""),
			model=data.get("model", ""),
			timestamp=data.get("time"),
			attachments=attachments,
		)


def newConversationId():
	return time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:8]


class Conversation:
	def __init__(self):
		self.entries = []
		self.listeners = []
		self.id = newConversationId()
		self.created = time.time()

	def _notify(self):
		for listener in list(self.listeners):
			try:
				listener()
			except Exception:
				pass

	def add(self, entry):
		self.entries.append(entry)
		self._notify()
		return entry

	def remove(self, entry):
		if entry in self.entries:
			self.entries.remove(entry)
			self._notify()

	def clear(self):
		"""Starts a new, empty conversation (with a new id)."""
		self.entries = []
		self.id = newConversationId()
		self.created = time.time()
		self._notify()

	def load(self, data):
		"""Replaces the content with a saved conversation (keeps the listeners)."""
		self.entries = [ChatEntry.fromDict(e) for e in data.get("entries", [])]
		self.id = data.get("id") or newConversationId()
		self.created = data.get("created") or time.time()
		self._notify()

	def toDict(self):
		return {
			"id": self.id,
			"created": self.created,
			"updated": self.entries[-1].timestamp if self.entries else self.created,
			"entries": [e.toDict() for e in self.entries],
		}

	def __len__(self):
		return len(self.entries)

	def apiMessages(self):
		"""Messages to send to the API (the whole conversation, any provider)."""
		return [Message(e.role, e.text, attachments=e.attachments) for e in self.entries]

	def lastAnswer(self):
		for e in reversed(self.entries):
			if e.role == "assistant":
				return e
		return None

	def toText(self, userLabel, attachmentsLabel):
		"""Plain text export. attachmentsLabel is a format string with {names}."""
		parts = []
		for e in self.entries:
			who = userLabel if e.role == "user" else ("%s (%s)" % (e.providerName, e.model) if e.model else e.providerName)
			stamp = time.strftime("%Y-%m-%d %H:%M", e.time)
			body = e.text
			if e.attachments:
				body = "%s\n%s" % (attachmentsLabel.format(names=", ".join(e.attachmentNames())), body)
			parts.append("[%s] %s:\n%s" % (stamp, who, body))
		return "\n\n".join(parts) + "\n"
