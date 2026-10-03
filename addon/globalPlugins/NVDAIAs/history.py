# -*- coding: UTF-8 -*-
# NVDAIAs - history.py
# Saved conversations ("previous conversations"), encrypted on disk.
# Copyright (C) 2026 Wellington Cruz
# This file is covered by the GNU General Public License, version 2.
#
# Each conversation is a JSON document encrypted with the same codec as the
# tokens (Windows DPAPI: only the current Windows user on this computer can read
# it) and saved as <id>.nvdaias in the NVDAIAs-history folder of the NVDA
# configuration folder.

import base64
import json
import os
import re

from .credentials import _defaultCodec

FOLDER_NAME = "NVDAIAs-history"
EXTENSION = ".nvdaias"
_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,80}$")


class HistoryStore:
	def __init__(self, configPath, codec=None, maxConversations=100):
		self.folder = os.path.join(configPath, FOLDER_NAME)
		self._codec = codec or _defaultCodec()
		self.maxConversations = maxConversations
		self._cache = {}  # id -> (mtime, data)

	def _path(self, convId):
		if not _ID_RE.match(convId or ""):
			raise ValueError("invalid conversation id")
		return os.path.join(self.folder, convId + EXTENSION)

	# Reading ---------------------------------------------------------------------

	def _read(self, path):
		with open(path, "rb") as f:
			raw = base64.b64decode(f.read())
		return json.loads(self._codec.unprotect(raw).decode("utf-8"))

	def _all(self):
		if not os.path.isdir(self.folder):
			return {}
		result = {}
		for name in os.listdir(self.folder):
			if not name.endswith(EXTENSION):
				continue
			convId = name[: -len(EXTENSION)]
			path = os.path.join(self.folder, name)
			try:
				mtime = os.path.getmtime(path)
				cached = self._cache.get(convId)
				if cached and cached[0] == mtime:
					data = cached[1]
				else:
					data = self._read(path)
					self._cache[convId] = (mtime, data)
			except Exception:
				# Damaged, or encrypted by another Windows user: ignore it.
				continue
			if data.get("entries"):
				result[convId] = data
		return result

	def list(self, excludeId=None):
		"""Saved conversations, most recent first."""
		items = [d for i, d in self._all().items() if i != excludeId]
		items.sort(key=lambda d: d.get("updated") or d.get("created") or 0, reverse=True)
		return items

	def load(self, convId):
		data = self._all().get(convId)
		if data is None:
			raise KeyError(convId)
		return data

	# Writing ---------------------------------------------------------------------

	def save(self, data):
		"""Saves (or replaces) one conversation. Empty conversations are not saved."""
		if not data.get("entries"):
			return False
		if not os.path.isdir(self.folder):
			os.makedirs(self.folder)
		path = self._path(data["id"])
		payload = base64.b64encode(self._codec.protect(json.dumps(data, ensure_ascii=False).encode("utf-8")))
		tmp = path + ".tmp"
		with open(tmp, "wb") as f:
			f.write(payload)
		os.replace(tmp, path)
		self._cache.pop(data["id"], None)
		self.prune()
		return True

	def delete(self, convId):
		self._cache.pop(convId, None)
		try:
			os.remove(self._path(convId))
		except OSError:
			pass

	def deleteAll(self):
		if not os.path.isdir(self.folder):
			return
		for name in os.listdir(self.folder):
			if name.endswith(EXTENSION) or name.endswith(".tmp"):
				try:
					os.remove(os.path.join(self.folder, name))
				except OSError:
					pass
		self._cache.clear()

	def prune(self):
		items = self.list()
		for data in items[self.maxConversations:]:
			self.delete(data["id"])


def summary(data, maxTitle=80):
	"""(title, providers, count, updated) of a saved conversation."""
	entries = data.get("entries") or []
	firstQuestion = next((e.get("text", "") for e in entries if e.get("role") == "user"), "")
	title = " ".join(firstQuestion.split())
	if len(title) > maxTitle:
		title = title[: maxTitle - 1].rstrip() + "…"
	providers = []
	for e in entries:
		name = e.get("provider")
		if name and name not in providers:
			providers.append(name)
	return title, providers, len(entries), data.get("updated") or data.get("created") or 0
