# -*- coding: UTF-8 -*-
# NVDAIAs - installTasks.py
# Copyright (C) 2026 Wellington Cruz
# This file is covered by the GNU General Public License, version 2.

import os

import globalVars

# Must match credentials.FILE_NAME
_CREDENTIALS_FILE = "NVDAIAs-credentials.json"


def onUninstall():
	"""Removes the saved tokens when the add-on is uninstalled."""
	path = os.path.join(globalVars.appArgs.configPath, _CREDENTIALS_FILE)
	try:
		os.remove(path)
	except OSError:
		pass
