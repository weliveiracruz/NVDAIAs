# -*- coding: UTF-8 -*-
# NVDAIAs - credentials.py
# Stores API tokens encrypted with the Windows Data Protection API (DPAPI).
# Copyright (C) 2026 Wellington Cruz
# This file is covered by the GNU General Public License, version 2.
#
# Tokens are never written to nvda.ini. They live in a separate JSON file in the
# NVDA user configuration folder and are encrypted for the current Windows user,
# so the file is useless if copied to another account or computer.

import base64
import json
import os
import sys
import threading

_ENTROPY = b"NVDAIAs-token-v1"
FILE_NAME = "NVDAIAs-credentials.json"


class _DPAPI:
	"""Minimal ctypes wrapper around CryptProtectData / CryptUnprotectData."""

	def __init__(self):
		import ctypes
		from ctypes import wintypes

		class DATA_BLOB(ctypes.Structure):
			_fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]

		self._ctypes = ctypes
		self._BLOB = DATA_BLOB
		crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
		kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
		P = ctypes.POINTER(DATA_BLOB)
		self._protect = crypt32.CryptProtectData
		self._protect.argtypes = [P, wintypes.LPCWSTR, P, ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, P]
		self._protect.restype = wintypes.BOOL
		self._unprotect = crypt32.CryptUnprotectData
		self._unprotect.argtypes = [P, ctypes.c_void_p, P, ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, P]
		self._unprotect.restype = wintypes.BOOL
		self._localFree = kernel32.LocalFree
		self._localFree.argtypes = [ctypes.c_void_p]
		self._localFree.restype = ctypes.c_void_p

	def _blob(self, data):
		ctypes = self._ctypes
		buf = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
		blob = self._BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_ubyte)))
		return blob, buf  # keep buf alive

	def _call(self, func, data, *extra):
		ctypes = self._ctypes
		inBlob, _keep1 = self._blob(data)
		entropy, _keep2 = self._blob(_ENTROPY)
		out = self._BLOB()
		CRYPTPROTECT_UI_FORBIDDEN = 0x1
		ok = func(ctypes.byref(inBlob), *extra, ctypes.byref(entropy), None, None, CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(out))
		if not ok:
			raise OSError(ctypes.get_last_error(), "DPAPI call failed")
		try:
			return ctypes.string_at(out.pbData, out.cbData)
		finally:
			self._localFree(ctypes.cast(out.pbData, ctypes.c_void_p))

	def protect(self, data):
		return self._call(self._protect, data, "NVDAIAs")

	def unprotect(self, data):
		return self._call(self._unprotect, data, None)


class _PlainCodec:
	"""Used only when not running on Windows (unit tests)."""

	def protect(self, data):
		return data

	def unprotect(self, data):
		return data


def _defaultCodec():
	if sys.platform == "win32":
		return _DPAPI()
	return _PlainCodec()


class CredentialStore:
	#: Writes come from the GUI and from background threads (ChatGPT sign-in and
	#: token refresh): one lock for every store of the process.
	_lock = threading.RLock()

	def __init__(self, folder, codec=None):
		self.path = os.path.join(folder, FILE_NAME)
		self._codec = codec or _defaultCodec()
		self._cache = None

	def _load(self):
		if self._cache is None:
			try:
				with open(self.path, "r", encoding="utf-8") as f:
					data = json.load(f)
				self._cache = data if isinstance(data, dict) else {}
			except (OSError, ValueError):
				self._cache = {}
		return self._cache

	def _save(self):
		folder = os.path.dirname(self.path)
		if folder and not os.path.isdir(folder):
			os.makedirs(folder)
		tmp = "%s.%d.%d.tmp" % (self.path, os.getpid(), threading.get_ident())
		with open(tmp, "w", encoding="utf-8") as f:
			json.dump(self._cache, f, indent=1)
		os.replace(tmp, self.path)

	def get(self, providerId):
		with self._lock:
			enc = self._load().get(providerId)
		if not enc:
			return ""
		try:
			return self._codec.unprotect(base64.b64decode(enc)).decode("utf-8")
		except Exception:
			# Encrypted by another Windows user / computer, or damaged.
			return ""

	def has(self, providerId):
		return bool(self.get(providerId))

	def set(self, providerId, token):
		token = (token or "").strip()
		with self._lock:
			data = self._load()
			if token:
				data[providerId] = base64.b64encode(self._codec.protect(token.encode("utf-8"))).decode("ascii")
			else:
				data.pop(providerId, None)
			self._save()

	def remove(self, providerId):
		self.set(providerId, "")

	def removeAll(self):
		with self._lock:
			self._cache = {}
			try:
				os.remove(self.path)
			except OSError:
				pass


def maskToken(token):
	"""Returns a short, safe hint such as '…a1b2' to tell the user which key is saved."""
	token = token or ""
	if len(token) <= 8:
		return "…"
	return "…" + token[-4:]
