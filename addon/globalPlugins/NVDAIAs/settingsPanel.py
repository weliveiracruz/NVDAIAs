# -*- coding: UTF-8 -*-
# NVDAIAs - settingsPanel.py
# NVDAIAs category in NVDA menu > Preferences > Settings.
# Copyright (C) 2026 Wellington Cruz
# This file is covered by the GNU General Public License, version 2.

import addonHandler
import gui
import ui
import wx
from gui import guiHelper, nvdaControls
from gui.settingsDialogs import NVDASettingsDialog, SettingsPanel
from logHandler import log

from . import core
from .connectDialog import openTokenPage
from .credentials import maskToken
from .providers import PROVIDER_IDS, getProviderClass

addonHandler.initTranslation()


def openSettings():
	wx.CallAfter(gui.mainFrame.popupSettingsDialog, NVDASettingsDialog, NVDAIAsSettingsPanel)


class _ProviderGroup:
	"""Controls of one AI inside the settings panel."""

	def __init__(self, panel, parentHelper, providerId):
		self.panel = panel
		self.providerId = providerId
		cls = getProviderClass(providerId)
		self.cls = cls
		box = wx.StaticBoxSizer(wx.VERTICAL, panel, label=core.providerLabel(providerId))
		boxParent = box.GetStaticBox()
		group = guiHelper.BoxSizerHelper(panel, sizer=box)
		parentHelper.addItem(group)

		self.statusText = group.addItem(wx.StaticText(boxParent, label=""))
		self.tokenEdit = group.addLabeledControl(
			# Translators: label of the token field in the settings. {name} is ChatGPT, Gemini or Claude.
			_("New {name} token (leave empty to keep the saved one):").format(name=cls.name),
			wx.TextCtrl,
			style=wx.TE_PASSWORD,
		)

		buttons = guiHelper.ButtonHelper(wx.HORIZONTAL)
		# Translators: button that opens the provider site to create a token. {name} is ChatGPT, Gemini or Claude.
		openButton = buttons.addButton(boxParent, label=_("Open {name} token page").format(name=cls.name))
		openButton.Bind(wx.EVT_BUTTON, lambda evt: openTokenPage(providerId))
		# Translators: button that tests the token. {name} is ChatGPT, Gemini or Claude.
		self.testButton = buttons.addButton(boxParent, label=_("Test connection to {name}").format(name=cls.name))
		self.testButton.Bind(wx.EVT_BUTTON, self.onTest)
		# Translators: button that deletes the saved token. {name} is ChatGPT, Gemini or Claude.
		self.removeButton = buttons.addButton(boxParent, label=_("Remove saved {name} token").format(name=cls.name))
		self.removeButton.Bind(wx.EVT_BUTTON, self.onRemove)
		group.addItem(buttons)

		# Translators: label of the model combo box in the settings.
		self.modelCombo = group.addLabeledControl(_("Model:"), wx.ComboBox, style=wx.CB_DROPDOWN)
		current = core.getModel(providerId)
		choices = list(core.modelCache.get(providerId) or cls.suggestedModels)
		if current not in choices:
			choices.insert(0, current)
		self.modelCombo.Set(choices)
		self.modelCombo.SetValue(current)
		# Translators: button that downloads the list of models available for the account. {name} is ChatGPT, Gemini or Claude.
		self.updateModelsButton = group.addItem(wx.Button(boxParent, label=_("Update {name} model list").format(name=cls.name)))
		self.updateModelsButton.Bind(wx.EVT_BUTTON, self.onUpdateModels)
		self.updateStatus()

	def updateStatus(self):
		token = core.store().get(self.providerId)
		if token:
			# Translators: status of a provider with a saved token. {hint} shows the last characters.
			label = _("Status: connected, token saved (ends with {hint}).").format(hint=maskToken(token))
		else:
			# Translators: status of a provider without token.
			label = _("Status: not connected, no token saved.")
		self.statusText.SetLabel(label)
		self.removeButton.Enable(bool(token))

	def currentToken(self):
		return self.tokenEdit.GetValue().strip() or core.store().get(self.providerId)

	def _provider(self):
		return core.makeProvider(self.providerId, token=self.currentToken(), model=self.modelCombo.GetValue().strip() or None)

	def onTest(self, evt):
		if not self.currentToken():
			# Translators: message when testing without token.
			gui.messageBox(_("Paste a token first."), "NVDAIAs", wx.OK | wx.ICON_WARNING, self.panel)
			return
		provider = self._provider()
		self.testButton.Disable()
		# Translators: announced while testing the connection.
		ui.message(_("Testing the connection, please wait…"))

		def ok(result):
			if not self.panel:
				return
			self.testButton.Enable()
			models, found = result
			if models:
				core.modelCache[self.providerId] = models
			# Translators: result of a successful test. {name} is the AI, {count} the number of models.
			msg = _("Connection to {name} working. {count} models available.").format(name=provider.name, count=len(models))
			if not found:
				# Translators: warning when the chosen model is not available. {model} is the model id.
				msg += "\n" + _("Attention: the model {model} is not in the list of your account. Choose another one in the Model field.").format(model=provider.model)
			if self.tokenEdit.GetValue().strip():
				# Translators: reminder that a typed token is only stored after OK/Apply.
				msg += "\n" + _("Press OK or Apply to save the new token.")
			gui.messageBox(msg, "NVDAIAs", wx.OK | wx.ICON_INFORMATION, self.panel)

		def fail(err):
			if not self.panel:
				return
			self.testButton.Enable()
			gui.messageBox(core.errorMessage(err, provider.name), "NVDAIAs", wx.OK | wx.ICON_ERROR, self.panel)

		core.runInBackground(provider.testConnection, ok, fail)

	def onUpdateModels(self, evt):
		if not self.currentToken():
			gui.messageBox(_("Paste a token first."), "NVDAIAs", wx.OK | wx.ICON_WARNING, self.panel)
			return
		provider = self._provider()
		self.updateModelsButton.Disable()
		# Translators: announced while downloading the model list.
		ui.message(_("Updating the model list…"))

		def ok(models):
			if not self.panel:
				return
			self.updateModelsButton.Enable()
			if not models:
				return
			core.modelCache[self.providerId] = models
			value = self.modelCombo.GetValue()
			self.modelCombo.Set(models)
			self.modelCombo.SetValue(value)
			# Translators: announced after updating the model list. {count} is the number of models.
			ui.message(_("{count} models available. Choose one in the Model combo box.").format(count=len(models)))

		def fail(err):
			if not self.panel:
				return
			self.updateModelsButton.Enable()
			gui.messageBox(core.errorMessage(err, provider.name), "NVDAIAs", wx.OK | wx.ICON_ERROR, self.panel)

		core.runInBackground(provider.listModels, ok, fail)

	def onRemove(self, evt):
		if gui.messageBox(
			# Translators: confirmation before removing a token. {name} is ChatGPT, Gemini or Claude.
			_("Remove the saved {name} token from this computer?").format(name=self.cls.name),
			"NVDAIAs",
			wx.YES_NO | wx.ICON_QUESTION,
			self.panel,
		) != wx.YES:
			return
		core.store().remove(self.providerId)
		self.tokenEdit.SetValue("")
		self.updateStatus()
		# Translators: announced after removing a token.
		ui.message(_("Token removed"))

	def save(self):
		token = self.tokenEdit.GetValue().strip()
		if token:
			try:
				core.store().set(self.providerId, token)
				self.tokenEdit.SetValue("")
			except Exception as e:
				log.error("NVDAIAs: could not save the token", exc_info=True)
				# Translators: error when the token cannot be saved. {error} is the technical error.
				gui.messageBox(_("The token could not be saved: {error}").format(error=e), "NVDAIAs", wx.OK | wx.ICON_ERROR)
		model = self.modelCombo.GetValue().strip()
		if model:
			core.setModel(self.providerId, model)
		self.updateStatus()


class NVDAIAsSettingsPanel(SettingsPanel):
	# Translators: title of the settings category.
	title = _("NVDAIAs")

	def makeSettings(self, settingsSizer):
		sHelper = guiHelper.BoxSizerHelper(self, sizer=settingsSizer)
		c = core.conf()

		# Translators: label of the default AI combo box.
		self.providerChoice = sHelper.addLabeledControl(_("Default &AI:"), wx.Choice, choices=[core.providerLabel(p) for p in PROVIDER_IDS])
		self.providerChoice.SetSelection(PROVIDER_IDS.index(c["provider"]))

		self.groups = [_ProviderGroup(self, sHelper, p) for p in PROVIDER_IDS]

		self.systemPromptEdit = sHelper.addLabeledControl(
			# Translators: label of the field with the instructions sent to the AI.
			_("&Instructions sent to the AI with every question (leave empty for the default):"),
			wx.TextCtrl,
			style=wx.TE_MULTILINE,
			size=(500, 90),
		)
		self.systemPromptEdit.SetValue(core.getSystemPrompt(effective=True))
		# Translators: button that restores the default instructions.
		restore = sHelper.addItem(wx.Button(self, label=_("Res&tore default instructions")))
		restore.Bind(wx.EVT_BUTTON, lambda evt: self.systemPromptEdit.SetValue(core.defaultSystemPrompt()))

		# Translators: checkbox to read answers automatically.
		self.speakCheck = sHelper.addItem(wx.CheckBox(self, label=_("&Read answers automatically when they arrive")))
		self.speakCheck.SetValue(c["speakResponses"])
		# Translators: checkbox to beep while waiting.
		self.beepCheck = sHelper.addItem(wx.CheckBox(self, label=_("&Beep while waiting for the answer")))
		self.beepCheck.SetValue(c["waitingBeeps"])
		# Translators: checkbox to remove Markdown symbols when reading.
		self.stripCheck = sHelper.addItem(wx.CheckBox(self, label=_("Remove &formatting symbols (#, *, |) when reading answers")))
		self.stripCheck.SetValue(c["stripMarkdown"])

		# Translators: checkbox that turns the visual theme on or off.
		self.themeCheck = sHelper.addItem(wx.CheckBox(self, label=_("Use the &visual theme in NVDAIAs windows (colours, header and focus frame)")))
		self.themeCheck.SetValue(c["visualTheme"])
		# Translators: checkbox that makes the text of the NVDAIAs windows bigger.
		self.largeTextCheck = sHelper.addItem(wx.CheckBox(self, label=_("&Larger text in NVDAIAs windows")))
		self.largeTextCheck.SetValue(c["largeText"])

		# Translators: checkbox to keep previous conversations.
		self.historyCheck = sHelper.addItem(wx.CheckBox(self, label=_("Keep &previous conversations (saved encrypted on this computer)")))
		self.historyCheck.SetValue(c["saveHistory"])
		self.maxHistorySpin = sHelper.addLabeledControl(
			# Translators: label of the maximum number of saved conversations.
			_("Maximum number of previous conversations:"),
			nvdaControls.SelectOnFocusSpinCtrl,
			min=5,
			max=1000,
			initial=c["maxHistory"],
		)
		# Translators: button that deletes all previous conversations.
		clearHistory = sHelper.addItem(wx.Button(self, label=_("&Delete all previous conversations…")))
		clearHistory.Bind(wx.EVT_BUTTON, self.onClearHistory)

		self.maxTokensSpin = sHelper.addLabeledControl(
			# Translators: label of the maximum answer size (used by Claude).
			_("Maximum answer size in tokens (Claude):"),
			nvdaControls.SelectOnFocusSpinCtrl,
			min=256,
			max=64000,
			initial=c["maxTokens"],
		)
		self.timeoutSpin = sHelper.addLabeledControl(
			# Translators: label of the time limit in seconds.
			_("Time limit to wait for an answer (seconds):"),
			nvdaControls.SelectOnFocusSpinCtrl,
			min=10,
			max=600,
			initial=c["timeout"],
		)

	def onClearHistory(self, evt):
		if gui.messageBox(
			# Translators: confirmation before deleting all previous conversations.
			_("Delete all previous conversations from this computer? This cannot be undone."),
			"NVDAIAs",
			wx.YES_NO | wx.ICON_WARNING,
			self,
		) != wx.YES:
			return
		core.history().deleteAll()
		# Translators: announced after deleting all previous conversations.
		ui.message(_("All previous conversations were deleted"))

	def onSave(self):
		c = core.conf()
		c["provider"] = PROVIDER_IDS[self.providerChoice.GetSelection()]
		for group in self.groups:
			group.save()
		prompt = self.systemPromptEdit.GetValue().strip()
		core.setSystemPrompt("" if prompt == core.defaultSystemPrompt().strip() else prompt)
		c["speakResponses"] = self.speakCheck.GetValue()
		c["waitingBeeps"] = self.beepCheck.GetValue()
		c["stripMarkdown"] = self.stripCheck.GetValue()
		c["visualTheme"] = self.themeCheck.GetValue()
		c["largeText"] = self.largeTextCheck.GetValue()
		c["saveHistory"] = self.historyCheck.GetValue()
		c["maxHistory"] = self.maxHistorySpin.GetValue()
		c["maxTokens"] = self.maxTokensSpin.GetValue()
		c["timeout"] = self.timeoutSpin.GetValue()
