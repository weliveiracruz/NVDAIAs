# -*- coding: UTF-8 -*-
# NVDAIAs - global plugin
# Chat with ChatGPT, Gemini or Claude from NVDA.
# Copyright (C) 2026 Wellington Cruz <weliveiracruz@gmail.com>
# This file is covered by the GNU General Public License, version 2.
# See the file COPYING for more details.

import addonHandler
import api
import globalPluginHandler
import globalVars
import gui
import ui
import wx
from logHandler import log
from scriptHandler import script

from . import core

addonHandler.initTranslation()

# Translators: category of the NVDAIAs commands in the Input gestures dialog.
SCRIPT_CATEGORY = _("NVDAIAs")


def disableInSecureMode(cls):
	"""Does not load the add-on on secure screens (logon, UAC), as recommended by NV Access."""
	if globalVars.appArgs.secure:
		return globalPluginHandler.GlobalPlugin
	return cls


@disableInSecureMode
class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	scriptCategory = SCRIPT_CATEGORY

	def __init__(self):
		super().__init__()
		core.initConfig()
		self.session = core.ChatSession()
		from .settingsPanel import NVDAIAsSettingsPanel

		self._settingsPanelClass = NVDAIAsSettingsPanel
		gui.settingsDialogs.NVDASettingsDialog.categoryClasses.append(NVDAIAsSettingsPanel)
		self._menuItem = None
		try:
			toolsMenu = gui.mainFrame.sysTrayIcon.toolsMenu
			self._menuItem = toolsMenu.Append(
				wx.ID_ANY,
				# Translators: item of the NVDA Tools menu.
				_("NVDAIAs - &Chat with AI…"),
				# Translators: help text of the Tools menu item.
				_("Opens the NVDAIAs window to chat with ChatGPT, Gemini or Claude"),
			)
			gui.mainFrame.sysTrayIcon.Bind(wx.EVT_MENU, lambda evt: self.openChat(), self._menuItem)
		except Exception:
			log.debugWarning("NVDAIAs: could not add the Tools menu item", exc_info=True)

	def terminate(self):
		from .chatDialog import ChatDialog

		try:
			ChatDialog.closeInstance()
		except Exception:
			pass
		self.session.terminate()
		try:
			gui.settingsDialogs.NVDASettingsDialog.categoryClasses.remove(self._settingsPanelClass)
		except ValueError:
			pass
		if self._menuItem is not None:
			try:
				gui.mainFrame.sysTrayIcon.toolsMenu.Remove(self._menuItem)
			except Exception:
				pass
		super().terminate()

	# Actions -------------------------------------------------------------------

	def openChat(self, then=None):
		from .chatDialog import ChatDialog

		def show():
			dlg = ChatDialog.showInstance(self.session)
			if not core.connectedProviders():
				# First use: open the login (token) screen right away.
				dlg._runConnect()
				dlg.questionEdit.SetFocus()
			if then:
				then(dlg)

		wx.CallAfter(show)

	def describeRect(self, rect, what):
		try:
			png = _captureForAI(rect)
		except Exception:
			log.error("NVDAIAs: screen capture failed", exc_info=True)
			# Translators: error when the screenshot fails.
			ui.message(_("Could not capture the screen"))
			return
		# Translators: question sent with a screenshot. {what} describes what was captured.
		question = _("Describe this image for a blind person ({what}). Start with a short overview, then describe "
			"the important elements, any visible text and how they are arranged."
		).format(what=what)

		def send(dlg):
			providerId = core.conf()["provider"]
			if not core.store().has(providerId):
				if not dlg._runConnect(providerId):
					return
				providerId = core.conf()["provider"]
			if self.session.busy:
				# Translators: announced when a question is already being answered.
				ui.message(_("Please wait for the current answer"))
				return
			try:
				from .attachments import Attachment
				# Translators: file name given to screenshots sent to the AI.
				shot = Attachment.image(png, name=_("screenshot.png"))
				self.session.send(question, providerId=providerId, attachments=[shot])
			except core.NoTokenError:
				return
			# Translators: announced after sending the screenshot.
			ui.message(_("Image sent, waiting for the description"))

		self.openChat(then=send)

	# Scripts -------------------------------------------------------------------

	@script(
		# Translators: description of the command that opens the chat window.
		description=_("Opens the NVDAIAs window to chat with ChatGPT, Gemini or Claude"),
		gesture="kb:NVDA+alt+i",
	)
	def script_openChat(self, gesture):
		self.openChat()

	@script(
		# Translators: description of the command that describes the navigator object.
		description=_("Sends an image of the current navigator object to the AI and reads its description"),
		gesture="kb:NVDA+alt+d",
	)
	def script_describeNavigator(self, gesture):
		obj = api.getNavigatorObject()
		location = getattr(obj, "location", None) if obj else None
		if not location or location[2] <= 0 or location[3] <= 0:
			# Translators: announced when the navigator object has no position on screen.
			ui.message(_("This object has no position on the screen"))
			return
		name = (getattr(obj, "name", None) or "").strip()
		try:
			role = obj.roleText or ""
		except Exception:
			role = ""
		# Translators: describes the captured area. {name} and {role} come from NVDA.
		what = _("screen element: {name} {role}").format(name=name, role=role).strip()
		self.describeRect(tuple(location), what)

	@script(
		# Translators: description of the command that describes the whole screen.
		description=_("Sends an image of the whole screen (current monitor) to the AI and reads its description"),
		gesture="kb:NVDA+shift+alt+d",
	)
	def script_describeScreen(self, gesture):
		from .screenshot import monitorRectAt

		fg = api.getForegroundObject()
		loc = getattr(fg, "location", None) if fg else None
		x, y = (loc[0] + loc[2] // 2, loc[1] + loc[3] // 2) if loc else (0, 0)
		# Translators: describes the captured area (whole screen).
		self.describeRect(monitorRectAt(x, y), _("whole screen"))

	@script(
		# Translators: description of the command that opens the settings.
		description=_("Opens the NVDAIAs settings"),
	)
	def script_openSettings(self, gesture):
		from .settingsPanel import openSettings

		openSettings()


def _captureForAI(rect):
	from .screenshot import captureRect

	left, top, width, height = rect
	return captureRect(left, top, width, height)
