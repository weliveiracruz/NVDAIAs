# -*- coding: UTF-8 -*-
"""Builds the NVDAIAs add-on package (dist/NVDAIAs-<version>.nvda-addon).

Usage:  python build.py

Only the Python standard library is needed. The script:
  1. checks manifest.ini;
  2. compiles the translations (locale/*/LC_MESSAGES/nvda.po -> nvda.mo);
  3. converts the documentation (readme.md, docs/pt_BR/readme.md) to addon/doc/<lang>/readme.html;
  4. zips the addon folder and prints the SHA-256 (needed by the Add-on Store).
"""

import ast
import hashlib
import html
import os
import re
import struct
import sys
import types
import zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))
ADDON = os.path.join(ROOT, "addon")
DIST = os.path.join(ROOT, "dist")

DOCS = {
	"en": os.path.join(ROOT, "readme.md"),
	"pt_BR": os.path.join(ROOT, "docs", "pt_BR", "readme.md"),
}


def readManifest():
	path = os.path.join(ADDON, "manifest.ini")
	data = {}
	with open(path, encoding="utf-8") as f:
		text = f.read()
	for m in re.finditer(r'^(\w+)\s*=\s*("""(.*?)"""|"(.*?)"|(.*?))\s*$', text, re.M | re.S):
		value = m.group(3) if m.group(3) is not None else (m.group(4) if m.group(4) is not None else m.group(5))
		data[m.group(1)] = value
	return data


def checkManifest(man):
	required = ("name", "summary", "description", "author", "url", "version", "minimumNVDAVersion", "lastTestedNVDAVersion", "docFileName")
	missing = [k for k in required if not man.get(k)]
	if missing:
		sys.exit("manifest.ini: missing %s" % ", ".join(missing))
	if not re.fullmatch(r"\d+\.\d+\.\d+", man["version"]):
		sys.exit("manifest.ini: version must be major.minor.patch")
	for key in ("minimumNVDAVersion", "lastTestedNVDAVersion"):
		if not re.fullmatch(r"\d{4}\.\d+(\.\d+)?", man[key]):
			sys.exit("manifest.ini: invalid %s" % key)
	if tuple(map(int, man["minimumNVDAVersion"].split("."))) > tuple(map(int, man["lastTestedNVDAVersion"].split("."))):
		sys.exit("manifest.ini: minimumNVDAVersion is newer than lastTestedNVDAVersion")
	if not man["url"].startswith("https://"):
		sys.exit("manifest.ini: url must start with https://")


# --- msgfmt (compile .po to .mo) --------------------------------------------------

def _unquote(s):
	return ast.literal_eval(s)


def parsePo(path):
	messages = {}
	msgid = msgstr = None
	section = None
	fuzzy = False

	def flush():
		if msgid is not None and msgstr is not None and not fuzzy and (msgstr or msgid == ""):
			messages[msgid] = msgstr

	with open(path, encoding="utf-8") as f:
		for line in f:
			line = line.strip()
			if line.startswith("#,") and "fuzzy" in line:
				fuzzy = True
			elif line.startswith("msgid "):
				flush()
				msgid, msgstr, section = _unquote(line[6:]), None, "id"
			elif line.startswith("msgstr "):
				msgstr, section = _unquote(line[7:]), "str"
			elif line.startswith('"'):
				if section == "id":
					msgid += _unquote(line)
				elif section == "str":
					msgstr += _unquote(line)
			elif not line:
				flush()
				msgid = msgstr = section = None
				fuzzy = False
	flush()
	return messages


def writeMo(messages, path):
	keys = sorted(messages)
	ids = b""
	strs = b""
	offsets = []
	for k in keys:
		kb = k.encode("utf-8")
		vb = messages[k].encode("utf-8")
		offsets.append((len(ids), len(kb), len(strs), len(vb)))
		ids += kb + b"\0"
		strs += vb + b"\0"
	n = len(keys)
	keyStart = 7 * 4 + 16 * n
	valueStart = keyStart + len(ids)
	koffsets = []
	voffsets = []
	for o1, l1, o2, l2 in offsets:
		koffsets += [l1, o1 + keyStart]
		voffsets += [l2, o2 + valueStart]
	output = struct.pack("Iiiiiii", 0x950412DE, 0, n, 7 * 4, 7 * 4 + n * 8, 0, 0)
	output += struct.pack("%di" % len(koffsets), *koffsets)
	output += struct.pack("%di" % len(voffsets), *voffsets)
	output += ids + strs
	with open(path, "wb") as f:
		f.write(output)


def compileTranslations():
	localeDir = os.path.join(ADDON, "locale")
	for lang in sorted(os.listdir(localeDir)):
		po = os.path.join(localeDir, lang, "LC_MESSAGES", "nvda.po")
		if os.path.isfile(po):
			messages = parsePo(po)
			writeMo(messages, po[:-3] + ".mo")
			print("translation %s: %d messages" % (lang, len(messages) - 1))


# --- documentation ------------------------------------------------------------------

def loadTextutils():
	pkg = types.ModuleType("_nvdaias_build")
	pkg.__path__ = [os.path.join(ADDON, "globalPlugins", "NVDAIAs")]
	sys.modules["_nvdaias_build"] = pkg
	import importlib
	return importlib.import_module("_nvdaias_build.textutils")


def buildDocs(man):
	textutils = loadTextutils()
	for lang, source in DOCS.items():
		with open(source, encoding="utf-8") as f:
			md = f.read()
		title = md.splitlines()[0].lstrip("# ").strip()
		body = textutils.toHtml(md)
		page = (
			'<!DOCTYPE html>\n<html lang="%s">\n<head>\n<meta charset="utf-8">\n'
			"<title>%s</title>\n</head>\n<body>\n%s\n</body>\n</html>\n"
		) % (lang.replace("_", "-"), html.escape(title), body)
		outDir = os.path.join(ADDON, "doc", lang)
		os.makedirs(outDir, exist_ok=True)
		with open(os.path.join(outDir, man["docFileName"]), "w", encoding="utf-8") as f:
			f.write(page)
		print("doc %s: %s" % (lang, os.path.relpath(os.path.join(outDir, man["docFileName"]), ROOT)))


# --- package ------------------------------------------------------------------------

def buildPackage(man):
	os.makedirs(DIST, exist_ok=True)
	target = os.path.join(DIST, "%s-%s.nvda-addon" % (man["name"], man["version"]))
	with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
		for folder, dirs, files in os.walk(ADDON):
			dirs[:] = sorted(d for d in dirs if d != "__pycache__")
			for name in sorted(files):
				if name.endswith((".pyc", ".pyo", ".po", ".pot")):
					continue
				full = os.path.join(folder, name)
				z.write(full, os.path.relpath(full, ADDON).replace(os.sep, "/"))
	with open(target, "rb") as f:
		digest = hashlib.sha256(f.read()).hexdigest()
	with open(target + ".sha256", "w") as f:
		f.write("%s  %s\n" % (digest, os.path.basename(target)))
	print("\npackage: %s" % os.path.relpath(target, ROOT))
	print("SHA-256: %s" % digest)
	return target


if __name__ == "__main__":
	manifest = readManifest()
	checkManifest(manifest)
	compileTranslations()
	buildDocs(manifest)
	buildPackage(manifest)
