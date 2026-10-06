# -*- coding: UTF-8 -*-
# NVDAIAs - theme.py
# Visual theme built from the design tokens in design/tokens.json.
# Copyright (C) 2026 Wellington Cruz
# This file is covered by the GNU General Public License, version 2.
#
# Modern layout: orange app bar, light grey page, white cards with rounded
# corners behind each group of controls, status chip and a rounded orange
# focus ring. Everything is painted behind or around the native controls.
#
# Accessibility rules followed here:
# * colours are only applied to the dialog background, labels, text fields and
#   lists; buttons stay native so NVDA presents them exactly as before;
# * cards, chips and the header are painted, never focusable, and do not change
#   the tab order or the names NVDA reads;
# * the theme switches itself off when Windows high contrast is on;
# * nothing is conveyed by colour alone: the status line has text, and the
#   focus frame is an extra visual cue on top of the normal system focus.

import json
import os
import sys

import wx

_HERE = os.path.dirname(os.path.abspath(__file__))
TOKENS_PATH = os.path.join(_HERE, "design", "tokens.json")

_tokens = None


def tokens():
	global _tokens
	if _tokens is None:
		with open(TOKENS_PATH, encoding="utf-8") as f:
			_tokens = json.load(f)
	return _tokens


def color(name):
	return wx.Colour(tokens()["color"][name])


def space(name):
	return int(tokens()["space"][name])


def border(name):
	return int(tokens()["border"][name])


def radius(name):
	return int(tokens().get("radius", {}).get(name, 0))


_faces = {}


def fontFace(kind="family"):
	"""First font of the token list that is installed on this computer."""
	if kind not in _faces:
		families = tokens()["font"].get(kind) or tokens()["font"]["family"]
		if isinstance(families, str):
			families = [families]
		try:
			installed = {f.lower() for f in wx.FontEnumerator.GetFacenames()}
		except Exception:
			installed = set()
		_faces[kind] = next((f for f in families if f.lower() in installed), families[-1])
	return _faces[kind]


def font(sizeName, bold=False, scale=1.0, display=False):
	t = tokens()["font"]
	size = max(6, int(round(t[sizeName] * scale)))
	return wx.Font(
		wx.FontInfo(size).FaceName(fontFace("family.display" if display else "family")).Bold(bold)
	)


# --- contrast (WCAG 2.x) ------------------------------------------------------------

def _luminance(hexColor):
	h = hexColor.lstrip("#")
	channels = [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
	lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
	return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrastRatio(a, b):
	la, lb = sorted((_luminance(a), _luminance(b)), reverse=True)
	return (la + 0.05) / (lb + 0.05)


# --- when to use the theme ---------------------------------------------------------

def isHighContrast():
	"""True when Windows high contrast mode is on (the theme then stays off)."""
	if sys.platform != "win32":
		return False
	try:
		import ctypes
		from ctypes import wintypes

		class HIGHCONTRAST(ctypes.Structure):
			_fields_ = [("cbSize", wintypes.UINT), ("dwFlags", wintypes.DWORD), ("lpszDefaultScheme", wintypes.LPWSTR)]

		hc = HIGHCONTRAST()
		hc.cbSize = ctypes.sizeof(HIGHCONTRAST)
		SPI_GETHIGHCONTRAST = 0x0042
		HCF_HIGHCONTRASTON = 0x1
		if ctypes.windll.user32.SystemParametersInfoW(SPI_GETHIGHCONTRAST, hc.cbSize, ctypes.byref(hc), 0):
			return bool(hc.dwFlags & HCF_HIGHCONTRASTON)
	except Exception:
		pass
	return False


def isEnabled():
	from . import core
	return bool(core.conf()["visualTheme"]) and not isHighContrast()


def fontScale():
	from . import core
	return 1.25 if core.conf()["largeText"] else 1.0


# --- building blocks ----------------------------------------------------------------

class HeaderPanel(wx.Panel):
	"""App bar: orange band with the title in large white bold text, and the
	subtitle below it on the page colour. Purely visual: it never takes the focus."""

	def __init__(self, parent, title, subtitle):
		super().__init__(parent)
		scale = fontScale()
		self.SetBackgroundColour(color("surface.page"))
		sizer = wx.BoxSizer(wx.VERTICAL)
		pad = space("xl")
		self.bar = wx.Panel(self)
		self.bar.SetBackgroundColour(color("surface.header"))
		barSizer = wx.BoxSizer(wx.VERTICAL)
		self.titleText = wx.StaticText(self.bar, label=title)
		# White on orange only passes WCAG as large bold text (3:1): the title is 18pt bold.
		self.titleText.SetFont(font("size.title", bold=True, scale=scale, display=True))
		self.titleText.SetForegroundColour(color("text.onHeader"))
		self.titleText.SetBackgroundColour(color("surface.header"))
		barSizer.AddSpacer(space("lg"))
		barSizer.Add(self.titleText, flag=wx.LEFT | wx.RIGHT, border=pad)
		barSizer.AddSpacer(space("lg"))
		self.bar.SetSizer(barSizer)
		sizer.Add(self.bar, flag=wx.EXPAND)
		self.subtitleText = wx.StaticText(self, label=subtitle)
		self.subtitleText.SetFont(font("size.subtitle", scale=scale))
		self.subtitleText.SetForegroundColour(color("text.secondary"))
		sizer.AddSpacer(space("md"))
		sizer.Add(self.subtitleText, flag=wx.LEFT | wx.RIGHT, border=pad)
		self.SetSizer(sizer)

	def AcceptsFocus(self):
		return False

	def AcceptsFocusFromKeyboard(self):
		return False


class StatusLine(wx.StaticText):
	"""One line of text such as "Claude · claude-sonnet-5-5 · connected"; the
	colour only repeats what the text already says."""

	KINDS = {"ok": "status.ok", "busy": "status.busy", "error": "status.error", "idle": "status.idle"}

	def __init__(self, parent):
		super().__init__(parent, label="")
		self._themed = isEnabled()
		self.kind = "idle"
		if self._themed:
			self.SetFont(font("size.status", bold=True, scale=fontScale()))

	def setStatus(self, text, kind="idle"):
		if self.GetLabel() != text:
			self.SetLabel(text)
		self.kind = kind
		if self._themed:
			# Shown as a chip: tinted background, text in the matching dark colour.
			name = self.KINDS.get(kind, "status.idle")
			self.SetForegroundColour(color(name))
			self.SetBackgroundColour(color(name + "Bg"))
			self.Refresh()
			parent = self.GetParent()
			if parent:
				parent.RefreshRect(self.GetRect().Inflate(space("md"), space("sm")))


def applyColors(window, bodyControls=(), cards=()):
	"""Colours the dialog, its labels and its text fields / lists (not buttons).
	Labels that belong to a card get the card colour and the title style."""
	scale = fontScale()
	window.SetBackgroundColour(color("surface.page"))
	window.SetForegroundColour(color("text.primary"))
	bodyFont = font("size.body", scale=scale)
	labelFont = font("size.label", bold=True, scale=scale)
	inCards = {id(c) for card in cards for c in card.windows}

	def walk(win):
		for child in win.GetChildren():
			if isinstance(child, (HeaderPanel, StatusLine)):
				continue
			if isinstance(child, wx.StaticBox):
				child.SetForegroundColour(color("text.accent"))
				walk(child)
			elif isinstance(child, wx.StaticText):
				child.SetFont(labelFont)
				if id(child) in inCards:
					child.SetForegroundColour(color("text.primary"))
					child.SetBackgroundColour(color("surface.card"))
				else:
					child.SetForegroundColour(color("text.secondary"))
			elif isinstance(child, (wx.TextCtrl, wx.ListBox, wx.ComboBox, wx.TreeCtrl)):
				child.SetBackgroundColour(color("surface.card"))
				child.SetForegroundColour(color("text.primary"))
				if child in bodyControls:
					child.SetFont(bodyFont)
			elif isinstance(child, wx.CheckBox):
				child.SetForegroundColour(color("text.primary"))
			elif isinstance(child, wx.Panel) and not isinstance(child, wx.Button):
				child.SetBackgroundColour(color("surface.page"))
				walk(child)

	walk(window)


class Card:
	"""A group of controls painted on a white rounded card.

	``sizer`` gives the card its size (the whole row, not only the controls),
	``title`` is the label that gets the orange accent bar (or None) and
	``windows`` are the controls on the card (their labels get the card colour)."""

	def __init__(self, sizer, windows, title=None):
		self.sizer = sizer
		self.windows = list(windows)
		self.title = title


class FocusFrames:
	"""Paints the modern layout behind the native controls:

	* cards: white rounded rectangles behind each group of controls, with a
	  short orange accent bar next to the card title (its first label);
	* the status chip: rounded tinted background behind the status line;
	* the focus ring: a rounded orange frame around the control that has the
	  focus (extra visual focus indicator for people with low vision).
	"""

	def __init__(self, window, controls, cards=(), chips=()):
		self.window = window
		self.controls = list(controls)
		self.cards = list(cards)
		self.chips = list(chips)
		window.Bind(wx.EVT_PAINT, self.onPaint)
		for ctrl in self.controls:
			ctrl.Bind(wx.EVT_SET_FOCUS, self._onFocusChange)
			ctrl.Bind(wx.EVT_KILL_FOCUS, self._onFocusChange)
		window.Bind(wx.EVT_SIZE, self._onSize)

	def _onFocusChange(self, evt):
		evt.Skip()
		wx.CallAfter(self._refresh)

	def _onSize(self, evt):
		evt.Skip()
		self._refresh()

	def _refresh(self):
		if self.window:
			self.window.Refresh()

	def focusedControl(self):
		focus = wx.Window.FindFocus()
		for ctrl in self.controls:
			if focus is ctrl or (focus is not None and ctrl.IsDescendant(focus)):
				return ctrl
		return None

	def cardRect(self, card):
		"""Rectangle of a card: the area of its sizer plus padding."""
		pos = card.sizer.GetPosition()
		size = card.sizer.GetSize()
		if size.width <= 0 or size.height <= 0:
			return None
		pad = space("md")
		return wx.Rect(pos.x - pad, pos.y - pad, size.width + 2 * pad, size.height + 2 * pad)

	def onPaint(self, evt):
		dc = wx.PaintDC(self.window)
		gc = wx.GraphicsContext.Create(dc) if hasattr(wx, "GraphicsContext") else None
		painter = gc if gc is not None else dc

		def roundRect(rect, rad, brush, pen):
			painter.SetBrush(brush)
			painter.SetPen(pen)
			if gc is not None:
				gc.DrawRoundedRectangle(rect.x, rect.y, rect.width, rect.height, rad)
			else:
				dc.DrawRoundedRectangle(rect, rad)

		for card in self.cards:
			rect = self.cardRect(card)
			if rect is None:
				continue
			roundRect(rect, radius("card"), wx.Brush(color("surface.card")), wx.Pen(color("border.card"), border("card")))
			title = card.title
			if title is not None and title.IsShown():
				tr = title.GetRect()
				bar = wx.Rect(rect.x, tr.y, border("accent"), tr.height)
				roundRect(bar, 1, wx.Brush(color("brand.orange")), wx.TRANSPARENT_PEN)
		for chip in self.chips:
			if not chip.IsShown() or not chip.GetLabel():
				continue
			r = chip.GetRect()
			kind = getattr(chip, "kind", "idle")
			name = StatusLine.KINDS.get(kind, "status.idle") + "Bg"
			rect = wx.Rect(r.x - space("md"), r.y - space("xs"), r.width + 2 * space("md"), r.height + 2 * space("xs"))
			roundRect(rect, radius("chip"), wx.Brush(color(name)), wx.TRANSPARENT_PEN)
		focused = self.focusedControl()
		if focused is not None and focused.IsShown():
			width = border("focus")
			r = focused.GetRect()
			inflate = border("gap") + width // 2
			rect = wx.Rect(r.x - inflate, r.y - inflate, r.width + 2 * inflate, r.height + 2 * inflate)
			roundRect(rect, radius("focus"), wx.TRANSPARENT_BRUSH, wx.Pen(color("border.focus"), width))
