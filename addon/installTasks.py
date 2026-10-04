# -*- coding: UTF-8 -*-
# NVDAIAs - installTasks.py
# Copyright (C) 2026 Wellington Cruz
# This file is covered by the GNU General Public License, version 2.
#
# NVDA runs onUninstall of the OLD version also when the add-on is UPDATED
# (the old copy is removed at the next restart). So:
# * onUninstall only deletes the tokens and the history on a real uninstall,
#   never during an update;
# * onInstall keeps a copy of them, because versions 1.0.0 to 1.4.0 deleted them
#   in their onUninstall even during an update. The new version restores the copy
#   when it starts (see globalPlugins/NVDAIAs/userData.py).

import os
import shutil

import globalVars

ADDON_NAME = "NVDAIAs"
# Must match credentials.FILE_NAME, history.FOLDER_NAME and userData.BACKUP_FOLDER
_CREDENTIALS_FILE = "NVDAIAs-credentials.json"
_HISTORY_FOLDER = "NVDAIAs-history"
_BACKUP_FOLDER = "NVDAIAs-backup"
_PENDING_INSTALL_SUFFIX = ".pendingInstall"


def _configPath():
	return globalVars.appArgs.configPath


def onInstall():
	"""Runs as soon as this version is installed, before NVDA restarts."""
	cfg = _configPath()
	credentials = os.path.join(cfg, _CREDENTIALS_FILE)
	history = os.path.join(cfg, _HISTORY_FOLDER)
	if not os.path.isfile(credentials) and not os.path.isdir(history):
		return
	backup = os.path.join(cfg, _BACKUP_FOLDER)
	try:
		shutil.rmtree(backup, ignore_errors=True)
		os.makedirs(backup)
		if os.path.isfile(credentials):
			shutil.copy2(credentials, os.path.join(backup, _CREDENTIALS_FILE))
		if os.path.isdir(history):
			shutil.copytree(history, os.path.join(backup, _HISTORY_FOLDER))
	except Exception:
		# A failed copy must never block the installation.
		pass


def isUpdate():
	"""True when NVDA is removing the old version because a new one was installed."""
	cfg = _configPath()
	if os.path.isdir(os.path.join(cfg, "addons", ADDON_NAME + _PENDING_INSTALL_SUFFIX)):
		return True
	try:
		import addonHandler
		from addonStore.models.status import AddonStateCategory

		return ADDON_NAME in addonHandler.state[AddonStateCategory.PENDING_INSTALL]
	except Exception:
		return False


def onUninstall():
	"""Deletes the saved tokens and conversations only when the add-on is really
	uninstalled. During an update they are kept for the new version."""
	if isUpdate():
		return
	cfg = _configPath()
	try:
		os.remove(os.path.join(cfg, _CREDENTIALS_FILE))
	except OSError:
		pass
	shutil.rmtree(os.path.join(cfg, _HISTORY_FOLDER), ignore_errors=True)
	shutil.rmtree(os.path.join(cfg, _BACKUP_FOLDER), ignore_errors=True)
