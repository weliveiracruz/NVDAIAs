# -*- coding: UTF-8 -*-
# NVDAIAs - planUi.py
# Windows of "Sign in with ChatGPT": waiting for the browser, the one-time notice
# "You're using your ChatGPT plan", Manage usage and sign out.
# Copyright (C) 2026 Wellington Cruz
# This file is covered by the GNU General Public License, version 2.

import threading
import webbrowser

import addonHandler
import gui
import ui
import wx
from logHandler import log

from . import core, theme
from .feedback import confirm

addonHandler.initTranslation()


def openBrowser(url):
	"""Opens the address in a new tab of the default browser. False when it fails."""
	try:
		return webbrowser.open(url, new=2)
	except Exception:
		return False


def openUsagePage(parent=None):
	"""Opens the ChatGPT page where the plan usage is shown (Manage usage)."""
	if openBrowser(core.chatgptPlan.USAGE_URL) is False:
		gui.messageBox(
			# Translators: shown when the browser could not be opened. {url} is the address.
			_("Could not open the browser. Open this address manually: {url}").format(url=core.chatgptPlan.USAGE_URL),
			"NVDAIAs", wx.OK | wx.ICON_WARNING, parent or gui.mainFrame,
		)
		return False
	# Translators: announced after opening the ChatGPT usage page.
	ui.message(_("Opening your ChatGPT usage in the browser"))
	return True


def askManageUsage(parent=None):
	"""Usage limit reached: Manage usage is the main action."""
	if confirm(
		parent or gui.mainFrame,
		# Translators: message shown when the ChatGPT plan reached its usage limit.
		_("You have reached the usage limit of your ChatGPT plan. See your usage and limits in the ChatGPT settings."),
		# Translators: title of the window shown when the ChatGPT plan reached its usage limit.
		_("NVDAIAs - ChatGPT usage limit"),
		# Translators: button that opens the ChatGPT usage page.
		_("&Manage usage"),
		# Translators: button that closes the usage limit window.
		_("&Close"),
	):
		return openUsagePage(parent)
	return False


def showPlanNotice(parent=None, force=False):
	"""One-time notice after the first sign-in (UI guidelines of OpenAI)."""
	c = core.conf()
	if c["planNoticeShown"] and not force:
		return False
	dlg = wx.MessageDialog(
		parent or gui.mainFrame,
		# Translators: text of the notice shown once after signing in with ChatGPT.
		_("Questions you send to ChatGPT in NVDAIAs now use your ChatGPT plan and count toward its usage limits. "
			"NVDAIAs does not see your ChatGPT conversations. "
			"Check your usage with the Manage ChatGPT usage button, and switch back to an API token in the NVDAIAs settings whenever you want."),
		# Translators: title of the notice shown once after signing in with ChatGPT.
		_("You're using your ChatGPT plan"),
		wx.OK | wx.ICON_INFORMATION,
	)
	try:
		# Translators: button that closes the notice about using the ChatGPT plan.
		dlg.SetOKLabel(_("&Got it"))
		dlg.ShowModal()
	finally:
		dlg.Destroy()
	c["planNoticeShown"] = True
	return True


def browserPages():
	"""Texts of the page the browser shows when it comes back to NVDAIAs."""
	return {
		# Translators: page shown in the browser after signing in with ChatGPT.
		"done": _("Signed in. You can close this tab and go back to NVDA."),
		# Translators: page shown in the browser when the sign-in with ChatGPT was not completed.
		"error": _("Sign-in was not completed. You can close this tab and go back to NVDA."),
		# Translators: page shown in the browser for an address that does not belong to the current sign-in.
		"invalid": _("This address does not belong to the current sign-in."),
	}


def finishSignIn(models):
	"""After a successful sign-in: models of the plan and ChatGPT as default AI."""
	c = core.conf()
	if models:
		core.modelCache[core.PLAN_SLOT] = models
		if c["model_openai_plan"] not in models:
			c["model_openai_plan"] = models[0]
	c["openaiUsePlan"] = True
	c["provider"] = "openai"


class SignInDialog(wx.Dialog):
	"""Waits while the user signs in in the browser. Cancel stops the wait.

	``onDone(ok)`` is called once, on the GUI thread, after the window closes."""

	_running = None

	def __init__(self, parent, onDone=None):
		# Translators: title of the window shown while signing in with ChatGPT.
		super().__init__(parent, title=_("NVDAIAs - Continue with ChatGPT"))
		self.onDone = onDone
		self.cancelEvent = threading.Event()
		self.result = None
		self.error = None
		sizer = wx.BoxSizer(wx.VERTICAL)
		# Translators: label of the text that explains the sign-in with ChatGPT.
		label = wx.StaticText(self, label=_("&Status:"))
		self.messageText = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY, size=(480, 110))
		self.messageText.SetValue(
			# Translators: shown while waiting for the sign-in with ChatGPT in the browser.
			_("Your browser was opened on the ChatGPT page. Sign in, allow NVDAIAs to use your ChatGPT plan and come back to NVDA. "
				"Waiting for the sign-in…")
		)
		# Translators: button that stops waiting for the sign-in with ChatGPT.
		self.cancelButton = wx.Button(self, id=wx.ID_CANCEL, label=_("&Cancel sign-in"))
		self.cancelButton.Bind(wx.EVT_BUTTON, lambda evt: self.cancel())
		self.Bind(wx.EVT_CLOSE, lambda evt: self.cancel())
		themed = theme.isEnabled()
		pad = theme.space("md") if themed else 0
		card = wx.BoxSizer(wx.VERTICAL)
		card.Add(label)
		card.AddSpacer(theme.space("sm"))
		card.Add(self.messageText, proportion=1, flag=wx.EXPAND)
		sizer.Add(card, proportion=1, flag=wx.ALL | wx.EXPAND, border=10 + 2 * pad)
		sizer.Add(self.cancelButton, flag=wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.ALIGN_RIGHT, border=10 + pad)
		self.SetSizer(sizer)
		sizer.Fit(self)
		if themed:
			cards = (theme.Card(card, (label, self.messageText), title=label),)
			theme.applyColors(self, bodyControls=(self.messageText,), cards=cards)
			self.focusFrames = theme.FocusFrames(self, (self.messageText,), cards=cards)
		self.SetEscapeId(wx.ID_CANCEL)
		self.CentreOnScreen()

	def start(self):
		"""Shows the window, opens the browser and waits in the background."""
		SignInDialog._running = self
		self.Show()
		self.Raise()
		self.messageText.SetFocus()
		# Once more after the window is really on screen, so NVDA reads the explanation.
		wx.CallAfter(self._focusMessage)
		cancelEvent = self.cancelEvent
		pages = browserPages()

		def work():
			session = core.plan().signIn(openBrowser, cancelEvent=cancelEvent, pages=pages)
			models = []
			try:
				models = core.chatgptPlan.ChatGPTPlanProvider(core.plan(), timeout=core.conf()["timeout"]).listModels()
			except Exception:
				log.debugWarning("NVDAIAs: could not list the ChatGPT plan models", exc_info=True)
			return session, models

		core.runInBackground(work, self._ok, self._fail)

	def _focusMessage(self):
		try:
			if self.result is None and self.error is None:
				self.messageText.SetFocus()
		except RuntimeError:
			pass

	def cancel(self):
		if self.result is None and self.error is None:
			self.cancelEvent.set()
			# Translators: announced when the user cancels the sign in with ChatGPT.
			ui.message(_("Cancelling the sign-in…"))

	def _close(self):
		if SignInDialog._running is self:
			SignInDialog._running = None
		try:
			self.Destroy()
		except RuntimeError:
			pass

	def _ok(self, result):
		self.result = result
		session, models = result
		finishSignIn(models)
		parent = self.GetParent()
		self._close()
		# Translators: announced after signing in with ChatGPT. {email} is the account.
		ui.message(_("Signed in to ChatGPT as {email}").format(email=session.get("email") or "-"))
		showPlanNotice(parent)
		if self.onDone:
			self.onDone(True)

	def _fail(self, err):
		self.error = err
		parent = self.GetParent()
		self._close()
		message = core.errorMessage(err, "ChatGPT")
		if getattr(err, "kind", "") == "cancelled":
			ui.message(message)
		else:
			log.debugWarning("NVDAIAs: sign in with ChatGPT failed: %s" % getattr(err, "detail", err))
			gui.messageBox(message, "NVDAIAs", wx.OK | wx.ICON_ERROR, parent or gui.mainFrame)
		if self.onDone:
			self.onDone(False)


def startSignIn(parent, onDone=None):
	"""Starts "Continue with ChatGPT". Returns the waiting window (or the one already open)."""
	if SignInDialog._running is not None:
		try:
			SignInDialog._running.Raise()
			SignInDialog._running.messageText.SetFocus()
			return SignInDialog._running
		except RuntimeError:
			SignInDialog._running = None
	dlg = SignInDialog(parent, onDone)
	dlg.start()
	return dlg


def signOut(parent=None):
	"""Asks, then signs out of ChatGPT (revokes the session). Returns True when done."""
	if gui.messageBox(
		# Translators: confirmation before signing out of ChatGPT. {email} is the account.
		_("Sign out of ChatGPT ({email}) on this computer? NVDAIAs will stop using your ChatGPT plan.").format(email=core.plan().email() or "-"),
		"NVDAIAs",
		wx.YES_NO | wx.ICON_QUESTION,
		parent or gui.mainFrame,
	) != wx.YES:
		return False

	# The session is deleted at once; the revocation talks to OpenAI in the background.
	session = core.plan().endSession()
	core.runInBackground(lambda: core.plan().revoke(session), lambda result: None, lambda err: None)
	# Translators: announced after signing out of ChatGPT.
	ui.message(_("Signed out of ChatGPT"))
	return True
