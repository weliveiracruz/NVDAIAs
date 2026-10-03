# -*- coding: UTF-8 -*-
# NVDAIAs - screenshot.py
# Captures a part of the screen as PNG, to be described by the AI.
# Copyright (C) 2026 Wellington Cruz
# This file is covered by the GNU General Public License, version 2.

import io

import wx

#: Images are reduced so that the longest side has at most this many pixels
#: (keeps uploads small and within the limits of the three APIs).
MAX_SIDE = 1568


def captureRect(left, top, width, height, maxSide=MAX_SIDE):
	"""Returns the PNG bytes of the given screen rectangle (physical pixels)."""
	width = int(width)
	height = int(height)
	if width <= 0 or height <= 0:
		raise ValueError("empty rectangle")
	screen = wx.ScreenDC()
	bmp = wx.Bitmap(width, height)
	mem = wx.MemoryDC(bmp)
	try:
		mem.Blit(0, 0, width, height, screen, int(left), int(top))
	finally:
		mem.SelectObject(wx.NullBitmap)
	img = bmp.ConvertToImage()
	longest = max(width, height)
	if longest > maxSide:
		factor = maxSide / float(longest)
		img = img.Scale(max(1, int(width * factor)), max(1, int(height * factor)), wx.IMAGE_QUALITY_HIGH)
	stream = io.BytesIO()
	if not img.SaveFile(stream, wx.BITMAP_TYPE_PNG):
		raise RuntimeError("could not encode PNG")
	return stream.getvalue()


def monitorRectAt(x, y):
	"""Geometry (left, top, width, height) of the monitor containing the point."""
	index = wx.Display.GetFromPoint(wx.Point(int(x), int(y)))
	if index == wx.NOT_FOUND:
		index = 0
	rect = wx.Display(index).GetGeometry()
	return rect.x, rect.y, rect.width, rect.height
