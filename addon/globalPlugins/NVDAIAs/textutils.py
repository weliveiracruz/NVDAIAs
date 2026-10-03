# -*- coding: UTF-8 -*-
# NVDAIAs - textutils.py
# Converts the Markdown returned by the AIs into speech-friendly text and into HTML.
# Copyright (C) 2026 Wellington Cruz
# This file is covered by the GNU General Public License, version 2.

import html
import re

_FENCE = re.compile(r"^\s*(```|~~~)")
_HEADING = re.compile(r"^\s{0,3}(#{1,6})\s+(.*?)\s*#*\s*$")
_BULLET = re.compile(r"^(\s*)[-*+•]\s+(.*)$")
_NUMBERED = re.compile(r"^(\s*)(\d+)[.)]\s+(.*)$")
_QUOTE = re.compile(r"^\s*>\s?(.*)$")
_HRULE = re.compile(r"^\s*([-*_])(\s*\1){2,}\s*$")
_TABLE_SEP = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")
_IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)[^)]*\)")
_LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)[^)]*\)")
_BOLD = re.compile(r"(\*\*|__)(?=\S)(.+?)(?<=\S)\1")
_ITALIC_STAR = re.compile(r"(?<![\w*])\*(?=\S)([^*\n]+?)(?<=\S)\*(?![\w*])")
_ITALIC_UNDER = re.compile(r"(?<![\w_])_(?=\S)([^_\n]+?)(?<=\S)_(?![\w_])")
_STRIKE = re.compile(r"~~(?=\S)(.+?)(?<=\S)~~")
_CODE = re.compile(r"`([^`\n]+)`")


def _inlinePlain(text):
	text = _IMAGE.sub(lambda m: m.group(1), text)
	text = _LINK.sub(lambda m: m.group(1) if m.group(1) == m.group(2) else "%s (%s)" % (m.group(1), m.group(2)), text)
	text = _CODE.sub(lambda m: m.group(1), text)
	text = _BOLD.sub(lambda m: m.group(2), text)
	text = _ITALIC_STAR.sub(lambda m: m.group(1), text)
	text = _ITALIC_UNDER.sub(lambda m: m.group(1), text)
	text = _STRIKE.sub(lambda m: m.group(1), text)
	return text


def toPlainText(markdown):
	"""Removes Markdown symbols that a speech synthesizer would read aloud (#, **, |, ```)."""
	lines = []
	inCode = False
	for line in (markdown or "").replace("\r\n", "\n").split("\n"):
		if _FENCE.match(line):
			inCode = not inCode
			continue
		if inCode:
			lines.append(line)
			continue
		if _HRULE.match(line) or _TABLE_SEP.match(line):
			continue
		m = _HEADING.match(line)
		if m:
			lines.append(_inlinePlain(m.group(2)))
			continue
		m = _BULLET.match(line)
		if m:
			lines.append(m.group(1) + _inlinePlain(m.group(2)))
			continue
		m = _QUOTE.match(line)
		if m:
			line = m.group(1)
		if line.strip().startswith("|") or line.count("|") >= 2:
			cells = [c.strip() for c in line.strip().strip("|").split("|")]
			line = ", ".join(c for c in cells if c)
		lines.append(_inlinePlain(line))
	text = "\n".join(lines)
	text = re.sub(r"\n{3,}", "\n\n", text)
	return text.strip()


def oneLine(text, limit=None):
	"""Collapses a text to a single line (for list items)."""
	text = re.sub(r"\s+", " ", text or "").strip()
	if limit and len(text) > limit:
		text = text[: limit - 1].rstrip() + "…"
	return text


def _inlineHtml(text):
	"""Escapes the text and converts inline Markdown to HTML."""
	codes = []

	def keepCode(m):
		codes.append("<code>%s</code>" % html.escape(m.group(1)))
		return "\x00%d\x00" % (len(codes) - 1)

	text = _CODE.sub(keepCode, text)
	text = html.escape(text, quote=False)
	text = _IMAGE.sub(lambda m: m.group(1), text)

	def link(m):
		url = m.group(2)
		if not re.match(r"^(https?:|mailto:)", url, re.I):
			return m.group(1)
		return '<a href="%s">%s</a>' % (url.replace('"', "%22"), m.group(1))

	text = _LINK.sub(link, text)
	text = _BOLD.sub(lambda m: "<strong>%s</strong>" % m.group(2), text)
	text = _ITALIC_STAR.sub(lambda m: "<em>%s</em>" % m.group(1), text)
	text = _ITALIC_UNDER.sub(lambda m: "<em>%s</em>" % m.group(1), text)
	text = _STRIKE.sub(lambda m: "<del>%s</del>" % m.group(1), text)
	return re.sub("\x00(\\d+)\x00", lambda m: codes[int(m.group(1))], text)


def toHtml(markdown):
	"""Small, safe Markdown to HTML converter (all text is escaped)."""
	out = []
	para = []
	listStack = []  # list of "ul"/"ol"
	liOpen = []  # whether the last <li> of each level is still open (nested lists go inside it)
	table = []
	inCode = False
	code = []

	def flushPara():
		if para:
			out.append("<p>%s</p>" % "<br>".join(_inlineHtml(p) for p in para))
			del para[:]

	def closeLevel():
		if liOpen.pop():
			out.append("</li>")
		out.append("</%s>" % listStack.pop())

	def closeLists():
		while listStack:
			closeLevel()

	def flushTable():
		if not table:
			return
		out.append("<table border=\"1\">")
		for i, row in enumerate(table):
			tag = "th" if i == 0 and len(table) > 1 else "td"
			out.append("<tr>%s</tr>" % "".join("<%s>%s</%s>" % (tag, _inlineHtml(c), tag) for c in row))
		out.append("</table>")
		del table[:]

	for line in (markdown or "").replace("\r\n", "\n").split("\n"):
		if inCode:
			if _FENCE.match(line):
				out.append("<pre><code>%s</code></pre>" % html.escape("\n".join(code)))
				code = []
				inCode = False
			else:
				code.append(line)
			continue
		if _FENCE.match(line):
			flushPara(); closeLists(); flushTable()
			inCode = True
			continue
		stripped = line.strip()
		if not stripped:
			flushPara(); closeLists(); flushTable()
			continue
		if _TABLE_SEP.match(line) and table:
			continue
		if stripped.startswith("|") and stripped.count("|") >= 2:
			flushPara(); closeLists()
			table.append([c.strip() for c in stripped.strip("|").split("|")])
			continue
		flushTable()
		if _HRULE.match(line):
			flushPara(); closeLists()
			out.append("<hr>")
			continue
		m = _HEADING.match(line)
		if m:
			flushPara(); closeLists()
			level = len(m.group(1))
			out.append("<h%d>%s</h%d>" % (level, _inlineHtml(m.group(2)), level))
			continue
		m = _BULLET.match(line) or _NUMBERED.match(line)
		if m:
			flushPara()
			kind = "ol" if _NUMBERED.match(line) and not _BULLET.match(line) else "ul"
			indent = len(m.group(1).replace("\t", "    ")) // 2
			depth = min(indent, len(listStack))  # 0-based depth wanted
			while len(listStack) > depth + 1:
				closeLevel()
			if len(listStack) == depth + 1 and listStack[-1] != kind:
				closeLevel()
			if len(listStack) == depth + 1:
				if liOpen[-1]:
					out.append("</li>")
			else:
				listStack.append(kind)
				liOpen.append(False)
				out.append("<%s>" % kind)
			out.append("<li>%s" % _inlineHtml(m.groups()[-1]))
			liOpen[-1] = True
			continue
		m = _QUOTE.match(line)
		if m:
			flushPara(); closeLists()
			out.append("<blockquote>%s</blockquote>" % _inlineHtml(m.group(1)))
			continue
		if listStack:
			closeLists()
		para.append(stripped)
	if inCode:
		out.append("<pre><code>%s</code></pre>" % html.escape("\n".join(code)))
	flushPara(); closeLists(); flushTable()
	return "\n".join(out)
