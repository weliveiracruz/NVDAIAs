# -*- coding: UTF-8 -*-
# NVDAIAs - conversation.py
# Conversation model, independent of the user interface.
# Copyright (C) 2026 Wellington Cruz
# This file is covered by the GNU General Public License, version 2.

import time

from .providers import Message


class ChatEntry:
	def __init__(self, role, text, providerName="", model="", image=None, imageMime="image/png"):
		self.role = role  # "user" or "assistant"
		self.text = text
		self.providerName = providerName
		self.model = model
		self.image = image
		self.imageMime = imageMime
		self.time = time.localtime()


class Conversation:
	def __init__(self):
		self.entries = []
		self.listeners = []

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
		self.entries = []
		self._notify()

	def __len__(self):
		return len(self.entries)

	def apiMessages(self):
		"""Messages to send to the API (the whole conversation, any provider)."""
		return [Message(e.role, e.text, e.image, e.imageMime) for e in self.entries]

	def lastAnswer(self):
		for e in reversed(self.entries):
			if e.role == "assistant":
				return e
		return None

	def toText(self, userLabel, imageLabel):
		parts = []
		for e in self.entries:
			who = userLabel if e.role == "user" else ("%s (%s)" % (e.providerName, e.model) if e.model else e.providerName)
			stamp = time.strftime("%Y-%m-%d %H:%M", e.time)
			body = e.text
			if e.image:
				body = "%s\n%s" % (imageLabel, body)
			parts.append("[%s] %s:\n%s" % (stamp, who, body))
		return "\n\n".join(parts) + "\n"
