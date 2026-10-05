# -*- coding: UTF-8 -*-
# NVDAIAs - feedback.py
# "Send feedback" button: asks for confirmation and opens the feedback form in the browser.
# Copyright (C) 2026 Wellington Cruz
# This file is covered by the GNU General Public License, version 2.

import webbrowser

import addonHandler
import gui
import ui
import wx

addonHandler.initTranslation()

#: Feedback form (Google Forms). Only this fixed HTTPS address is ever opened.
FEEDBACK_URL = "https://docs.google.com/forms/d/e/1FAIpQLSdlYqyagfsOykxCdLLjBlUGm2vG7HxAkVH7cXl3vEWigRt3zg/viewform?usp=publish-editor"


def confirm(parent, message, caption, okLabel, cancelLabel):
	"""Standard Windows message box with the buttons renamed, so NVDA reads the
	title and the message as soon as it opens. Returns True for the OK button."""
	dlg = wx.MessageDialog(parent, message, caption, wx.OK | wx.CANCEL | wx.OK_DEFAULT | wx.ICON_INFORMATION)
	try:
		dlg.SetOKCancelLabels(okLabel, cancelLabel)
		return dlg.ShowModal() == wx.ID_OK
	finally:
		dlg.Destroy()


def openBrowser(url):
	"""Opens the address in a new tab of the default browser."""
	return webbrowser.open(url, new=2)


def askAndOpen(parent=None):
	"""Shows the confirmation and opens the form. Returns True when it was opened."""
	parent = parent or gui.mainFrame
	if not confirm(
		parent,
		# Translators: message of the window shown before opening the feedback form.
		_("The evaluation will open in a new tab of your browser."),
		# Translators: title of the window shown before opening the feedback form.
		_("NVDAIAs - Send feedback"),
		# Translators: button that opens the feedback form in the browser.
		_("Give &feedback"),
		# Translators: button that closes the feedback window without opening the form.
		_("&Cancel"),
	):
		return False
	try:
		opened = openBrowser(FEEDBACK_URL)
	except Exception:
		opened = False
	if opened is False:
		# Translators: shown when the browser could not be opened. {url} is the address of the form.
		gui.messageBox(_("Could not open the browser. Open this address manually: {url}").format(url=FEEDBACK_URL), "NVDAIAs", wx.OK | wx.ICON_WARNING, parent)
		return False
	# Translators: announced after opening the feedback form.
	ui.message(_("Opening the feedback form in your browser"))
	return True
