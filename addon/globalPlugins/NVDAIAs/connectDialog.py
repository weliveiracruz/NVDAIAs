# -*- coding: UTF-8 -*-
# NVDAIAs - connectDialog.py
# "Connect account" screen: the user picks an AI, opens the page that generates
# the token, pastes it, and the add-on tests it before saving.
# Copyright (C) 2026 Wellington Cruz
# This file is covered by the GNU General Public License, version 2.

import webbrowser

import addonHandler
import gui
import ui
import wx
from gui import guiHelper
from logHandler import log

from . import core, planUi, theme
from .providers import PROVIDER_IDS, getProviderClass

addonHandler.initTranslation()


def openTokenPage(providerId):
	url = getProviderClass(providerId).tokenUrl
	try:
		webbrowser.open(url)
		# Translators: announced after opening the browser on the token page.
		ui.message(_("Opening the page to generate the token in your browser"))
	except Exception:
		# Translators: shown when the browser could not be opened. {url} is the address.
		gui.messageBox(_("Could not open the browser. Open this address manually: {url}").format(url=url), "NVDAIAs")


def instructions(providerId):
	cls = getProviderClass(providerId)
	steps = {
		# Translators: steps to create an OpenAI API key.
		"openai": _("1. Press the button \"Open page to generate token\". The OpenAI platform (platform.openai.com) opens in your browser.\n"
			"2. Sign in with your OpenAI account.\n"
			"3. Choose \"Create new secret key\", give it a name such as NVDAIAs and confirm.\n"
			"4. Copy the key (it starts with sk-) and paste it in the Token field below.\n"
			"Note: API usage is billed separately from the ChatGPT Plus subscription; the account needs credit."
		),
		# Translators: steps to create a Gemini API key.
		"gemini": _("1. Press the button \"Open page to generate token\". Google AI Studio (aistudio.google.com) opens in your browser.\n"
			"2. Sign in with your Google account.\n"
			"3. Choose \"Create API key\" and confirm.\n"
			"4. Copy the key and paste it in the Token field below.\n"
			"Note: Gemini offers a free usage tier with limits."
		),
		# Translators: steps to create an Anthropic API key.
		"anthropic": _("1. Press the button \"Open page to generate token\". The Claude Console (console.anthropic.com) opens in your browser.\n"
			"2. Sign in with your Anthropic account.\n"
			"3. Choose \"Create Key\", give it a name such as NVDAIAs and confirm.\n"
			"4. Copy the key (it starts with sk-ant-) and paste it in the Token field below.\n"
			"Note: API usage is billed separately from the Claude Pro subscription; the account needs credit."
		),
	}
	# Translators: first line of the connection instructions. {name} is ChatGPT, Gemini or Claude.
	head = _("To connect NVDAIAs to {name} you need an access token (API key) generated on the provider's site.").format(name=cls.name)
	return head + "\n" + steps[providerId]


class ConnectDialog(wx.Dialog):
	"""Login screen. After a successful connection ``self.connectedProvider`` holds the provider id."""

	def __init__(self, parent, providerId=None):
		# Translators: title of the connect account dialog.
		super().__init__(parent, title=_("NVDAIAs - Connect account"))
		self.connectedProvider = None
		self._testing = False
		providerId = providerId or core.conf()["provider"]
		themed = theme.isEnabled()
		mainSizer = wx.BoxSizer(wx.VERTICAL)
		if themed:
			# Translators: title of the coloured header of the connect dialog.
			headerTitle = _("Connect account")
			# Translators: subtitle of the coloured header of the connect dialog.
			headerSubtitle = _("Paste the token generated on the AI's site")
			mainSizer.Add(theme.HeaderPanel(self, headerTitle, headerSubtitle), flag=wx.EXPAND)
		sHelper = guiHelper.BoxSizerHelper(self, orientation=wx.VERTICAL)

		# Translators: label of the combo box to choose the AI in the connect dialog.
		self.providerChoice = sHelper.addLabeledControl(_("&Artificial intelligence:"), wx.Choice, choices=[core.providerLabel(p) for p in PROVIDER_IDS])
		self.providerChoice.SetSelection(PROVIDER_IDS.index(providerId))
		self.providerChoice.Bind(wx.EVT_CHOICE, self.onProviderChanged)

		# "Sign in with ChatGPT": uses the user's ChatGPT plan, no API key (ChatGPT only).
		# Translators: button that signs in with the ChatGPT account and uses the ChatGPT plan, without API key.
		self.chatgptButton = sHelper.addItem(wx.Button(self, label=_("Continue &with ChatGPT")))
		self.chatgptButton.Bind(wx.EVT_BUTTON, self.onContinueWithChatGPT)

		# Translators: label of the read-only field with the connection instructions.
		instructionsLabel = wx.StaticText(self, label=_("&Instructions:"))
		self.instructionsText = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2, size=(560, 180))
		instructionsBox = wx.BoxSizer(wx.VERTICAL)
		instructionsBox.Add(instructionsLabel)
		instructionsBox.AddSpacer(theme.space("sm"))
		instructionsBox.Add(self.instructionsText, proportion=1, flag=wx.EXPAND)
		sHelper.addItem(instructionsBox, flag=wx.EXPAND)

		# Translators: button that opens the provider site where the token is generated.
		self.openPageButton = sHelper.addItem(wx.Button(self, label=_("&Open page to generate token")))
		self.openPageButton.Bind(wx.EVT_BUTTON, lambda evt: openTokenPage(self.providerId))

		# Translators: label of the password field where the token is pasted.
		self.tokenEdit = sHelper.addLabeledControl(_("&Token (API key):"), wx.TextCtrl, style=wx.TE_PASSWORD, size=(400, -1))

		self.statusLabel = sHelper.addItem(wx.StaticText(self, label=""))

		bHelper = guiHelper.ButtonHelper(wx.HORIZONTAL)
		# Translators: button that tests and saves the token.
		self.connectButton = bHelper.addButton(self, label=_("&Connect"))
		self.connectButton.SetDefault()
		self.connectButton.Bind(wx.EVT_BUTTON, self.onConnect)
		# Translators: cancel button.
		bHelper.addButton(self, id=wx.ID_CANCEL, label=_("Cancel"))
		sHelper.addDialogDismissButtons(bHelper)
		mainSizer.Add(sHelper.sizer, border=guiHelper.BORDER_FOR_DIALOGS + (theme.space("xs") if themed else 0), flag=wx.ALL | wx.EXPAND)
		if themed:
			theme.applyColors(self, bodyControls=(self.instructionsText, self.tokenEdit))
			self.focusFrames = theme.FocusFrames(self, (self.providerChoice, self.instructionsText, self.tokenEdit))
		self.SetSizer(mainSizer)
		mainSizer.Fit(self)
		self._updateInstructions()
		self.CentreOnScreen()
		self.providerChoice.SetFocus()

	@property
	def providerId(self):
		return PROVIDER_IDS[self.providerChoice.GetSelection()]

	def onProviderChanged(self, evt):
		self._updateInstructions()

	def _updateInstructions(self):
		isChatGPT = self.providerId == "openai"
		if self.chatgptButton.IsShown() != isChatGPT:
			self.chatgptButton.Show(isChatGPT)
			self.Layout()
		text = instructions(self.providerId)
		if isChatGPT:
			# Translators: explanation of the Continue with ChatGPT button in the connect dialog.
			text = _("No API key? Press \"Continue with ChatGPT\" to sign in with your ChatGPT account and use your ChatGPT plan (Plus, Pro and others). "
				"Questions then count toward the usage limits of your plan, with no extra billing.") + "\n\n" + text
			if core.planSignedIn():
				# Translators: appended to the instructions when already signed in with ChatGPT. {email} is the account.
				text += "\n" + _("Already signed in with ChatGPT as {email}.").format(email=core.plan().email() or "-")
		if core.store().has(self.providerId):
			# Translators: appended to the instructions when a token is already saved.
			text += "\n" + _("A token for this AI is already saved. Paste a new one only if you want to replace it.")
		self.instructionsText.SetValue(text)

	def onContinueWithChatGPT(self, evt):
		if self._testing:
			return

		def done(ok):
			if not ok or not self:
				return
			self.connectedProvider = "openai"
			if self.IsModal():
				self.EndModal(wx.ID_OK)
			else:
				self.Close()

		planUi.startSignIn(self, done)

	def onConnect(self, evt):
		if self._testing:
			return
		token = self.tokenEdit.GetValue().strip()
		if not token:
			# Translators: message when the token field is empty.
			gui.messageBox(_("Paste the token in the Token field first."), "NVDAIAs", wx.OK | wx.ICON_WARNING, self)
			self.tokenEdit.SetFocus()
			return
		providerId = self.providerId
		provider = core.makeProvider(providerId, token=token)
		self._testing = True
		self.connectButton.Disable()
		# Translators: shown and announced while the token is being tested.
		status = _("Testing the connection, please wait…")
		self.statusLabel.SetLabel(status)
		ui.message(status)

		def ok(result):
			self._testing = False
			if not self:
				return
			self.connectButton.Enable()
			try:
				core.store().set(providerId, token)
				if providerId == "openai":
					# A token typed now means: use the token, not the ChatGPT plan.
					core.conf()["openaiUsePlan"] = False
			except Exception as e:
				log.error("NVDAIAs: could not save the token", exc_info=True)
				# Translators: error when the token cannot be saved. {error} is the technical error.
				gui.messageBox(_("The connection works, but the token could not be saved: {error}").format(error=e), "NVDAIAs", wx.OK | wx.ICON_ERROR, self)
				return
			core.conf()["provider"] = providerId
			models, found = result
			if not found and models:
				# Keep the user's choice valid: fall back to the provider default or the first model listed.
				cls = getProviderClass(providerId)
				core.setModel(providerId, cls.defaultModel if cls.defaultModel in models else models[0])
			self.connectedProvider = providerId
			# Translators: message after a successful connection. {name} is ChatGPT, Gemini or Claude.
			gui.messageBox(_("Connected to {name}. The token was saved securely on this computer.").format(name=provider.name), "NVDAIAs", wx.OK | wx.ICON_INFORMATION, self)
			self.EndModal(wx.ID_OK)

		def fail(err):
			self._testing = False
			if not self:
				return
			self.connectButton.Enable()
			self.statusLabel.SetLabel("")
			gui.messageBox(core.errorMessage(err, provider.name), "NVDAIAs", wx.OK | wx.ICON_ERROR, self)
			self.tokenEdit.SetFocus()

		core.runInBackground(provider.testConnection, ok, fail)
