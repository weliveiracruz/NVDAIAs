# -*- coding: UTF-8 -*-
# NVDAIAs - chatDialog.py
# The chat window: question field, conversation list and buttons.
# Copyright (C) 2026 Wellington Cruz
# This file is covered by the GNU General Public License, version 2.
#
# Tab order (Shift+Tab from the question field goes straight to the conversation list):
#   AI combo box > Model > Conversation list > Question > Send > ... > Close

import os
import time

import addonHandler
import api
import gui
import ui
import wx
from gui import guiHelper

from . import core, history, textutils, theme
from .conversation import ChatEntry
from .connectDialog import ConnectDialog
from .providers import PROVIDER_IDS, getProviderClass

addonHandler.initTranslation()

#: Max characters shown in one list item. The full text is shown with Enter.
LIST_ITEM_LIMIT = 6000


def showMessageText(entry, title):
	"""Opens a message in an NVDA browseable window (navigable with the arrows)."""
	htmlText = textutils.toHtml(entry.text)
	try:
		ui.browseableMessage(htmlText, title, True, closeButton=True, copyButton=True)
	except TypeError:  # NVDA older than 2025.1
		ui.browseableMessage(htmlText, title, True)


def copyText(text):
	try:
		ok = api.copyToClip(text, notify=False)
	except TypeError:
		ok = api.copyToClip(text)
	if ok is not False:
		# Translators: announced after copying a message.
		ui.message(_("Copied to the clipboard"))


class ChatDialog(wx.Dialog):
	_instance = None

	@classmethod
	def showInstance(cls, session, focusQuestion=True):
		"""Shows the single chat window, creating it when needed."""
		dlg = cls._instance
		if dlg is None or not dlg:
			gui.mainFrame.prePopup()
			dlg = cls(gui.mainFrame, session)
			cls._instance = dlg
			dlg.Show()
			gui.mainFrame.postPopup()
		else:
			dlg.Show()
			dlg.Raise()
		if focusQuestion:
			dlg.questionEdit.SetFocus()
		return dlg

	@classmethod
	def closeInstance(cls):
		dlg = cls._instance
		cls._instance = None
		if dlg:
			dlg.Destroy()

	def __init__(self, parent, session):
		# Translators: title of the chat window.
		super().__init__(parent, title=_("NVDAIAs - Chat with AI"), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER | wx.MAXIMIZE_BOX)
		self.session = session
		self.themed = theme.isEnabled()
		mainSizer = wx.BoxSizer(wx.VERTICAL)
		if self.themed:
			# Translators: subtitle shown in the coloured header of the chat window.
			self.header = theme.HeaderPanel(self, "NVDAIAs", _("Chat with ChatGPT, Gemini and Claude"))
			mainSizer.Add(self.header, flag=wx.EXPAND)
		sHelper = guiHelper.BoxSizerHelper(self, orientation=wx.VERTICAL)

		self.statusLine = sHelper.addItem(theme.StatusLine(self), flag=wx.EXPAND)
		gapS = theme.space("sm")
		gapL = theme.space("lg")

		# AI and model side by side. Creation order = tab order: AI, Model.
		selectors = wx.BoxSizer(wx.HORIZONTAL)
		# Translators: label of the combo box to choose the AI (ChatGPT, Gemini or Claude).
		aiHelper = guiHelper.LabeledControlHelper(self, _("&AI:"), wx.Choice, choices=[core.providerLabel(p) for p in PROVIDER_IDS])
		self.providerChoice = aiHelper.control
		self.providerChoice.SetSelection(PROVIDER_IDS.index(core.conf()["provider"]))
		self.providerChoice.Bind(wx.EVT_CHOICE, self.onProviderChanged)
		selectors.Add(aiHelper.sizer, flag=wx.ALIGN_CENTER_VERTICAL)
		selectors.AddSpacer(gapL * 2)
		# Translators: label of the editable combo box with the AI model.
		modelHelper = guiHelper.LabeledControlHelper(self, _("&Model:"), wx.ComboBox, style=wx.CB_DROPDOWN, size=(260, -1))
		self.modelCombo = modelHelper.control
		self.modelCombo.Bind(wx.EVT_KILL_FOCUS, self.onModelKillFocus)
		self.modelCombo.Bind(wx.EVT_COMBOBOX, lambda evt: self._saveModel())
		selectors.Add(modelHelper.sizer, flag=wx.ALIGN_CENTER_VERTICAL)
		sHelper.addItem(selectors)

		# Conversation: label above, list fills the window.
		# Translators: label of the list with the messages of the conversation.
		conversationLabel = wx.StaticText(self, label=_("Con&versation:"))
		# A tree: the first item, "Previous conversations", starts collapsed; each
		# previous conversation is a collapsed branch with its messages; the
		# messages of the current conversation follow at the top level.
		self.conversationTree = wx.TreeCtrl(
			self,
			style=wx.TR_HIDE_ROOT | wx.TR_HAS_BUTTONS | wx.TR_LINES_AT_ROOT | wx.TR_SINGLE,
			size=(720, 280),
		)
		self._root = self.conversationTree.AddRoot("root")
		self._historyNode = None
		self._historyData = {}
		self.conversationTree.Bind(wx.EVT_TREE_ITEM_EXPANDING, self.onTreeExpanding)
		self.conversationTree.Bind(wx.EVT_TREE_ITEM_ACTIVATED, lambda evt: self.onTreeActivate())
		conversationBox = wx.BoxSizer(wx.VERTICAL)
		conversationBox.Add(conversationLabel)
		conversationBox.AddSpacer(gapS)
		conversationBox.Add(self.conversationTree, proportion=1, flag=wx.EXPAND)
		sHelper.addItem(conversationBox, proportion=1, flag=wx.EXPAND)

		# Question: label above, field and Send button on the same row (chat layout).
		# Translators: label of the field where the user types the question.
		questionLabel = wx.StaticText(self, label=_("&Question (Enter sends, Shift+Enter adds a new line):"))
		self.questionEdit = wx.TextCtrl(self, style=wx.TE_MULTILINE, size=(-1, 90))
		# Translators: button that sends the question.
		self.sendButton = wx.Button(self, label=_("&Send"), size=(110, -1))
		self.sendButton.Bind(wx.EVT_BUTTON, self.onSend)
		questionRow = wx.BoxSizer(wx.HORIZONTAL)
		questionRow.Add(self.questionEdit, proportion=1, flag=wx.EXPAND)
		questionRow.AddSpacer(gapL)
		questionRow.Add(self.sendButton, flag=wx.EXPAND)
		questionBox = wx.BoxSizer(wx.VERTICAL)
		questionBox.Add(questionLabel)
		questionBox.AddSpacer(gapS)
		questionBox.Add(questionRow, flag=wx.EXPAND)
		sHelper.addItem(questionBox, flag=wx.EXPAND)

		row1 = guiHelper.ButtonHelper(wx.HORIZONTAL)
		# Translators: button that cancels the question being sent.
		self.cancelButton = row1.addButton(self, label=_("Cance&l sending"))
		self.cancelButton.Bind(wx.EVT_BUTTON, self.onCancelSend)
		# Translators: button that opens the selected message in a reading window.
		self.readButton = row1.addButton(self, label=_("&Read message"))
		self.readButton.Bind(wx.EVT_BUTTON, self.onReadMessage)
		# Translators: button that copies the selected message.
		self.copyButton = row1.addButton(self, label=_("C&opy message"))
		self.copyButton.Bind(wx.EVT_BUTTON, self.onCopyMessage)
		sHelper.addItem(row1)

		row2 = guiHelper.ButtonHelper(wx.HORIZONTAL)
		# Translators: button that clears the conversation.
		self.newButton = row2.addButton(self, label=_("&New conversation"))
		self.newButton.Bind(wx.EVT_BUTTON, self.onNewConversation)
		# Translators: button that saves the conversation to a text file.
		self.saveButton = row2.addButton(self, label=_("Sav&e conversation…"))
		self.saveButton.Bind(wx.EVT_BUTTON, self.onSaveConversation)
		# Translators: button that opens the connect account (token) screen.
		self.connectButton = row2.addButton(self, label=_("Connec&t account…"))
		self.connectButton.Bind(wx.EVT_BUTTON, self.onConnect)
		# Translators: button that opens the NVDAIAs settings.
		self.settingsButton = row2.addButton(self, label=_("Settin&gs…"))
		self.settingsButton.Bind(wx.EVT_BUTTON, self.onSettings)
		# Translators: button that closes the chat window.
		self.closeButton = row2.addButton(self, id=wx.ID_CLOSE, label=_("&Close"))
		self.closeButton.Bind(wx.EVT_BUTTON, lambda evt: self.Close())
		sHelper.addItem(row2)

		mainSizer.Add(sHelper.sizer, proportion=1, border=guiHelper.BORDER_FOR_DIALOGS + (theme.space("xs") if self.themed else 0), flag=wx.ALL | wx.EXPAND)
		if self.themed:
			theme.applyColors(self, bodyControls=(self.conversationTree, self.questionEdit, self.modelCombo))
			self.focusFrames = theme.FocusFrames(self, (self.providerChoice, self.modelCombo, self.conversationTree, self.questionEdit))
		self.SetSizer(mainSizer)
		mainSizer.Fit(self)
		width, height = self.GetSize()
		self.SetMinSize((min(width, 640), min(height, 520)))
		self.SetSize((max(width, 860), max(height, 700)))
		self.SetEscapeId(wx.ID_CLOSE)
		# EVT_CHAR_HOOK sees the keys before Windows dialog navigation, so Enter
		# reaches the question field and the list reliably.
		self.Bind(wx.EVT_CHAR_HOOK, self.onCharHook)
		self.Bind(wx.EVT_CLOSE, self.onClose)
		self.CentreOnScreen()

		self._fillModels()
		self.session.listeners.append(self)
		self.session.conversation.listeners.append(self.refreshList)
		self.rebuildHistory()
		self.refreshList()
		self.onBusyChanged(self.session.busy)

	# Helpers -----------------------------------------------------------------

	@property
	def providerId(self):
		return PROVIDER_IDS[self.providerChoice.GetSelection()]

	def _fillModels(self):
		providerId = self.providerId
		cls = getProviderClass(providerId)
		current = core.getModel(providerId)
		choices = list(core.modelCache.get(providerId) or cls.suggestedModels)
		if current not in choices:
			choices.insert(0, current)
		self.modelCombo.Set(choices)
		self.modelCombo.SetValue(current)

	def _saveModel(self):
		value = self.modelCombo.GetValue().strip()
		if value:
			core.setModel(self.providerId, value)
			if hasattr(self, "statusLine"):
				self.updateStatus()

	def _entryLabel(self, entry):
		if entry.role == "user":
			# Translators: prefix of the user's messages in the conversation list.
			who = _("You")
		else:
			who = entry.providerName
		text = textutils.toPlainText(entry.text) if core.conf()["stripMarkdown"] else entry.text
		if entry.image:
			# Translators: shown in a message that carries a screenshot.
			text = _("[image attached]") + " " + text
		return "%s: %s" % (who, textutils.oneLine(text, LIST_ITEM_LIMIT))

	# Tree ----------------------------------------------------------------------

	def selectedData(self):
		item = self.conversationTree.GetSelection()
		if not item.IsOk() or item == self._root:
			return None
		return self.conversationTree.GetItemData(item)

	def selectedEntry(self):
		"""ChatEntry of the selected message (current or previous conversation)."""
		data = self.selectedData()
		if not data or data[0] != "msg":
			return None
		convId, index = data[1], data[2]
		if convId is None:
			entries = self.session.conversation.entries
			return entries[index] if 0 <= index < len(entries) else None
		saved = self._historyData.get(convId)
		if not saved:
			return None
		entries = saved.get("entries") or []
		return ChatEntry.fromDict(entries[index]) if 0 <= index < len(entries) else None

	def _conversationLabel(self, data):
		title, providers, count, updated = history.summary(data)
		# Translators: date format of the previous conversations (Python strftime).
		stamp = time.strftime(_("%Y-%m-%d %H:%M"), time.localtime(updated))
		# Translators: one previous conversation in the tree. {date}, {ais} (e.g. Claude, Gemini), {title} (first question) and {count} (messages).
		return _("{date} · {ais} · {title} ({count} messages)").format(date=stamp, ais=", ".join(providers) or "-", title=title, count=count)

	def rebuildHistory(self):
		"""(Re)creates the "Previous conversations" branch, keeping what was expanded."""
		tree = self.conversationTree
		if not core.conf()["saveHistory"]:
			if self._historyNode is not None:
				tree.Delete(self._historyNode)
				self._historyNode = None
			self._historyData = {}
			return
		wasExpanded = self._historyNode is not None and tree.IsExpanded(self._historyNode)
		expandedIds = set()
		if self._historyNode is not None:
			child, cookie = tree.GetFirstChild(self._historyNode)
			while child.IsOk():
				if tree.IsExpanded(child):
					expandedIds.add(tree.GetItemData(child)[1])
				child, cookie = tree.GetNextChild(self._historyNode, cookie)
			tree.DeleteChildren(self._historyNode)
		else:
			first, _cookie = tree.GetFirstChild(self._root)
			if first.IsOk():
				self._historyNode = tree.InsertItem(self._root, 0, "")
			else:
				self._historyNode = tree.AppendItem(self._root, "")
			tree.SetItemData(self._historyNode, ("history",))
		previous = self.session.previousConversations()
		self._historyData = {d["id"]: d for d in previous}
		# Translators: first item of the conversation tree. {count} is the number of saved conversations.
		tree.SetItemText(self._historyNode, _("Previous conversations ({count})").format(count=len(previous)))
		for data in previous:
			node = tree.AppendItem(self._historyNode, self._conversationLabel(data))
			tree.SetItemData(node, ("conv", data["id"]))
			# Placeholder so the branch can be expanded; messages are added on expansion.
			placeholder = tree.AppendItem(node, "…")
			tree.SetItemData(placeholder, ("placeholder",))
			if data["id"] in expandedIds:
				self._fillConversationNode(node)
				tree.Expand(node)
		if wasExpanded and previous:
			tree.Expand(self._historyNode)

	def _fillConversationNode(self, node):
		tree = self.conversationTree
		convId = tree.GetItemData(node)[1]
		tree.DeleteChildren(node)
		data = self._historyData.get(convId) or {}
		for index, raw in enumerate(data.get("entries") or []):
			child = tree.AppendItem(node, self._entryLabel(ChatEntry.fromDict(raw)))
			tree.SetItemData(child, ("msg", convId, index))

	def onTreeExpanding(self, evt):
		item = evt.GetItem()
		data = self.conversationTree.GetItemData(item) if item.IsOk() else None
		if data and data[0] == "conv":
			first, _cookie = self.conversationTree.GetFirstChild(item)
			if first.IsOk() and self.conversationTree.GetItemData(first) == ("placeholder",):
				self._fillConversationNode(item)
		evt.Skip()

	# Session / conversation listeners ------------------------------------------

	def refreshList(self):
		"""Rebuilds the messages of the current conversation (top level, after the history item)."""
		if not self:
			return
		tree = self.conversationTree
		toDelete = []
		child, cookie = tree.GetFirstChild(self._root)
		while child.IsOk():
			if child != self._historyNode:
				toDelete.append(child)
			child, cookie = tree.GetNextChild(self._root, cookie)
		for item in toDelete:
			tree.Delete(item)
		last = None
		for index, entry in enumerate(self.session.conversation.entries):
			last = tree.AppendItem(self._root, self._entryLabel(entry))
			tree.SetItemData(last, ("msg", None, index))
		if self.session.busy:
			name = getProviderClass(core.conf()["provider"]).name
			# Translators: last item of the conversation while waiting. {name} is ChatGPT, Gemini or Claude.
			last = tree.AppendItem(self._root, _("{name} is answering…").format(name=name))
			tree.SetItemData(last, ("busy",))
		if last is not None:
			tree.SelectItem(last)
			tree.EnsureVisible(last)
		elif self._historyNode is not None:
			tree.SelectItem(self._historyNode)
		self._updateButtons()

	def onHistoryChanged(self):
		if not self:
			return
		self.rebuildHistory()
		self.refreshList()

	def onBusyChanged(self, busy):
		if not self:
			return
		self.refreshList()

	def onAnswer(self, entry):
		if not self:
			return
		self.refreshList()

	def onError(self, message, questionText):
		if not self:
			return
		self.refreshList()
		self.updateStatus(errorText=message)
		# Give the question back so the user can try again.
		if not self.questionEdit.GetValue().strip():
			self.questionEdit.SetValue(questionText)
			self.questionEdit.SetInsertionPointEnd()

	def updateStatus(self, errorText=None):
		providerId = self.providerId
		name = getProviderClass(providerId).name
		model = core.getModel(providerId)
		if errorText:
			# Translators: status line after an error. {name} is the AI.
			self.statusLine.setStatus(_("{name} · the last question failed, it is back in the Question field").format(name=name), "error")
		elif self.session.busy:
			# Translators: status line while waiting. {name} is the AI, {model} the model.
			self.statusLine.setStatus(_("{name} · {model} · answering…").format(name=name, model=model), "busy")
		elif core.store().has(providerId):
			# Translators: status line when the AI is connected. {name} is the AI, {model} the model.
			self.statusLine.setStatus(_("{name} · {model} · connected").format(name=name, model=model), "ok")
		else:
			# Translators: status line when the AI has no token. {name} is the AI.
			self.statusLine.setStatus(_("{name} · not connected, sending a question opens the connection screen").format(name=name), "idle")
		self.Layout()

	def _updateButtons(self):
		busy = self.session.busy
		self.sendButton.Enable(not busy)
		self.cancelButton.Enable(busy)
		hasEntries = len(self.session.conversation) > 0
		self.readButton.Enable(hasEntries)
		self.copyButton.Enable(hasEntries)
		self.saveButton.Enable(hasEntries)
		self.updateStatus()

	# Events ------------------------------------------------------------------

	def onProviderChanged(self, evt):
		providerId = self.providerId
		core.conf()["provider"] = providerId
		self._fillModels()
		self.updateStatus()
		if not core.store().has(providerId):
			# Translators: announced when the chosen AI has no token yet.
			ui.message(_("This AI is not connected yet. A connection screen will open when you send a question."))

	def onModelKillFocus(self, evt):
		self._saveModel()
		evt.Skip()

	def onCharHook(self, evt):
		focus = wx.Window.FindFocus()
		if focus is self.questionEdit:
			self.onQuestionKeyDown(evt)
		elif focus is self.conversationTree:
			self.onListKeyDown(evt)
		else:
			evt.Skip()

	def onQuestionKeyDown(self, evt):
		key = evt.GetKeyCode()
		if key in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER) and not evt.ShiftDown() and not evt.AltDown():
			self.onSend(None)
			return
		evt.Skip()

	def onListKeyDown(self, evt):
		key = evt.GetKeyCode()
		if key in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
			self.onTreeActivate()
			return
		if evt.ControlDown() and key in (ord("C"), ord("c")):
			self.onCopyMessage(None)
			return
		if key == wx.WXK_DELETE:
			data = self.selectedData()
			if data and data[0] == "conv":
				self.deletePreviousConversation(data[1])
				return
		evt.Skip()

	def onTreeActivate(self):
		"""Enter: reads a message of the current conversation; on a previous
		conversation (or one of its messages) opens it to be continued."""
		data = self.selectedData()
		if not data:
			return
		kind = data[0]
		if kind == "history":
			tree = self.conversationTree
			if tree.IsExpanded(self._historyNode):
				tree.Collapse(self._historyNode)
			elif tree.GetChildrenCount(self._historyNode, False):
				tree.Expand(self._historyNode)
		elif kind == "conv":
			self.openPreviousConversation(data[1])
		elif kind == "msg":
			if data[1] is None:
				self.onReadMessage(None)
			else:
				self.openPreviousConversation(data[1])

	def openPreviousConversation(self, convId):
		if self.session.busy:
			# Translators: announced when a question is already being answered.
			ui.message(_("Please wait for the current answer"))
			return
		saved = self._historyData.get(convId)
		try:
			conversation = self.session.openFromHistory(convId)
		except (KeyError, OSError, ValueError):
			# Translators: error when a saved conversation cannot be opened.
			ui.message(_("Could not open this conversation"))
			self.rebuildHistory()
			return
		title = history.summary(saved)[0] if saved else ""
		# Translators: announced after opening a previous conversation. {title} is its first question, {count} the number of messages.
		ui.message(_("Conversation \"{title}\" opened, {count} messages. Continue it in the Question field.").format(title=title, count=len(conversation)))
		self.questionEdit.SetFocus()

	def deletePreviousConversation(self, convId):
		saved = self._historyData.get(convId)
		title = history.summary(saved)[0] if saved else ""
		if gui.messageBox(
			# Translators: confirmation before deleting a previous conversation. {title} is its first question.
			_("Delete the conversation \"{title}\" from the history?").format(title=title),
			"NVDAIAs",
			wx.YES_NO | wx.ICON_QUESTION,
			self,
		) != wx.YES:
			return
		self.session.deleteFromHistory(convId)
		# Translators: announced after deleting a previous conversation.
		ui.message(_("Conversation deleted"))

	def onSend(self, evt):
		text = self.questionEdit.GetValue().strip()
		if not text:
			# Translators: announced when trying to send an empty question.
			ui.message(_("Type a question first"))
			self.questionEdit.SetFocus()
			return
		if self.session.busy:
			# Translators: announced when a question is already being answered.
			ui.message(_("Please wait for the current answer"))
			return
		self._saveModel()
		providerId = self.providerId
		if not core.store().has(providerId):
			if not self._runConnect(providerId):
				self.questionEdit.SetFocus()
				return
			providerId = self.providerId
		try:
			sent = self.session.send(text, providerId=providerId)
		except core.NoTokenError:
			sent = False
		if sent:
			self.questionEdit.SetValue("")
			name = getProviderClass(providerId).name
			# Translators: announced after sending. {name} is ChatGPT, Gemini or Claude.
			ui.message(_("Sent to {name}").format(name=name))
		self.questionEdit.SetFocus()

	def onCancelSend(self, evt):
		text = self.session.cancel()
		if text and not self.questionEdit.GetValue().strip():
			self.questionEdit.SetValue(text)
		# Translators: announced after cancelling a question.
		ui.message(_("Sending cancelled"))
		self.questionEdit.SetFocus()

	def onReadMessage(self, evt):
		entry = self.selectedEntry()
		if entry is None:
			return
		if entry.role == "user":
			# Translators: title of the window that shows a message written by the user.
			title = _("Your message")
		else:
			# Translators: title of the window that shows an answer. {name} is the AI, {model} the model.
			title = _("Answer from {name} ({model})").format(name=entry.providerName, model=entry.model)
		showMessageText(entry, title)

	def onCopyMessage(self, evt):
		entry = self.selectedEntry()
		if entry is not None:
			copyText(entry.text)

	def onNewConversation(self, evt):
		if len(self.session.conversation) and not core.conf()["saveHistory"] and gui.messageBox(
			# Translators: confirmation before clearing the conversation.
			_("Start a new conversation? The current messages will be removed."),
			"NVDAIAs",
			wx.YES_NO | wx.ICON_QUESTION,
			self,
		) != wx.YES:
			return
		self.session.newConversation()
		# Translators: announced after clearing the conversation.
		ui.message(_("New conversation"))
		self.questionEdit.SetFocus()

	def onSaveConversation(self, evt):
		if not len(self.session.conversation):
			return
		defaultName = time.strftime("NVDAIAs-%Y%m%d-%H%M.txt")
		with wx.FileDialog(
			self,
			# Translators: title of the save conversation dialog.
			_("Save conversation"),
			defaultDir=os.path.expanduser("~\\Documents") if os.name == "nt" else os.path.expanduser("~"),
			defaultFile=defaultName,
			# Translators: file type in the save dialog.
			wildcard=_("Text files (*.txt)") + "|*.txt",
			style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
		) as fd:
			if fd.ShowModal() != wx.ID_OK:
				return
			path = fd.GetPath()
		# Translators: label of the user in the saved file.
		text = self.session.conversation.toText(_("You"), _("[image attached]"))
		try:
			with open(path, "w", encoding="utf-8") as f:
				f.write(text)
		except OSError as e:
			# Translators: error while saving the file.
			gui.messageBox(_("Could not save the file: {error}").format(error=e), "NVDAIAs", wx.OK | wx.ICON_ERROR, self)
			return
		# Translators: announced after saving the conversation.
		ui.message(_("Conversation saved"))

	def _runConnect(self, providerId=None):
		dlg = ConnectDialog(self, providerId or self.providerId)
		try:
			dlg.ShowModal()
			connected = dlg.connectedProvider
		finally:
			dlg.Destroy()
		if connected:
			self.providerChoice.SetSelection(PROVIDER_IDS.index(connected))
			self._fillModels()
		return connected

	def onConnect(self, evt):
		self._runConnect()
		self.questionEdit.SetFocus()

	def onSettings(self, evt):
		from .settingsPanel import openSettings
		openSettings()

	def onClose(self, evt):
		self._saveModel()
		if self in self.session.listeners:
			self.session.listeners.remove(self)
		if self.refreshList in self.session.conversation.listeners:
			self.session.conversation.listeners.remove(self.refreshList)
		if ChatDialog._instance is self:
			ChatDialog._instance = None
		self.Destroy()
