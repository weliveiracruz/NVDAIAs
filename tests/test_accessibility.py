# -*- coding: UTF-8 -*-
"""Accessibility tests (ACE-xx in docs/SDD-TESTES.md).

Run (Linux): xvfb-run -a python3 tests/test_accessibility.py
"""
import ast
import gettext
import os
import re
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
PKG = os.path.join(ROOT, "addon", "globalPlugins", "NVDAIAs")
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "addon", "globalPlugins"))
import wx  # noqa: E402

import nvda_stubs  # noqa: E402
from nvda_stubs import RECORD  # noqa: E402
from _results import Recorder  # noqa: E402

nvda_stubs.install()
import mock_server  # noqa: E402

SERVER, BASE = mock_server.start()
app = wx.App(False)
import gui  # noqa: E402

gui.mainFrame = gui.MainFrame()
import NVDAIAs  # noqa: E402
from NVDAIAs import core, providers, chatDialog, connectDialog, settingsPanel, textutils, theme, chatgptPlan, planUi  # noqa: E402

for cls, path in ((providers.OpenAIProvider, "/openai/v1"), (providers.GeminiProvider, "/gemini/v1beta"), (providers.AnthropicProvider, "/anthropic/v1")):
	cls.defaultBaseUrl = BASE + path

R = Recorder("accessibility (test_accessibility)")
POPUPS = []


def _fakePopup(self, menu, pos=None):
	"""PopupMenu is modal: record the items (the menu is destroyed afterwards)."""
	items = []
	for i in menu.GetMenuItems():
		sub = [x.GetItemLabel() for x in i.GetSubMenu().GetMenuItems()] if i.GetSubMenu() else None
		items.append((i.GetItemLabel(), sub))
	POPUPS.append(items)
	return True


chatDialog.ChatDialog.PopupMenu = _fakePopup


def pump(until=lambda: False, timeout=5.0):
	end = time.time() + timeout
	while time.time() < end:
		wx.Yield()
		if until():
			return True
		time.sleep(0.02)
	return until()


def focusables(win):
	"""Controls reachable with Tab, in tab order (creation order of the children)."""
	out = []
	for c in win.GetChildren():
		if not c.IsShown():
			continue
		if isinstance(c, wx.StaticBox):
			out.extend(focusables(c))
		elif isinstance(c, wx.Panel) and not isinstance(c, (theme.HeaderPanel,)) and c.GetChildren() and not c.AcceptsFocusFromKeyboard():
			out.extend(focusables(c))
		elif c.AcceptsFocusFromKeyboard() and not isinstance(c, (wx.StaticText, theme.HeaderPanel)):
			out.append(c)
	return out


def accessibleName(ctrl):
	"""Name a screen reader gets on Windows: own label for buttons/check boxes,
	otherwise the static text that comes right before the control."""
	if isinstance(ctrl, (wx.Button, wx.CheckBox)):
		return ctrl.GetLabel()
	siblings = list(ctrl.GetParent().GetChildren())
	i = siblings.index(ctrl)
	j = i - 1
	while j >= 0 and not siblings[j].IsShown():
		j -= 1
	if j >= 0 and isinstance(siblings[j], wx.StaticText) and not isinstance(siblings[j], theme.StatusLine):
		return siblings[j].GetLabel()
	return ""


def mnemonicLabels(win):
	labels = []
	for c in win.GetChildren():
		if isinstance(c, (theme.StatusLine, theme.HeaderPanel)):
			continue
		if isinstance(c, (wx.Button, wx.CheckBox, wx.StaticText)) and c.IsShown():
			labels.append(c.GetLabel())
		if isinstance(c, wx.StaticBox) or (isinstance(c, wx.Panel) and not isinstance(c, theme.HeaderPanel)):
			labels.extend(mnemonicLabels(c))
	return labels


def checkWindow(name, win, requireMnemonicOnButtons=True):
	ctrls = focusables(win)
	unnamed = [type(c).__name__ for c in ctrls if not accessibleName(c).replace("&", "").strip()]
	R.check("ACE-01 every focusable control has an accessible name: %s" % name, not unnamed, unnamed)
	keys = []
	for label in mnemonicLabels(win):
		m = re.search(r"&(\w)", label)
		if m:
			keys.append((m.group(1).lower(), label))
	dups = sorted({k for k, _l in keys if [x for x, _y in keys].count(k) > 1})
	R.check("ACE-02 Alt shortcuts are unique: %s" % name, not dups, dups)
	if requireMnemonicOnButtons:
		missing = [b.GetLabel() for b in ctrls if isinstance(b, wx.Button) and "&" not in b.GetLabel() and b.GetId() not in (wx.ID_CANCEL, wx.ID_OK)]
		R.check("ACE-02 every button has an Alt shortcut: %s" % name, not missing, missing)
	else:
		# Panels with repeated groups (one per AI): there are not enough letters for
		# every button, so each button must at least have a unique name.
		names = [b.GetLabel().replace("&", "") for b in ctrls if isinstance(b, wx.Button)]
		dupNames = sorted({n for n in names if names.count(n) > 1})
		R.check("ACE-02 every button has a unique name: %s" % name, not dupNames, dupNames)
	R.check("ACE-14 window has its own title: %s" % name, not isinstance(win, wx.TopLevelWindow) or bool(win.GetTitle().strip()), win.GetTitle() if isinstance(win, wx.TopLevelWindow) else "")


def run():
	plugin = NVDAIAs.GlobalPlugin()
	core.store().set("anthropic", mock_server.VALID["anthropic"])
	core.conf()["provider"] = "anthropic"
	dlg = chatDialog.ChatDialog.showInstance(plugin.session)
	pump(timeout=0.3)

	# ACE-01/02/14 in the three windows
	checkWindow("chat", dlg)
	cd = connectDialog.ConnectDialog(dlg, "openai")
	checkWindow("connect account", cd)
	cd.Destroy()
	frame = wx.Frame(None)
	panel = settingsPanel.NVDAIAsSettingsPanel(frame)
	checkWindow("settings", panel, requireMnemonicOnButtons=False)
	frame.Destroy()

	# ACE-20 Sign in with ChatGPT ----------------------------------------------------------
	chatgptPlan.ISSUER = BASE + "/chatgpt/auth"
	chatgptPlan.ChatGPTPlanProvider.defaultBaseUrl = BASE + "/chatgpt/v1"
	planUi.openBrowser = lambda url: mock_server.fakeBrowser(url, delay=1.5)  # the user takes a while in the browser
	core._plan = None  # created again with the fake authorization server
	core.conf()["planNoticeShown"] = True
	cd = connectDialog.ConnectDialog(dlg, "openai")
	order = focusables(cd)
	R.check("ACE-20 Continue with ChatGPT reachable with Tab right after the AI box", order.index(cd.chatgptButton) == order.index(cd.providerChoice) + 1)
	R.check("ACE-20 Continue with ChatGPT has an Alt shortcut", "&" in cd.chatgptButton.GetLabel())
	cd.providerChoice.SetSelection(1)
	cd.onProviderChanged(None)
	R.check("ACE-04 Continue with ChatGPT out of the tab order for other AIs", cd.chatgptButton not in focusables(cd))
	cd.Destroy()
	waiting = planUi.SignInDialog(dlg)
	checkWindow("sign-in waiting window", waiting)
	R.check("ACE-01 waiting message has a name", accessibleName(waiting.messageText).replace("&", "") == "Status:", accessibleName(waiting.messageText))
	waiting.Destroy()
	RECORD["spoken"].clear()
	waiting = planUi.startSignIn(dlg)
	pump(timeout=0.4)
	R.check("ACE-07 focus on the explanation while waiting for the browser", planUi.SignInDialog._running is waiting and wx.Window.FindFocus() is waiting.messageText, wx.Window.FindFocus())
	pump(lambda: planUi.SignInDialog._running is None, 15)
	R.check("ACE-06 sign-in with ChatGPT is announced", any(s.startswith("Signed in to ChatGPT as") for s in RECORD["spoken"]), RECORD["spoken"])
	dlg.providerChoice.SetSelection(0)
	dlg.onProviderChanged(None)
	checkWindow("chat using the ChatGPT plan", dlg)
	R.check("ACE-10 status line says the ChatGPT plan is in use", "using your ChatGPT plan" in dlg.statusLine.GetLabel(), dlg.statusLine.GetLabel())
	R.check("ACE-20 Manage ChatGPT usage reachable with Tab", dlg.usageButton in focusables(dlg))
	nvda_stubs.MESSAGEBOX_ANSWER["value"] = wx.YES
	planUi.signOut(dlg)
	dlg.updateStatus()
	R.check("ACE-04 Manage ChatGPT usage out of the tab order without the plan", dlg.usageButton not in focusables(dlg))
	R.check("ACE-06 sign out is announced", RECORD["spoken"][-1] == "Signed out of ChatGPT", RECORD["spoken"][-1:])
	dlg.providerChoice.SetSelection(2)
	dlg.onProviderChanged(None)

	# ACE-03 tab order
	order = focusables(dlg)
	expected = [dlg.providerChoice, dlg.modelCombo, dlg.conversationTree, dlg.questionEdit, dlg.attachButton, dlg.sendButton]
	R.check("ACE-03 tab order starts AI, Model, Conversation, Question, Attach, Send", order[: len(expected)] == expected, [type(c).__name__ for c in order])
	dlg.questionEdit.SetFocus()
	pump(timeout=0.3)
	dlg.questionEdit.Navigate(wx.NavigationKeyEvent.IsBackward)
	pump(timeout=0.3)
	R.check("ACE-03 Shift+Tab from the question reaches the conversation", wx.Window.FindFocus() is dlg.conversationTree, wx.Window.FindFocus())

	# ACE-04 hidden controls
	R.check("ACE-04 hidden attachment list is out of the tab order", dlg.attachmentsList not in order and not dlg.attachmentsList.IsShown())

	# ACE-05/06/07 keyboard, announcements, focus
	def keyEvent(win, key, shift=False, ctrl=False):
		e = wx.KeyEvent(wx.wxEVT_KEY_DOWN)
		e.SetEventObject(win)
		e.SetKeyCode(key)
		e.SetShiftDown(shift)
		e.SetControlDown(ctrl)
		return e

	def spokenAfter(action):
		n = len(RECORD["spoken"])
		action()
		return RECORD["spoken"][n:]

	dlg.questionEdit.SetFocus()
	dlg.questionEdit.SetValue("Pergunta de acessibilidade")
	said = spokenAfter(lambda: dlg.onCharHook(keyEvent(dlg.questionEdit, wx.WXK_RETURN)))
	R.check("ACE-05 Enter in the question sends", plugin.session.busy or len(plugin.session.conversation) >= 1)
	R.check("ACE-06 sending is announced", any(s.startswith("Sent to") for s in said), said)
	said = []
	n = len(RECORD["spoken"])
	pump(lambda: not plugin.session.busy, 10)
	R.check("ACE-06 the answer is read automatically", any("Claude responde" in s for s in RECORD["spoken"][n:]), RECORD["spoken"][n:])
	R.check("ACE-07 focus stays in the question after the answer", wx.Window.FindFocus() is dlg.questionEdit, wx.Window.FindFocus())

	tree = dlg.conversationTree
	dlg.conversationTree.SetFocus()
	last = None
	child, cookie = tree.GetFirstChild(dlg._currentNode)
	while child.IsOk():
		last = child
		child, cookie = tree.GetNextChild(dlg._currentNode, cookie)
	tree.SelectItem(last)
	n = len(POPUPS)
	dlg.onCharHook(keyEvent(tree, wx.WXK_RETURN))
	R.check("ACE-05 Enter on a message opens the actions menu", len(POPUPS) == n + 1)
	evt = wx.ContextMenuEvent(wx.wxEVT_CONTEXT_MENU, tree.GetId())
	tree.GetEventHandler().ProcessEvent(evt)
	R.check("ACE-05 Applications key / Shift+F10 opens the actions menu", len(POPUPS) == n + 2)
	menu = POPUPS[-1]
	labels = [label for label, _sub in menu]
	keys = [re.search(r"&(\w)", l).group(1).lower() if re.search(r"&(\w)", l) else None for l in labels]
	R.check("ACE-12 every menu item has an Alt shortcut", None not in keys, labels)
	R.check("ACE-12 menu shortcuts are unique", len(set(keys)) == len(keys), labels)
	subLabels = next((sub for _label, sub in menu if sub), [])
	R.check("ACE-12 translate submenu has items", len(subLabels) >= 10, subLabels)

	# announcements of the other actions
	nvda_stubs.MESSAGEBOX_ANSWER["value"] = wx.YES
	tree.SelectItem(last)
	said = spokenAfter(lambda: dict(dlg.messageActions())["&Copy"]())
	R.check("ACE-06 copy is announced", said == ["Copied to the clipboard"], said)
	said = spokenAfter(lambda: dict(dlg.messageActions())["&Delete"]())
	R.check("ACE-06 message deletion is announced", "Message deleted" in said, said)
	R.check("ACE-07 focus stays in the conversation after deleting", wx.Window.FindFocus() in (tree, dlg.questionEdit), wx.Window.FindFocus())
	folder = tempfile.mkdtemp()
	path = os.path.join(folder, "nota.txt")
	with open(path, "w", encoding="utf-8") as f:
		f.write("conteúdo")
	said = spokenAfter(lambda: dlg.addAttachmentFiles([path]))
	R.check("ACE-06 attaching is announced", said and said[0].startswith("Attached: nota.txt"), said)
	R.check("ACE-04 attachment list appears when it has files", dlg.attachmentsList.IsShown() and dlg.attachmentsList in focusables(dlg))
	R.check("ACE-01 attachment list has a name", "Attached" in accessibleName(dlg.attachmentsList), accessibleName(dlg.attachmentsList))
	dlg.attachmentsList.SetFocus()
	dlg.attachmentsList.SetSelection(0)
	said = spokenAfter(lambda: dlg.onAttachmentsKeyDown(keyEvent(dlg.attachmentsList, wx.WXK_DELETE)))
	R.check("ACE-06 removing an attachment is announced", said == ["nota.txt removed"], said)
	R.check("ACE-07 focus goes back to the question when the last file is removed", wx.Window.FindFocus() is dlg.questionEdit, wx.Window.FindFocus())
	said = spokenAfter(lambda: dlg.onNewConversation(None))
	R.check("ACE-06 new conversation is announced", said == ["New conversation"], said)
	mock_server.DELAY["seconds"] = 1
	dlg.questionEdit.SetValue("x")
	dlg.onSend(None)
	said = spokenAfter(lambda: dlg.onCancelSend(None))
	mock_server.DELAY["seconds"] = 0
	R.check("ACE-06 cancelling is announced", said == ["Sending cancelled"], said)
	pump(timeout=1.5)
	core.store().set("openai", "errado")
	dlg.providerChoice.SetSelection(0)
	dlg.onProviderChanged(None)
	dlg.questionEdit.SetValue("vai falhar")
	dlg.onSend(None)
	n = len(RECORD["spoken"])
	pump(lambda: not plugin.session.busy, 10)
	R.check("ACE-06 errors are announced", any("did not accept the token" in s for s in RECORD["spoken"][n:]), RECORD["spoken"][n:])
	R.check("ACE-10 error state has text in the status line", "failed" in dlg.statusLine.GetLabel(), dlg.statusLine.GetLabel())
	R.check("ACE-07 focus in the question after an error", wx.Window.FindFocus() is dlg.questionEdit, wx.Window.FindFocus())
	core.store().set("openai", mock_server.VALID["openai"])
	dlg.updateStatus()
	R.check("ACE-10 connected state has text in the status line", "connected" in dlg.statusLine.GetLabel(), dlg.statusLine.GetLabel())
	R.check("ACE-10 status line is text, not focusable", isinstance(dlg.statusLine, wx.StaticText) and dlg.statusLine not in focusables(dlg))

	# ACE-19 tree branches
	R.check("ACE-19 current conversation branch says how many messages it has", re.match(r"Current conversation \(\d+ messages\)|Current conversation \(no messages yet\)", tree.GetItemText(dlg._currentNode)) is not None, tree.GetItemText(dlg._currentNode))
	tree.SetFocus()
	pump(timeout=0.2)
	tree.SelectItem(dlg._currentNode)
	wasExpanded = tree.IsExpanded(dlg._currentNode)
	dlg.onCharHook(keyEvent(tree, wx.WXK_RETURN))
	R.check("ACE-05 Enter on the current conversation branch collapses or expands it", tree.IsExpanded(dlg._currentNode) != wasExpanded or tree.GetChildrenCount(dlg._currentNode, False) == 0)
	dlg.onCharHook(keyEvent(tree, wx.WXK_RETURN))
	R.check("ACE-19 history branch says how many conversations it has", dlg._historyNode is None or re.match(r"Previous conversations \(\d+\)", tree.GetItemText(dlg._historyNode)) is not None)

	# ACE-11 reading window semantics
	entry = core.ChatEntry("assistant", "# Título\n\n- item\n\n| A | B |\n|---|---|\n| 1 | 2 |", providerName="Claude", model="m")
	chatDialog.showMessageText(entry, "t")
	html, title, isHtml = RECORD["browseable"][-1]
	R.check("ACE-11 reading window uses real headings, lists and tables", isHtml and "<h1>" in html and "<li>" in html and "<th>" in html, html)

	# ACE-13 larger text
	normal = theme.font("size.body", scale=1.0).GetPointSize()
	core.conf()["largeText"] = True
	big = theme.font("size.body", scale=theme.fontScale()).GetPointSize()
	core.conf()["largeText"] = False
	R.check("ACE-13 larger text increases the fonts", big > normal, (normal, big))

	# ACE-17 clean speech
	core.conf()["stripMarkdown"] = True
	R.check("ACE-17 Markdown symbols removed from speech", "#" not in plugin.session.speechText("# Oi **mundo**") and "*" not in plugin.session.speechText("# Oi **mundo**"))

	# ACE-18 long messages
	longText = "palavra " * 3000
	label = dlg._entryLabel(core.ChatEntry("assistant", longText, providerName="Claude"))
	R.check("ACE-18 long messages are shortened in the list", len(label) <= chatDialog.LIST_ITEM_LIMIT + 20 and label.endswith("…"), len(label))

	plugin.terminate()

	# ACE-15 translator comments / ACE-16 complete translation
	pot = os.path.join(tempfile.mkdtemp(), "nvda.pot")
	files = sorted(os.path.join(PKG, f) for f in os.listdir(PKG) if f.endswith(".py"))
	subprocess.run(["xgettext", "--language=Python", "--keyword=_", "--add-comments=Translators:", "--from-code=UTF-8", "-o", pot] + files, check=True)
	entries = _readPot(pot)
	noComment = [msgid for msgid, comment in entries if msgid and not comment]
	R.check("ACE-15 every translatable text has a Translators comment", not noComment, noComment[:15])
	mo = gettext.GNUTranslations(open(os.path.join(ROOT, "addon", "locale", "pt_BR", "LC_MESSAGES", "nvda.mo"), "rb"))
	missing = [m for m, _c in entries if m and m not in mo._catalog]
	R.check("ACE-16 interface fully translated to pt_BR", not missing, missing[:15])
	bad = [m for m, _c in entries if m in mo._catalog and sorted(re.findall(r"\{\w+\}", m)) != sorted(re.findall(r"\{\w+\}", mo._catalog[m]))]
	R.check("ACE-16 pt_BR keeps the {placeholders}", not bad, bad)


def _readPot(path):
	"""[(msgid, has_translator_comment)] from a .pot file."""
	out = []
	comment = False
	msgid = None
	section = None
	with open(path, encoding="utf-8") as f:
		for line in f:
			line = line.rstrip("\n")
			if line.startswith("#. Translators:") or (line.startswith("#.") and comment):
				comment = True
			elif line.startswith("msgid "):
				msgid = ast.literal_eval(line[6:])
				section = "id"
			elif line.startswith('"') and section == "id":
				msgid += ast.literal_eval(line)
			elif line.startswith("msgstr"):
				out.append((msgid, comment))
				comment = False
				section = None
	return out


try:
	run()
except Exception:
	import traceback
	traceback.print_exc()
	R.check("suite ran to the end", False, "exception")
sys.exit(R.finish())
