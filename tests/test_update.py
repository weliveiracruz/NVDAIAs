# -*- coding: UTF-8 -*-
"""Tests of add-on updates: tokens and history must survive an update and be
deleted only by a real uninstall (FUN-15 to FUN-19 in docs/SDD-TESTES.md).

NVDA removes the OLD version during an update and runs its onUninstall. These
tests reproduce that sequence with the real installTasks.py and userData.py.

Run: xvfb-run -a python3 tests/test_update.py
"""
import importlib
import os
import shutil
import sys
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
ADDON = os.path.join(ROOT, "addon")
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ADDON, "globalPlugins"))
sys.path.insert(0, ADDON)

import nvda_stubs  # noqa: E402
from _results import Recorder  # noqa: E402

CONFIG = nvda_stubs.install()
import wx  # noqa: E402

app = wx.App(False)
import gui  # noqa: E402

gui.mainFrame = gui.MainFrame()

# Fake of NVDA's add-on state (addonHandler.state / AddonStateCategory).
addonHandler = sys.modules["addonHandler"]
statusModule = types.ModuleType("addonStore.models.status")


class AddonStateCategory:
	PENDING_INSTALL = "pendingInstall"
	PENDING_REMOVE = "pendingRemove"


statusModule.AddonStateCategory = AddonStateCategory
for name in ("addonStore", "addonStore.models"):
	sys.modules.setdefault(name, types.ModuleType(name))
sys.modules["addonStore.models.status"] = statusModule
addonHandler.state = {AddonStateCategory.PENDING_INSTALL: set(), AddonStateCategory.PENDING_REMOVE: set()}

import installTasks  # noqa: E402
import NVDAIAs  # noqa: E402
from NVDAIAs import core, credentials, history, userData  # noqa: E402
from NVDAIAs.conversation import ChatEntry, Conversation  # noqa: E402

R = Recorder("updates (test_update)")

# onUninstall of versions 1.0.0 to 1.4.0 (deleted everything even during an update).
OLD_ON_UNINSTALL = '''
import os, shutil, globalVars
def onUninstall():
	path = os.path.join(globalVars.appArgs.configPath, "NVDAIAs-credentials.json")
	try:
		os.remove(path)
	except OSError:
		pass
	shutil.rmtree(os.path.join(globalVars.appArgs.configPath, "NVDAIAs-history"), ignore_errors=True)
'''


def oldOnUninstall():
	namespace = {}
	exec(compile(OLD_ON_UNINSTALL, "installTasks-1.4.0", "exec"), namespace)  # noqa: S102 - test fixture
	namespace["onUninstall"]()


def resetConfig():
	for name in os.listdir(CONFIG):
		path = os.path.join(CONFIG, name)
		shutil.rmtree(path) if os.path.isdir(path) else os.remove(path)
	core._store = None
	core._history = None
	addonHandler.state[AddonStateCategory.PENDING_INSTALL].clear()


def seedUserData():
	core.initConfig()
	core.store().set("gemini", "AIza-token-do-usuario")
	conv = Conversation()
	conv.add(ChatEntry("user", "Pergunta guardada"))
	conv.add(ChatEntry("assistant", "Resposta guardada", providerName="Gemini"))
	core.history().save(conv.toDict())
	return conv.id


def userDataIntact(convId):
	core._store = None
	core._history = None
	token = credentials.CredentialStore(CONFIG).get("gemini")
	ids = [d["id"] for d in history.HistoryStore(CONFIG).list()]
	return token == "AIza-token-do-usuario" and convId in ids


def startNewVersion():
	"""What NVDA does when the new version starts: creates the global plugin."""
	plugin = NVDAIAs.GlobalPlugin()
	plugin.terminate()


def run():
	pendingDir = os.path.join(CONFIG, "addons", "NVDAIAs" + installTasks._PENDING_INSTALL_SUFFIX)

	# FUN-15 real uninstall deletes everything
	resetConfig()
	seedUserData()
	installTasks.onInstall()
	installTasks.onUninstall()
	R.check("FUN-15 real uninstall deletes the tokens", not os.path.exists(os.path.join(CONFIG, credentials.FILE_NAME)))
	R.check("FUN-15 real uninstall deletes the history", not os.path.exists(os.path.join(CONFIG, history.FOLDER_NAME)))
	R.check("FUN-15 real uninstall deletes the update copy", not os.path.exists(os.path.join(CONFIG, userData.BACKUP_FOLDER)))

	# FUN-16 update detected by the pending install folder
	resetConfig()
	convId = seedUserData()
	os.makedirs(pendingDir)
	R.check("FUN-16 update detected by the new version folder", installTasks.isUpdate())
	installTasks.onUninstall()
	R.check("FUN-16 update keeps tokens and history", userDataIntact(convId))
	shutil.rmtree(pendingDir)

	# FUN-16 update detected by NVDA's add-on state
	resetConfig()
	convId = seedUserData()
	addonHandler.state[AddonStateCategory.PENDING_INSTALL].add("NVDAIAs")
	R.check("FUN-16 update detected by NVDA's pending install state", installTasks.isUpdate())
	installTasks.onUninstall()
	R.check("FUN-16 update (state) keeps tokens and history", userDataIntact(convId))
	addonHandler.state[AddonStateCategory.PENDING_INSTALL].clear()
	R.check("FUN-16 without a new version it is not an update", not installTasks.isUpdate())

	# FUN-17 update from 1.0.0-1.4.0: their onUninstall deletes everything
	resetConfig()
	convId = seedUserData()
	installTasks.onInstall()  # the new version is installed (before restart)
	backup = os.path.join(CONFIG, userData.BACKUP_FOLDER)
	R.check("FUN-17 installing makes a copy of tokens and history", os.path.isfile(os.path.join(backup, credentials.FILE_NAME)) and os.listdir(os.path.join(backup, history.FOLDER_NAME)))
	oldOnUninstall()  # NVDA restarts and removes the old version
	R.check("FUN-17 (precondition) the old version deleted the data", not os.path.exists(os.path.join(CONFIG, credentials.FILE_NAME)))
	startNewVersion()
	R.check("FUN-17 the new version restores tokens and history", userDataIntact(convId))
	R.check("FUN-17 the copy is removed after restoring", not os.path.exists(backup))

	# FUN-18 restore never overwrites newer data
	resetConfig()
	convId = seedUserData()
	installTasks.onInstall()
	core.store().set("gemini", "AIza-token-NOVO")
	userData.restoreAfterUpdate(CONFIG)
	core._store = None
	R.check("FUN-18 restore does not overwrite a token saved later", credentials.CredentialStore(CONFIG).get("gemini") == "AIza-token-NOVO")

	# FUN-19 fresh install / failures
	resetConfig()
	installTasks.onInstall()
	R.check("FUN-19 first install (no data) makes no copy", not os.path.exists(os.path.join(CONFIG, userData.BACKUP_FOLDER)))
	startNewVersion()
	R.check("FUN-19 first start without copy works (no error, no token invented)", not nvda_stubs.RECORD.get("logErrors") and not credentials.CredentialStore(CONFIG).has("gemini"))
	resetConfig()
	seedUserData()
	with open(os.path.join(CONFIG, userData.BACKUP_FOLDER), "w") as f:
		f.write("a file where the folder should be")
	try:
		installTasks.onInstall()
		ok = True
	except Exception:
		ok = False
	R.check("FUN-19 a failed copy never blocks the installation", ok)
	os.remove(os.path.join(CONFIG, userData.BACKUP_FOLDER))

	# FUN-17 also with the update sequence of this version (data kept, copy cleaned)
	resetConfig()
	convId = seedUserData()
	installTasks.onInstall()
	os.makedirs(pendingDir)
	installTasks.onUninstall()
	shutil.rmtree(pendingDir)
	startNewVersion()
	R.check("FUN-17 update from 1.5.0 on: data kept and copy cleaned", userDataIntact(convId) and not os.path.exists(os.path.join(CONFIG, userData.BACKUP_FOLDER)))


try:
	run()
except Exception:
	import traceback
	traceback.print_exc()
	R.check("suite ran to the end", False, "exception")
sys.exit(R.finish())
