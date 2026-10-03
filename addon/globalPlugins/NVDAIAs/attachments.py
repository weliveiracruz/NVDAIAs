# -*- coding: UTF-8 -*-
# NVDAIAs - attachments.py
# Turns any file chosen by the user into something the AIs can read.
# Copyright (C) 2026 Wellington Cruz
# This file is covered by the GNU General Public License, version 2.
#
# Kinds of attachment:
#   image - sent as an image to the three AIs (formats they do not accept are converted to PNG)
#   pdf   - sent as a document to the three AIs
#   media - audio or video, only Gemini accepts it
#   text  - text extracted on this computer (plain text, code, CSV, HTML, Word,
#           Excel, PowerPoint, OpenDocument, EPUB, RTF...), works with the three AIs
# Only the Python standard library is used (plus wx, when available, to convert
# unusual image formats), so nothing needs to be installed.

import base64
import mimetypes
import os
import re
import zipfile
from html.parser import HTMLParser
from xml.etree import ElementTree

#: Files bigger than this are refused (the APIs reject big inline uploads).
MAX_FILE_BYTES = 20 * 1024 * 1024
#: Extracted text is cut after this many characters.
MAX_TEXT_CHARS = 300000
#: Documents inside zip files (Office, OpenDocument, EPUB) may not expand to more than this
#: (protection against "zip bombs" that would fill NVDA's memory).
MAX_UNZIPPED_BYTES = 40 * 1024 * 1024
#: Expansion ratio above which a big member of a zip file is considered a bomb.
MAX_COMPRESSION_RATIO = 200

NATIVE_IMAGE_TYPES = {"image/png", "image/jpeg", "image/gif", "image/webp"}
CONVERTIBLE_IMAGE_EXT = {".bmp", ".tif", ".tiff", ".ico", ".pcx", ".tga", ".pnm", ".ppm", ".pgm", ".xpm", ".cur", ".iff"}
MEDIA_TYPES = {
	".mp3": "audio/mp3", ".wav": "audio/wav", ".ogg": "audio/ogg", ".oga": "audio/ogg", ".opus": "audio/ogg",
	".flac": "audio/flac", ".aac": "audio/aac", ".m4a": "audio/aac", ".aiff": "audio/aiff", ".aif": "audio/aiff",
	".mp4": "video/mp4", ".m4v": "video/mp4", ".mpeg": "video/mpeg", ".mpg": "video/mpeg", ".mov": "video/mov",
	".avi": "video/avi", ".wmv": "video/wmv", ".flv": "video/x-flv", ".webm": "video/webm", ".3gp": "video/3gpp",
	".mkv": "video/webm",
}
OFFICE_LEGACY = {".doc", ".xls", ".ppt", ".pps", ".wps", ".xlsb"}


class AttachmentError(Exception):
	"""reason: "empty", "tooBig", "unreadable", "legacyOffice", "binary", "suspicious"."""

	def __init__(self, reason, name):
		super().__init__("%s: %s" % (reason, name))
		self.reason = reason
		self.name = name


class Attachment:
	def __init__(self, name, kind, mime, data=None, text=None, truncated=False):
		self.name = name
		self.kind = kind  # "image", "pdf", "media" or "text"
		self.mime = mime
		self.data = data  # bytes (image, pdf, media)
		self.text = text  # str (text)
		self.truncated = truncated

	@property
	def size(self):
		return len(self.data) if self.data is not None else len((self.text or "").encode("utf-8"))

	def base64(self):
		return base64.b64encode(self.data).decode("ascii") if self.data is not None else ""

	def dataUrl(self):
		return "data:%s;base64,%s" % (self.mime, self.base64())

	def asPromptText(self):
		"""Text block sent to the AI for text attachments."""
		body = self.text or ""
		note = "\n[...]" if self.truncated else ""
		return "<file name=\"%s\">\n%s%s\n</file>" % (self.name, body, note)

	def toDict(self):
		d = {"name": self.name, "kind": self.kind, "mime": self.mime}
		if self.data is not None:
			d["data"] = self.base64()
		if self.text is not None:
			d["text"] = self.text
		if self.truncated:
			d["truncated"] = True
		return d

	@classmethod
	def fromDict(cls, d):
		data = d.get("data")
		return cls(
			d.get("name", "file"),
			d.get("kind", "text"),
			d.get("mime", "application/octet-stream"),
			data=base64.b64decode(data) if data else None,
			text=d.get("text"),
			truncated=d.get("truncated", False),
		)

	@classmethod
	def image(cls, data, name="screenshot.png", mime="image/png"):
		return cls(name, "image", mime, data=data)


def humanSize(n):
	for unit in ("bytes", "KB", "MB", "GB"):
		if n < 1024 or unit == "GB":
			return ("%d %s" % (n, unit)) if unit == "bytes" else ("%.1f %s" % (n, unit))
		n /= 1024.0


# --- loading -------------------------------------------------------------------

def load(path, convertImage=None):
	"""Reads a file and returns an Attachment. Raises AttachmentError."""
	name = os.path.basename(path)
	try:
		size = os.path.getsize(path)
	except OSError:
		raise AttachmentError("unreadable", name)
	if size == 0:
		raise AttachmentError("empty", name)
	if size > MAX_FILE_BYTES:
		raise AttachmentError("tooBig", name)
	try:
		with open(path, "rb") as f:
			data = f.read()
	except OSError:
		raise AttachmentError("unreadable", name)
	return fromBytes(name, data, convertImage=convertImage)


def fromBytes(name, data, convertImage=None):
	ext = os.path.splitext(name)[1].lower()
	mime = _sniffMime(data) or mimetypes.guess_type(name)[0] or "application/octet-stream"

	if mime in NATIVE_IMAGE_TYPES:
		return Attachment(name, "image", mime, data=data)
	if mime.startswith("image/") or ext in CONVERTIBLE_IMAGE_EXT:
		png = (convertImage or _convertImageWithWx)(data)
		if png:
			return Attachment(os.path.splitext(name)[0] + ".png", "image", "image/png", data=png)
		if mime == "image/svg+xml" or ext == ".svg":
			return _textAttachment(name, _decode(data))
		raise AttachmentError("unreadable", name)
	if mime == "application/pdf" or ext == ".pdf":
		return Attachment(name, "pdf", "application/pdf", data=data)
	if ext in MEDIA_TYPES:
		return Attachment(name, "media", MEDIA_TYPES[ext], data=data)
	if mime.startswith("audio/") or mime.startswith("video/"):
		return Attachment(name, "media", mime, data=data)
	if ext in OFFICE_LEGACY:
		raise AttachmentError("legacyOffice", name)

	if data[:2] == b"PK":
		try:
			text = _extractZipDocument(data, ext)
		except _UnsafeDocument:
			raise AttachmentError("suspicious", name)
		if text is not None:
			return _textAttachment(name, text)
		raise AttachmentError("binary", name)
	if ext == ".rtf" or data[:5] == b"{\\rtf":
		return _textAttachment(name, _rtfToText(_decode(data)))
	if ext in (".html", ".htm", ".xhtml"):
		return _textAttachment(name, _htmlToText(_decode(data)))
	text = _decodeIfText(data)
	if text is not None:
		return _textAttachment(name, text)
	raise AttachmentError("binary", name)


def _textAttachment(name, text):
	text = (text or "").replace("\r\n", "\n").strip()
	if not text:
		raise AttachmentError("empty", name)
	truncated = len(text) > MAX_TEXT_CHARS
	if truncated:
		text = text[:MAX_TEXT_CHARS]
	return Attachment(name, "text", "text/plain", text=text, truncated=truncated)


def _sniffMime(data):
	head = data[:16]
	if head.startswith(b"\x89PNG\r\n\x1a\n"):
		return "image/png"
	if head[:3] == b"\xff\xd8\xff":
		return "image/jpeg"
	if head[:6] in (b"GIF87a", b"GIF89a"):
		return "image/gif"
	if head[:4] == b"RIFF" and data[8:12] == b"WEBP":
		return "image/webp"
	if head[:4] == b"%PDF":
		return "application/pdf"
	if head[:2] == b"BM":
		return "image/bmp"
	return None


def _convertImageWithWx(data):
	try:
		import io
		import wx
		img = wx.Image(io.BytesIO(data))
		if not img.IsOk():
			return None
		out = io.BytesIO()
		if not img.SaveFile(out, wx.BITMAP_TYPE_PNG):
			return None
		return out.getvalue()
	except Exception:
		return None


def _decode(data):
	for enc in ("utf-8-sig", "utf-16") if data[:2] in (b"\xff\xfe", b"\xfe\xff") else ("utf-8-sig", "cp1252", "latin-1"):
		try:
			return data.decode(enc)
		except UnicodeDecodeError:
			continue
	return data.decode("latin-1", "replace")


def _decodeIfText(data):
	if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
		try:
			return data.decode("utf-16")
		except UnicodeDecodeError:
			return None
	sample = data[:65536]
	if b"\x00" in sample:
		return None
	try:
		return data.decode("utf-8-sig")
	except UnicodeDecodeError:
		pass
	# Accept legacy Windows text only if it is mostly printable.
	text = data.decode("cp1252", "replace")
	controls = sum(1 for ch in text[:65536] if ord(ch) < 32 and ch not in "\n\r\t\f")
	if controls > len(text[:65536]) * 0.02:
		return None
	return text


# --- documents inside zip files (Office Open XML, OpenDocument, EPUB) ----------

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
_S = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


class _UnsafeDocument(Exception):
	"""Zip bomb, or XML with DTD/entities (billion laughs, XXE)."""


def _checkZipSizes(z):
	total = 0
	for info in z.infolist():
		total += info.file_size
		if info.file_size > MAX_UNZIPPED_BYTES or total > MAX_UNZIPPED_BYTES:
			raise _UnsafeDocument("expands too much")
		if info.file_size > 1024 * 1024 and info.compress_size and info.file_size / info.compress_size > MAX_COMPRESSION_RATIO:
			raise _UnsafeDocument("compression ratio")


def _extractZipDocument(data, ext):
	import io
	try:
		z = zipfile.ZipFile(io.BytesIO(data))
	except zipfile.BadZipFile:
		return None
	_checkZipSizes(z)
	names = set(z.namelist())
	try:
		if "word/document.xml" in names:
			return _docx(z)
		if "xl/workbook.xml" in names:
			return _xlsx(z)
		if "ppt/presentation.xml" in names:
			return _pptx(z)
		if "content.xml" in names and "mimetype" in names:
			return _odf(z)
		if "META-INF/container.xml" in names:
			return _epub(z)
	except (KeyError, ElementTree.ParseError, ValueError):
		return None
	return None


_DTD_RE = re.compile(rb"<!\s*(DOCTYPE|ENTITY)", re.I)


def _xml(z, name):
	data = z.read(name)
	# Office, OpenDocument and EPUB content never needs a DTD. Refusing DTDs blocks
	# entity expansion ("billion laughs") and external entities (XXE) whatever the
	# version of expat bundled with NVDA.
	if _DTD_RE.search(data):
		raise _UnsafeDocument("DTD")
	# DTD and entities were refused above.
	return ElementTree.fromstring(data)  # nosec B314


def _docx(z):
	parts = ["word/document.xml"] + sorted(n for n in z.namelist() if re.match(r"word/(footnotes|endnotes)\.xml$", n))
	out = []
	for part in parts:
		root = _xml(z, part)
		for p in root.iter(_W + "p"):
			chunks = []
			for node in p.iter():
				if node.tag == _W + "t" and node.text:
					chunks.append(node.text)
				elif node.tag == _W + "tab":
					chunks.append("\t")
				elif node.tag in (_W + "br", _W + "cr"):
					chunks.append("\n")
			out.append("".join(chunks))
	return "\n".join(out)


def _colIndex(ref):
	letters = re.match(r"[A-Z]+", ref or "")
	n = 0
	for ch in letters.group(0) if letters else "":
		n = n * 26 + ord(ch) - 64
	return max(n - 1, 0)


def _xlsx(z):
	shared = []
	if "xl/sharedStrings.xml" in z.namelist():
		for si in _xml(z, "xl/sharedStrings.xml").iter(_S + "si"):
			shared.append("".join(t.text or "" for t in si.iter(_S + "t")))
	wb = _xml(z, "xl/workbook.xml")
	rels = {}
	if "xl/_rels/workbook.xml.rels" in z.namelist():
		for rel in _xml(z, "xl/_rels/workbook.xml.rels"):
			rels[rel.get("Id")] = rel.get("Target")
	out = []
	for sheet in wb.iter(_S + "sheet"):
		target = rels.get(sheet.get(_R + "id"), "")
		path = target.lstrip("/") if target.startswith("/") else "xl/" + target
		if path not in z.namelist():
			continue
		out.append("# %s" % sheet.get("name"))
		for row in _xml(z, path).iter(_S + "row"):
			cells = []
			for c in row.iter(_S + "c"):
				idx = _colIndex(c.get("r"))
				while len(cells) < idx:
					cells.append("")
				value = ""
				t = c.get("t")
				v = c.find(_S + "v")
				if t == "s" and v is not None:
					value = shared[int(v.text)] if v.text and int(v.text) < len(shared) else ""
				elif t == "inlineStr":
					value = "".join(x.text or "" for x in c.iter(_S + "t"))
				elif v is not None and v.text is not None:
					value = v.text
				cells.append(value.replace("\t", " ").replace("\n", " "))
			if any(cells):
				out.append("\t".join(cells))
		out.append("")
	return "\n".join(out)


def _pptx(z):
	slides = sorted(
		(n for n in z.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", n)),
		key=lambda n: int(re.search(r"(\d+)", n.rsplit("/", 1)[1]).group(1)),
	)
	out = []
	for i, name in enumerate(slides, 1):
		out.append("# Slide %d" % i)
		for p in _xml(z, name).iter(_A + "p"):
			line = "".join(t.text or "" for t in p.iter(_A + "t"))
			if line.strip():
				out.append(line)
		notes = name.replace("slides/slide", "notesSlides/notesSlide")
		if notes in z.namelist():
			text = " ".join(t.text or "" for t in _xml(z, notes).iter(_A + "t")).strip()
			if text:
				out.append("(notes) " + text)
		out.append("")
	return "\n".join(out)


def _odf(z):
	root = _xml(z, "content.xml")
	textNs = "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}"
	tableNs = "{urn:oasis:names:tc:opendocument:xmlns:table:1.0}"
	out = []
	rows = list(root.iter(tableNs + "table-row"))
	if rows and not list(root.iter("{urn:oasis:names:tc:opendocument:xmlns:presentation:1.0}notes")) and root.find(".//" + tableNs + "table") is not None and not list(root.iter(textNs + "h")):
		for row in rows:
			cells = ["".join(cell.itertext()).strip() for cell in row.iter(tableNs + "table-cell")]
			if any(cells):
				out.append("\t".join(cells).rstrip("\t"))
		return "\n".join(out)
	for node in root.iter():
		if node.tag in (textNs + "p", textNs + "h"):
			out.append("".join(node.itertext()))
	return "\n".join(out)


class _TextFromHtml(HTMLParser):
	BLOCK = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "section", "article", "table", "ul", "ol", "pre", "blockquote"}

	def __init__(self):
		super().__init__(convert_charrefs=True)
		self.parts = []
		self.skip = 0

	def handle_starttag(self, tag, attrs):
		if tag in ("script", "style"):
			self.skip += 1
		elif tag in self.BLOCK:
			self.parts.append("\n")

	def handle_endtag(self, tag):
		if tag in ("script", "style") and self.skip:
			self.skip -= 1
		elif tag in self.BLOCK:
			self.parts.append("\n")

	def handle_data(self, data):
		if not self.skip:
			self.parts.append(data)


def _htmlToText(html):
	parser = _TextFromHtml()
	parser.feed(html)
	text = "".join(parser.parts)
	text = re.sub(r"[ \t]+", " ", text)
	return re.sub(r"\n\s*\n+", "\n\n", text).strip()


def _epub(z):
	names = sorted(n for n in z.namelist() if n.lower().endswith((".xhtml", ".html", ".htm")))
	return "\n\n".join(_htmlToText(_decode(z.read(n))) for n in names)


def _rtfToText(rtf):
	text = re.sub(r"\\par[d]?\b ?", "\n", rtf)
	text = re.sub(r"\\'([0-9a-fA-F]{2})", lambda m: bytes([int(m.group(1), 16)]).decode("cp1252", "replace"), text)
	text = re.sub(r"\\u(-?\d+)\??", lambda m: chr(int(m.group(1)) % 65536), text)
	text = re.sub(r"\{\\\*[^{}]*\}", "", text)
	text = re.sub(r"\{\\(fonttbl|colortbl|stylesheet|info)[^{}]*(\{[^{}]*\}[^{}]*)*\}", "", text)
	text = re.sub(r"\\[a-zA-Z]+-?\d* ?", "", text)
	text = text.replace("{", "").replace("}", "").replace("\\\\", "\\")
	return re.sub(r"\n\s*\n+", "\n\n", text).strip()
