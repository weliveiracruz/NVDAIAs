# -*- coding: UTF-8 -*-
"""Minimal fakes of the NVDA modules used by NVDAIAs, so the add-on can be
loaded and exercised outside NVDA (with a real wxPython).

gui.guiHelper is NVDA's real file (copied from the NVDA source, GPL-2), so the
dialogs are laid out exactly as in NVDA.
"""

import builtins
import inspect
import os
import sys
import tempfile
import types

import wx

HERE = os.path.dirname(os.path.abspath(__file__))
RECORD = {"spoken": [], "beeps": [], "browseable": [], "clipboard": [], "messageBoxes": [], "settingsOpened": []}
#: Answer that gui.messageBox returns (tests change it).
MESSAGEBOX_ANSWER = {"value": wx.OK}


def _module(name):
	mod = types.ModuleType(name)
	sys.modules[name] = mod
	return mod


def install(configPath=None):
	configPath = configPath or tempfile.mkdtemp(prefix="nvdaias-test-")

	# addonHandler ------------------------------------------------------------
	addonHandler = _module("addonHandler")

	lang = os.environ.get("NVDAIAS_LANG")
	if lang:
		import gettext
		localeDir = os.path.join(HERE, "..", "addon", "locale")
		translation = gettext.translation("nvda", localedir=localeDir, languages=[lang])
		gettextFunc = translation.gettext
	else:
		gettextFunc = lambda s: s  # noqa: E731

	def initTranslation():
		frame = inspect.currentframe().f_back
		frame.f_globals["_"] = gettextFunc
		frame.f_globals["ngettext"] = lambda s, p, n: s if n == 1 else p
		frame.f_globals["pgettext"] = lambda c, s: s

	addonHandler.initTranslation = initTranslation
	builtins._ = lambda s: s

	# globalVars ----------------------------------------------------------------
	globalVars = _module("globalVars")
	globalVars.appArgs = types.SimpleNamespace(configPath=configPath, secure=False)

	# config ------------------------------------------------------------------
	config = _module("config")

	class Conf(dict):
		def __init__(self):
			super().__init__()
			self.spec = {}

		def __getitem__(self, key):
			if not dict.__contains__(self, key):
				section = {}
				for k, v in self.spec[key].items():
					section[k] = _defaultFromSpec(v)
				dict.__setitem__(self, key, section)
			return dict.__getitem__(self, key)

	config.conf = Conf()

	# tones / ui / api ------------------------------------------------------------
	tones = _module("tones")
	tones.beep = lambda hz, ms, *a, **k: RECORD["beeps"].append((hz, ms))
	ui = _module("ui")
	ui.message = lambda text, *a, **k: RECORD["spoken"].append(text)

	def browseableMessage(message, title=None, isHtml=False, closeButton=False, copyButton=False):
		RECORD["browseable"].append((message, title, isHtml))

	ui.browseableMessage = browseableMessage
	api = _module("api")

	def copyToClip(text, notify=False):
		RECORD["clipboard"].append(text)
		return True

	api.copyToClip = copyToClip
	api._navigator = None
	api._foreground = None
	api.getNavigatorObject = lambda: api._navigator
	api.getForegroundObject = lambda: api._foreground

	# logHandler ---------------------------------------------------------------
	logHandler = _module("logHandler")

	class Log:
		def __getattr__(self, name):
			def f(msg, *a, **k):
				RECORD.setdefault("log", []).append("%s: %s" % (name, msg))
				if name in ("error", "exception"):
					RECORD.setdefault("logErrors", []).append(msg)
					if k.get("exc_info"):
						import traceback as _tb
						RECORD.setdefault("logTracebacks", []).append(_tb.format_exc())
			return f

	logHandler.log = Log()

	# scriptHandler ------------------------------------------------------------
	scriptHandler = _module("scriptHandler")

	def script(description=None, gesture=None, gestures=None, category=None, **kw):
		def deco(func):
			func.__doc__ = description
			func.gestures = [gesture] if gesture else list(gestures or [])
			func.category = category
			return func
		return deco

	scriptHandler.script = script

	# globalPluginHandler -------------------------------------------------------
	gph = _module("globalPluginHandler")

	class GlobalPlugin:
		def __init__(self):
			pass

		def terminate(self):
			pass

	gph.GlobalPlugin = GlobalPlugin

	# gui ---------------------------------------------------------------------
	gui = _module("gui")
	sys.path.insert(0, os.path.join(HERE, "nvda_real"))
	import importlib.util
	spec = importlib.util.spec_from_file_location("gui.guiHelper", os.path.join(HERE, "nvda_real", "guiHelper.py"))
	guiHelper = importlib.util.module_from_spec(spec)
	sys.modules["gui.guiHelper"] = guiHelper
	spec.loader.exec_module(guiHelper)
	gui.guiHelper = guiHelper

	nvdaControls = _module("gui.nvdaControls")

	class SelectOnFocusSpinCtrl(wx.SpinCtrl):
		pass

	nvdaControls.SelectOnFocusSpinCtrl = SelectOnFocusSpinCtrl
	gui.nvdaControls = nvdaControls

	settingsDialogs = _module("gui.settingsDialogs")

	class SettingsPanel(wx.Panel):
		title = ""

		def __init__(self, parent):
			super().__init__(parent)
			sizer = wx.BoxSizer(wx.VERTICAL)
			self.settingsSizer = wx.BoxSizer(wx.VERTICAL)
			self.makeSettings(self.settingsSizer)
			sizer.Add(self.settingsSizer, flag=wx.ALL, border=5)
			self.SetSizer(sizer)

	class NVDASettingsDialog:
		categoryClasses = []

	settingsDialogs.SettingsPanel = SettingsPanel
	settingsDialogs.NVDASettingsDialog = NVDASettingsDialog
	gui.settingsDialogs = settingsDialogs

	def messageBox(message, caption="", style=wx.OK, parent=None):
		RECORD["messageBoxes"].append(message)
		return MESSAGEBOX_ANSWER["value"]

	gui.messageBox = messageBox

	class MainFrame(wx.Frame):
		def __init__(self):
			super().__init__(None, title="NVDA")
			self.sysTrayIcon = types.SimpleNamespace(toolsMenu=wx.Menu(), Bind=lambda *a, **k: None)

		def prePopup(self):
			pass

		def postPopup(self):
			pass

		def popupSettingsDialog(self, dialog, *args, **kwargs):
			RECORD["settingsOpened"].append((dialog, args))

	gui.MainFrame = MainFrame
	gui.mainFrame = None  # created by the test after wx.App exists
	return configPath


def _defaultFromSpec(spec):
	import re
	m = re.search(r"default=([^,)]+)", spec)
	raw = m.group(1).strip() if m else ""
	if raw.startswith('"'):
		return raw.strip('"')
	if spec.startswith("boolean"):
		return raw == "True"
	if spec.startswith("integer"):
		return int(raw)
	return raw
