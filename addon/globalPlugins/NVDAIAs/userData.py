# -*- coding: UTF-8 -*-
# NVDAIAs - userData.py
# Keeps the tokens and the conversation history across add-on updates.
# Copyright (C) 2026 Wellington Cruz
# This file is covered by the GNU General Public License, version 2.
#
# installTasks.onInstall copies the tokens and the history to NVDAIAs-backup
# before the update. Versions 1.0.0 to 1.4.0 delete the originals when NVDA
# removes them during the update; restoreAfterUpdate brings them back the first
# time the new version starts. Existing data is never overwritten.

import os
import shutil

from .credentials import FILE_NAME as CREDENTIALS_FILE
from .history import FOLDER_NAME as HISTORY_FOLDER

BACKUP_FOLDER = "NVDAIAs-backup"


def _hasHistory(folder):
	return os.path.isdir(folder) and any(name.endswith(".nvdaias") for name in os.listdir(folder))


def restoreAfterUpdate(configPath):
	"""Restores what is missing from the backup made during the update.

	Returns a tuple (tokensRestored, historyRestored).
	"""
	backup = os.path.join(configPath, BACKUP_FOLDER)
	if not os.path.isdir(backup):
		return False, False
	tokens = history = False
	src = os.path.join(backup, CREDENTIALS_FILE)
	dst = os.path.join(configPath, CREDENTIALS_FILE)
	if os.path.isfile(src) and not os.path.isfile(dst):
		shutil.copy2(src, dst)
		tokens = True
	srcHistory = os.path.join(backup, HISTORY_FOLDER)
	dstHistory = os.path.join(configPath, HISTORY_FOLDER)
	if _hasHistory(srcHistory):
		os.makedirs(dstHistory, exist_ok=True)
		for name in os.listdir(srcHistory):
			target = os.path.join(dstHistory, name)
			if name.endswith(".nvdaias") and not os.path.exists(target):
				shutil.copy2(os.path.join(srcHistory, name), target)
				history = True
	shutil.rmtree(backup, ignore_errors=True)
	return tokens, history
