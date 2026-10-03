# -*- coding: UTF-8 -*-
# NVDAIAs - theme.py
# Visual theme built from the design tokens in design/tokens.json.
# Copyright (C) 2026 Wellington Cruz
# This file is covered by the GNU General Public License, version 2.
#
# Accessibility rules followed here:
# * colours are only applied to the dialog background, labels, text fields and
#   lists; buttons stay native so NVDA presents them exactly as before;
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


def font(sizeName, bold=False, scale=1.0):
	t = tokens()["font"]
	size = max(6, int(round(t[sizeName] * scale)))
	return wx.Font(
		wx.FontInfo(size).FaceName(t["family"]).Bold(bold)
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
	"""Navy band with the title, a subtitle and an orange stripe at the bottom.
	Purely visual: it never takes the focus."""

	def __init__(self, parent, title, subtitle):
		super().__init__(parent)
		scale = fontScale()
		self.SetBackgroundColour(color("surface.header"))
		sizer = wx.BoxSizer(wx.VERTICAL)
		pad = space("lg")
		self.titleText = wx.StaticText(self, label=title)
		self.titleText.SetFont(font("size.title", bold=True, scale=scale))
		self.titleText.SetForegroundColour(color("text.onHeader"))
		self.subtitleText = wx.StaticText(self, label=subtitle)
		self.subtitleText.SetFont(font("size.subtitle", scale=scale))
		self.subtitleText.SetForegroundColour(color("text.onHeaderMuted"))
		sizer.AddSpacer(space("md"))
		sizer.Add(self.titleText, flag=wx.LEFT | wx.RIGHT, border=pad)
		sizer.AddSpacer(space("xs"))
		sizer.Add(self.subtitleText, flag=wx.LEFT | wx.RIGHT, border=pad)
		sizer.AddSpacer(space("md"))
		stripe = wx.Panel(self, size=(-1, border("stripe")))
		stripe.SetBackgroundColour(color("brand.orange"))
		sizer.Add(stripe, flag=wx.EXPAND)
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
		if self._themed:
			self.SetFont(font("size.status", bold=True, scale=fontScale()))

	def setStatus(self, text, kind="idle"):
		if self.GetLabel() != text:
			self.SetLabel(text)
		if self._themed:
			self.SetForegroundColour(color(self.KINDS.get(kind, "status.idle")))
			self.Refresh()


def applyColors(window, bodyControls=()):
	"""Colours the dialog, its labels and its text fields / lists (not buttons)."""
	scale = fontScale()
	window.SetBackgroundColour(color("surface.page"))
	window.SetForegroundColour(color("text.primary"))
	bodyFont = font("size.body", scale=scale)
	labelFont = font("size.label", bold=True, scale=scale)

	def walk(win):
		for child in win.GetChildren():
			if isinstance(child, (HeaderPanel, StatusLine)):
				continue
			if isinstance(child, wx.StaticBox):
				child.SetForegroundColour(color("text.accent"))
				walk(child)
			elif isinstance(child, wx.StaticText):
				child.SetForegroundColour(color("text.secondary"))
				child.SetFont(labelFont)
			elif isinstance(child, (wx.TextCtrl, wx.ListBox, wx.ComboBox)):
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


class FocusFrames:
	"""Draws a thin frame around the main controls and a thick orange frame
	around the one that has the focus (extra visual focus indicator for people
	with low vision)."""

	def __init__(self, window, controls):
		self.window = window
		self.controls = list(controls)
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

	def onPaint(self, evt):
		dc = wx.PaintDC(self.window)
		focused = self.focusedControl()
		gap = border("gap")
		for ctrl in self.controls:
			if not ctrl.IsShown():
				continue
			rect = ctrl.GetRect()
			if ctrl is focused:
				width = border("focus")
				pen = wx.Pen(color("border.focus"), width)
			else:
				width = border("idle")
				pen = wx.Pen(color("border.idle"), width)
			dc.SetPen(pen)
			dc.SetBrush(wx.TRANSPARENT_BRUSH)
			inflate = gap - 1 + width // 2
			dc.DrawRectangle(rect.x - inflate, rect.y - inflate, rect.width + 2 * inflate, rect.height + 2 * inflate)
