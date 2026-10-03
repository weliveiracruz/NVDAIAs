# -*- coding: UTF-8 -*-
# NVDAIAs - installTasks.py
# Copyright (C) 2026 Wellington Cruz
# This file is covered by the GNU General Public License, version 2.

import os

import globalVars

import shutil

# Must match credentials.FILE_NAME and history.FOLDER_NAME
_CREDENTIALS_FILE = "NVDAIAs-credentials.json"
_HISTORY_FOLDER = "NVDAIAs-history"


def onUninstall():
	"""Removes the saved tokens and conversations when the add-on is uninstalled."""
	path = os.path.join(globalVars.appArgs.configPath, _CREDENTIALS_FILE)
	try:
		os.remove(path)
	except OSError:
		pass
	shutil.rmtree(os.path.join(globalVars.appArgs.configPath, _HISTORY_FOLDER), ignore_errors=True)
