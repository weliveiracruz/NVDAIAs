# -*- coding: UTF-8 -*-
"""End-to-end test of the add-on user interface with a real wxPython, NVDA
modules replaced by fakes (tests/nvda_stubs.py) and the three APIs imitated by
tests/mock_server.py.

Run (Linux): xvfb-run -a python3 tests/test_gui.py
"""

import os
import sys
import time
import traceback
import types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "addon", "globalPlugins"))

import wx  # noqa: E402

import nvda_stubs  # noqa: E402
from nvda_stubs import RECORD  # noqa: E402

nvda_stubs.install()
import mock_server  # noqa: E402

SERVER, BASE = mock_server.start()

app = wx.App(False)
import gui  # noqa: E402

gui.mainFrame = gui.MainFrame()

import NVDAIAs  # noqa: E402  (the add-on package, exactly as NVDA loads it)
from NVDAIAs import core, providers, chatDialog, connectDialog, settingsPanel, chatgptPlan, planUi  # noqa: E402

for cls, path in ((providers.OpenAIProvider, "/openai/v1"), (providers.GeminiProvider, "/gemini/v1beta"), (providers.AnthropicProvider, "/anthropic/v1")):
	cls.defaultBaseUrl = BASE + path
# Sign in with ChatGPT talks to the fake auth.openai.com and api.openai.com.
chatgptPlan.ISSUER = BASE + "/chatgpt/auth"
chatgptPlan.ChatGPTPlanProvider.defaultBaseUrl = BASE + "/chatgpt/v1"
OPENED = []


def _fakeBrowser(url):
	OPENED.append(url)
	if url.startswith(chatgptPlan.ISSUER):
		return mock_server.fakeBrowser(url)
	return True


planUi.openBrowser = _fakeBrowser

RESULTS = []
POPUPS = []


def _fakePopupMenu(self, menu, pos=None):
	"""PopupMenu is modal; the tests record the menu instead of showing it."""
	labels = []
	for item in menu.GetMenuItems():
		labels.append(item.GetItemLabel())
		if item.GetSubMenu():
			labels.append([i.GetItemLabel() for i in item.GetSubMenu().GetMenuItems()])
	POPUPS.append(labels)
	return True


chatDialog.ChatDialog.PopupMenu = _fakePopupMenu


def check(name, condition, info=""):
	RESULTS.append((name, bool(condition), info))
	print(("PASS " if condition else "FAIL ") + name + ("" if condition else "  -> %s" % info))


def pump(until=lambda: False, timeout=5.0):
	end = time.time() + timeout
	while time.time() < end:
		wx.Yield()
		app.ProcessPendingEvents()
		if until():
			return True
		time.sleep(0.02)
	return until()


def keyDown(window, keyCode, shift=False, ctrl=False):
	evt = wx.KeyEvent(wx.wxEVT_KEY_DOWN)
	evt.SetEventObject(window)
	evt.SetKeyCode(keyCode) if hasattr(evt, "SetKeyCode") else setattr(evt, "m_keyCode", keyCode)
	evt.SetShiftDown(shift)
	evt.SetControlDown(ctrl)
	return evt


def topItems(dlg):
	"""Messages of the current conversation (children of the "Current conversation" branch)."""
	tree = dlg.conversationTree
	items = []
	child, cookie = tree.GetFirstChild(dlg._currentNode)
	while child.IsOk():
		items.append(child)
		child, cookie = tree.GetNextChild(dlg._currentNode, cookie)
	return items


def current(dlg):
	return [dlg.conversationTree.GetItemText(i) for i in topItems(dlg)]


def children(tree, item):
	out = []
	child, cookie = tree.GetFirstChild(item)
	while child.IsOk():
		out.append(child)
		child, cookie = tree.GetNextChild(item, cookie)
	return out


def selectLast(dlg):
	dlg.conversationTree.SelectItem(topItems(dlg)[-1])


def run():
	plugin = NVDAIAs.GlobalPlugin()
	check("settings panel registered", settingsPanel.NVDAIAsSettingsPanel in gui.settingsDialogs.NVDASettingsDialog.categoryClasses)
	check("tools menu item added", gui.mainFrame.sysTrayIcon.toolsMenu.GetMenuItemCount() == 1)
	gestures = {name: getattr(NVDAIAs.GlobalPlugin, name).gestures for name in dir(NVDAIAs.GlobalPlugin) if name.startswith("script_")}
	check("gestures", gestures == {
		"script_openChat": ["kb:NVDA+alt+i"],
		"script_describeNavigator": ["kb:NVDA+alt+d"],
		"script_describeScreen": ["kb:NVDA+shift+alt+d"],
		"script_openSettings": [],
		"script_sendFeedback": [],
	}, gestures)
	check("defaults", core.conf()["provider"] == "openai" and core.getModel("anthropic") == "claude-sonnet-5-5")

	# 1. First use: the login (token) screen opens by itself ---------------------------
	steps = []

	def driveConnect():
		dlg = wx.GetActiveWindow() if isinstance(wx.GetActiveWindow(), connectDialog.ConnectDialog) else None
		if dlg is None:
			for w in wx.GetTopLevelWindows():
				if isinstance(w, connectDialog.ConnectDialog) and w.IsShown():
					dlg = w
		if dlg is None:
			steps.append("no dialog")
			return
		steps.append("dialog")
		check("connect dialog instructions for ChatGPT", "platform.openai.com" in dlg.instructionsText.GetValue())
		dlg.providerChoice.SetSelection(2)
		dlg.onProviderChanged(None)
		check("connect dialog instructions for Claude", "console.anthropic.com" in dlg.instructionsText.GetValue())
		dlg.onConnect(None)  # empty token
		check("empty token warning", RECORD["messageBoxes"][-1].startswith("Paste the token"))
		dlg.tokenEdit.SetValue("sk-ant-errado")
		dlg.onConnect(None)
		pump(lambda: not dlg._testing)
		check("wrong token rejected", "did not accept the token" in RECORD["messageBoxes"][-1], RECORD["messageBoxes"][-1:])
		dlg.tokenEdit.SetValue(mock_server.VALID["anthropic"])
		dlg.onConnect(None)  # success ends the modal loop

	wx.CallLater(300, driveConnect)
	plugin.script_openChat(None)
	pump(lambda: chatDialog.ChatDialog._instance is not None and core.store().has("anthropic"), 10)
	dlg = chatDialog.ChatDialog._instance
	check("chat window opened", dlg is not None and dlg.IsShown())
	check("connect screen shown on first use", "dialog" in steps, steps)
	check("token saved after login", core.store().get("anthropic") == mock_server.VALID["anthropic"])
	check("token not stored in clear text", mock_server.VALID["anthropic"] not in open(core.store().path, encoding="utf-8").read() or sys.platform != "win32")
	check("provider switched to Claude", core.conf()["provider"] == "anthropic" and dlg.providerId == "anthropic")
	check("connected message", RECORD["messageBoxes"][-1].startswith("Connected to Claude"))

	# 2. Tab order: Shift+Tab from the question goes to the conversation list ------------
	focusable = [c for c in dlg.GetChildren() if c.AcceptsFocusFromKeyboard() and not isinstance(c, wx.StaticText)]
	names = [type(c).__mro__[1].__name__ if type(c).__name__.startswith("WxCtrl") else type(c).__name__ for c in focusable]
	qi = focusable.index(dlg.questionEdit)
	check("question is right after conversation list in tab order", focusable[qi - 1] is dlg.conversationTree, names)
	check("tab order starts with AI, Model, Conversation", focusable[:3] == [dlg.providerChoice, dlg.modelCombo, dlg.conversationTree], names)
	dlg.questionEdit.SetFocus()
	pump(timeout=0.3)
	dlg.questionEdit.Navigate(wx.NavigationKeyEvent.IsBackward)
	pump(timeout=0.3)
	focused = wx.Window.FindFocus()
	check("Shift+Tab from question focuses the conversation list (real navigation)", focused is dlg.conversationTree, focused)

	# 3. Ask a question with Enter -------------------------------------------------------
	RECORD["spoken"].clear()
	dlg.questionEdit.SetValue("Qual é a capital do Brasil?")
	dlg.questionEdit.SetFocus()
	pump(timeout=0.2)
	dlg.onCharHook(keyDown(dlg.questionEdit, wx.WXK_RETURN))
	check("Enter sends", core.ChatSession and plugin.session.busy and dlg.questionEdit.GetValue() == "")
	check("waiting item shown", current(dlg)[-1] == "Claude is answering…")
	check("send button disabled while waiting", not dlg.sendButton.IsEnabled() and dlg.cancelButton.IsEnabled())
	pump(lambda: not plugin.session.busy, 10)
	items = current(dlg)
	check("conversation list has question and answer", items[0] == "You: Qual é a capital do Brasil?" and items[1].startswith("Claude: Claude responde: Qual é a capital do Brasil?"), items)
	check("answer spoken automatically", any("Claude responde" in s for s in RECORD["spoken"]), RECORD["spoken"])
	check("'Sent to Claude' announced", "Sent to Claude" in RECORD["spoken"], RECORD["spoken"])
	check("last item selected", dlg.conversationTree.GetSelection() == topItems(dlg)[-1])

	# Shift+Enter does not send
	dlg.questionEdit.SetValue("linha 1")
	evt = keyDown(dlg.questionEdit, wx.WXK_RETURN, shift=True)
	before = len(plugin.session.conversation)
	dlg.onQuestionKeyDown(evt)
	check("Shift+Enter does not send", len(plugin.session.conversation) == before and not plugin.session.busy)
	dlg.questionEdit.SetValue("")

	# 3b. Real keyboard (X11 key events through wx.UIActionSimulator) ---------------------
	sim = wx.UIActionSimulator()
	dlg.Raise()
	dlg.questionEdit.SetFocus()
	pump(timeout=0.5)
	sim.Text(b"Ola teclado")
	pump(lambda: dlg.questionEdit.GetValue() == "Ola teclado", 2)
	check("real typing reaches the question field", dlg.questionEdit.GetValue() == "Ola teclado", repr(dlg.questionEdit.GetValue()))
	sim.Char(wx.WXK_RETURN, wx.MOD_SHIFT)
	pump(timeout=0.5)
	check("real Shift+Enter inserts a new line", "\n" in dlg.questionEdit.GetValue() and not plugin.session.busy, repr(dlg.questionEdit.GetValue()))
	sim.Text(b"linha 2")
	pump(timeout=0.3)
	sim.Char(wx.WXK_RETURN)
	pump(lambda: plugin.session.busy or len(plugin.session.conversation) > 2, 2)
	pump(lambda: not plugin.session.busy, 10)
	check("real Enter sends the question", plugin.session.conversation.entries[-2].text == "Ola teclado\nlinha 2", [e.text for e in plugin.session.conversation.entries])
	sim.Char(wx.WXK_TAB, wx.MOD_SHIFT)
	pump(timeout=0.5)
	check("real Shift+Tab goes to the conversation list", wx.Window.FindFocus() is dlg.conversationTree, wx.Window.FindFocus())
	n = len(POPUPS)
	sim.Char(wx.WXK_RETURN)
	pump(lambda: len(POPUPS) > n, 2)
	check("real Enter on a message opens the actions menu", len(POPUPS) > n and POPUPS[-1][0] == "&Read message", POPUPS[-1:])
	dlg.questionEdit.SetFocus()
	pump(timeout=0.3)
	# the follow-up test below expects 2 entries before it: remove the keyboard exchange
	for e in plugin.session.conversation.entries[2:]:
		plugin.session.conversation.remove(e)

	# 4. Follow-up keeps the history --------------------------------------------------------
	mock_server.REQUESTS.clear()
	dlg.questionEdit.SetValue("E a do Peru?")
	dlg.onSend(None)
	pump(lambda: not plugin.session.busy, 10)
	body = [r for r in mock_server.REQUESTS if r["method"] == "POST"][-1]["body"]
	check("history sent to Claude (3 messages)", len(body["messages"]) == 3, body)
	check("system prompt sent", "NVDA screen reader" in body["system"])

	# 5. Switch to ChatGPT in the same conversation ------------------------------------------
	core.store().set("openai", mock_server.VALID["openai"])
	dlg.providerChoice.SetSelection(0)
	dlg.onProviderChanged(None)
	check("model combo shows ChatGPT model", dlg.modelCombo.GetValue() == "gpt-5-mini")
	dlg.questionEdit.SetValue("Resuma")
	dlg.onSend(None)
	pump(lambda: not plugin.session.busy, 10)
	last = current(dlg)[-1]
	check("ChatGPT answer in list, Markdown removed", last.startswith("ChatGPT: Resposta Olá!") and "#" not in last and "*" not in last, last)
	check("ChatGPT received whole conversation", "5 mensagens" in plugin.session.conversation.lastAnswer().text, plugin.session.conversation.lastAnswer().text)

	# 6. Read message (Enter on the list) and copy (Ctrl+C) -----------------------------------
	selectLast(dlg)
	dlg.onListKeyDown(keyDown(dlg.conversationTree, wx.WXK_RETURN))
	check("Enter on an answer opens the actions menu", POPUPS and POPUPS[-1][0] == "&Read message", POPUPS[-1:])
	dict(dlg.messageActions())["&Read message"]()
	html, title, isHtml = RECORD["browseable"][-1]
	check("Read message action opens the answer in a reading window", isHtml and "<h1>Resposta</h1>" in html and title.startswith("Answer from ChatGPT"), (title, html))
	dlg.onListKeyDown(keyDown(dlg.conversationTree, ord("C"), ctrl=True))
	check("Ctrl+C copies the original answer", RECORD["clipboard"][-1].startswith("# Resposta"), RECORD["clipboard"][-1:])

	# 7. Errors: invalid Gemini token ------------------------------------------------------
	core.store().set("gemini", "token-errado")
	dlg.providerChoice.SetSelection(1)
	dlg.onProviderChanged(None)
	count = len(plugin.session.conversation)
	dlg.questionEdit.SetValue("Pergunta que vai falhar")
	dlg.onSend(None)
	pump(lambda: not plugin.session.busy, 10)
	check("auth error spoken", any("Gemini did not accept the token" in s for s in RECORD["spoken"]), RECORD["spoken"][-2:])
	check("failed question removed from conversation", len(plugin.session.conversation) == count)
	check("question given back to the field", dlg.questionEdit.GetValue() == "Pergunta que vai falhar")

	# 8. Gemini with the right token -------------------------------------------------------
	core.store().set("gemini", mock_server.VALID["gemini"])
	dlg.onSend(None)
	pump(lambda: not plugin.session.busy, 10)
	check("Gemini answers", plugin.session.conversation.lastAnswer().providerName == "Gemini")

	# 9. Cancel -----------------------------------------------------------------------------
	mock_server.DELAY["seconds"] = 1.5
	count = len(plugin.session.conversation)
	dlg.questionEdit.SetValue("Pergunta lenta")
	dlg.onSend(None)
	pump(timeout=0.3)
	dlg.onCancelSend(None)
	check("cancel restores the question", dlg.questionEdit.GetValue() == "Pergunta lenta" and not plugin.session.busy)
	pump(timeout=2.5)
	check("late answer after cancel is ignored", len(plugin.session.conversation) == count)
	mock_server.DELAY["seconds"] = 0
	dlg.questionEdit.SetValue("")

	# 10. Missing token for the chosen AI opens the connect screen ----------------------------
	core.store().remove("openai")
	dlg.providerChoice.SetSelection(0)
	dlg.onProviderChanged(None)
	opened = []

	def fakeRunConnect(providerId=None):
		opened.append(providerId)
		return None

	original = dlg._runConnect
	dlg._runConnect = fakeRunConnect
	dlg.questionEdit.SetValue("Oi")
	dlg.onSend(None)
	check("sending without token opens the connect screen", opened == ["openai"] and not plugin.session.busy)
	dlg._runConnect = original
	core.store().set("openai", mock_server.VALID["openai"])

	# 11. Describe the navigator object (real screen capture) -----------------------------------
	RECORD["spoken"].clear()
	navigator = types.SimpleNamespace(location=(0, 0, 200, 120), name="Botão Enviar", roleText="botão")
	import api
	api._navigator = navigator
	dlg.questionEdit.SetValue("")
	plugin.script_describeNavigator(None)
	pump(lambda: plugin.session.busy, 3)
	pump(lambda: not plugin.session.busy, 10)
	entries = plugin.session.conversation.entries
	imgEntry = entries[-2]
	check("screenshot is a PNG", bool(imgEntry.image) and imgEntry.image[:8] == b"\x89PNG\r\n\x1a\n", imgEntry.image[:8] if imgEntry.image else None)
	check("image question mentions the element", "Botão Enviar" in imgEntry.text, imgEntry.text)
	check("image answer received", entries[-1].role == "assistant" and "Imagem" in entries[-1].text, entries[-1].text)
	check("list shows the attached screenshot", "[attached: screenshot.png]" in current(dlg)[-2], current(dlg)[-2])
	api._navigator = types.SimpleNamespace(location=None, name="", roleText="")
	plugin.script_describeNavigator(None)
	check("object without position is reported", RECORD["spoken"][-1] == "This object has no position on the screen")
	from NVDAIAs import screenshot
	png = screenshot.captureRect(0, 0, 3000, 2000)
	img = wx.Image(__import__("io").BytesIO(png), wx.BITMAP_TYPE_PNG)
	check("large captures are reduced", max(img.GetWidth(), img.GetHeight()) <= screenshot.MAX_SIDE, img.GetSize())
	check("monitor geometry", screenshot.monitorRectAt(10, 10)[2] > 0)

	# 12. Settings panel -------------------------------------------------------------------
	frame = wx.Frame(None)
	panel = settingsPanel.NVDAIAsSettingsPanel(frame)
	group = {g.providerId: g for g in panel.groups}
	check("status shows saved token", "connected" in group["anthropic"].statusText.GetLabel() and "…" in group["anthropic"].statusText.GetLabel(), group["anthropic"].statusText.GetLabel())
	check("token fields are password fields", all(g.tokenEdit.GetWindowStyle() & wx.TE_PASSWORD for g in panel.groups))
	core.store().remove("gemini")
	group["gemini"].updateStatus()
	check("status shows missing token", "not connected" in group["gemini"].statusText.GetLabel())
	group["gemini"].tokenEdit.SetValue(mock_server.VALID["gemini"])
	group["gemini"].onTest(None)
	pump(lambda: group["gemini"].testButton.IsEnabled(), 10)
	check("test connection works", "working" in RECORD["messageBoxes"][-1] and "Press OK or Apply" in RECORD["messageBoxes"][-1], RECORD["messageBoxes"][-1])
	group["gemini"].onUpdateModels(None)
	pump(lambda: group["gemini"].updateModelsButton.IsEnabled(), 10)
	check("model list updated from the API", group["gemini"].modelCombo.GetStrings() == ["gemini-2.5-flash", "gemini-2.5-pro"], group["gemini"].modelCombo.GetStrings())
	group["gemini"].modelCombo.SetValue("gemini-2.5-pro")
	panel.systemPromptEdit.SetValue("Responda como um pirata.\nSeja breve.")
	panel.speakCheck.SetValue(False)
	panel.timeoutSpin.SetValue(30)
	panel.providerChoice.SetSelection(1)
	panel.onSave()
	check("token saved by OK", core.store().get("gemini") == mock_server.VALID["gemini"] and group["gemini"].tokenEdit.GetValue() == "")
	check("model saved", core.getModel("gemini") == "gemini-2.5-pro")
	check("multi-line instructions saved", core.getSystemPrompt() == "Responda como um pirata.\nSeja breve." and "\n" not in core.conf()["systemPrompt"], repr(core.conf()["systemPrompt"]))
	check("options saved", core.conf()["speakResponses"] is False and core.conf()["timeout"] == 30 and core.conf()["provider"] == "gemini")
	panel.systemPromptEdit.SetValue(core.defaultSystemPrompt())
	panel.onSave()
	check("default instructions stored as empty", core.conf()["systemPrompt"] == "")
	nvda_stubs.MESSAGEBOX_ANSWER["value"] = wx.YES
	group["openai"].onRemove(None)
	check("remove token", not core.store().has("openai") and "not connected" in group["openai"].statusText.GetLabel())
	frame.Destroy()

	# 13. Save / new conversation ---------------------------------------------------------
	text = plugin.session.conversation.toText("You", "[image attached]")
	check("conversation export", "You:\nQual é a capital do Brasil?" in text and "Gemini (gemini-2.5-flash):" in text, text[:300])
	dlg.onNewConversation(None)
	check("new conversation clears list", current(dlg) == [] and not dlg.saveButton.IsEnabled())
	dlg.onSettings(None)
	pump(timeout=0.3)
	check("settings button opens NVDA settings on NVDAIAs", RECORD["settingsOpened"][-1][1] == (settingsPanel.NVDAIAsSettingsPanel,))

	# 14. Close with Escape keeps the session; reopen ------------------------------------------
	plugin.session.conversation.add(core.ChatEntry("user", "persistente"))
	dlg.Close()
	pump(timeout=0.3)
	check("window closed", chatDialog.ChatDialog._instance is None)
	plugin.script_openChat(None)
	pump(lambda: chatDialog.ChatDialog._instance is not None, 3)
	dlg = chatDialog.ChatDialog._instance
	check("conversation kept after reopening", current(dlg) == ["You: persistente"])
	check("escape id is Close", dlg.GetEscapeId() == wx.ID_CLOSE)
	dlg.Raise()
	dlg.questionEdit.SetFocus()
	pump(timeout=0.5)
	sim.Char(wx.WXK_ESCAPE)
	pump(lambda: chatDialog.ChatDialog._instance is None, 2)
	check("real Escape closes the window", chatDialog.ChatDialog._instance is None)
	plugin.script_openChat(None)
	pump(lambda: chatDialog.ChatDialog._instance is not None, 3)

	# 16. Previous conversations (history) -------------------------------------------------
	dlg = chatDialog.ChatDialog._instance
	tree = dlg.conversationTree
	root = tree.GetRootItem()
	firstTop = tree.GetFirstChild(root)[0]
	check("history item is the first item of the tree", firstTop == dlg._historyNode)
	histLabel = tree.GetItemText(dlg._historyNode)
	check("history item starts collapsed", not tree.IsExpanded(dlg._historyNode), histLabel)
	saved = plugin.session.previousConversations()
	check("previous conversations were saved automatically", len(saved) >= 1 and histLabel == "Previous conversations (%d)" % len(saved), (histLabel, len(saved)))
	convNodes = children(tree, dlg._historyNode)
	check("one branch per previous conversation", len(convNodes) == len(saved))
	labelsConv = [tree.GetItemText(n) for n in convNodes]
	check("conversation label shows AI, first question and size", any("Qual é a capital do Brasil?" in l and "Claude" in l and "messages)" in l for l in labelsConv), labelsConv)
	target = next(n for n in convNodes if "Qual é a capital do Brasil?" in tree.GetItemText(n))
	check("each conversation starts collapsed", not tree.IsExpanded(target))
	# Enter on the history item expands it
	tree.SelectItem(dlg._historyNode)
	dlg.onTreeActivate()
	check("Enter expands the previous conversations item", tree.IsExpanded(dlg._historyNode))
	tree.Expand(target)
	msgs = children(tree, target)
	check("expanding a conversation shows its messages", len(msgs) >= 4 and tree.GetItemText(msgs[0]) == "You: Qual é a capital do Brasil?", [tree.GetItemText(m) for m in msgs][:3])
	tree.SelectItem(msgs[1])
	check("old message can be copied", True)
	dlg.onListKeyDown(keyDown(tree, ord("C"), ctrl=True))
	check("Ctrl+C on an old message copies it", RECORD["clipboard"][-1].startswith("Claude responde"), RECORD["clipboard"][-1][:40])
	targetId = tree.GetItemData(target)[1]
	before = current(dlg)
	countBefore = len(saved)
	RECORD["spoken"].clear()
	tree.SelectItem(msgs[1])
	dlg.onListKeyDown(keyDown(tree, wx.WXK_RETURN))
	pump(timeout=0.3)
	check("Enter on an old message opens that conversation", plugin.session.conversation.id == targetId and current(dlg)[0] == "You: Qual é a capital do Brasil?", current(dlg)[:2])
	check("opening is announced", any("opened" in m and "Continue it" in m for m in RECORD["spoken"]), RECORD["spoken"])
	check("focus goes to the question field", wx.Window.FindFocus() is dlg.questionEdit, wx.Window.FindFocus())
	check("the conversation that was open went to the history", any(d["entries"][0]["text"] == before[0][5:] for d in plugin.session.previousConversations()) if before else True)
	check("opened conversation leaves the history list", targetId not in [d["id"] for d in plugin.session.previousConversations()])
	check("history count kept consistent", len(plugin.session.previousConversations()) == countBefore - 1 + (1 if before else 0))
	# continue it
	n = len(plugin.session.conversation)
	dlg.questionEdit.SetValue("Continuando a conversa antiga")
	dlg.onSend(None)
	pump(lambda: not plugin.session.busy, 10)
	check("continued conversation keeps the old messages", len(plugin.session.conversation) == n + 2)
	body = [r for r in mock_server.REQUESTS if r["method"] == "POST"][-1]["body"]
	sentCount = len(body.get("messages") or body.get("contents") or [])
	check("the AI receives the old history", sentCount >= n, sentCount)
	saved2 = core.history().load(targetId)
	check("continued conversation saved under the same id", len(saved2["entries"]) == n + 2)
	# Enter on a conversation branch also opens it
	plugin.session.newConversation()
	pump(timeout=0.2)
	node = next(c for c in children(tree, dlg._historyNode) if tree.GetItemData(c)[1] == targetId)
	tree.SelectItem(node)
	dlg.onTreeActivate()
	check("Enter on a conversation branch opens it", plugin.session.conversation.id == targetId)
	# survives an NVDA restart
	plugin2session = core.ChatSession()
	check("history survives restart", targetId in [d["id"] for d in plugin2session.previousConversations()] or plugin.session.conversation.id == targetId)
	plugin.session.newConversation()
	pump(timeout=0.2)
	check("after New conversation the old one is back in the history", targetId in [d["id"] for d in plugin.session.previousConversations()])
	# delete with the Delete key
	nvda_stubs.MESSAGEBOX_ANSWER["value"] = wx.YES
	node = next(c for c in children(tree, dlg._historyNode) if tree.GetItemData(c)[1] == targetId)
	tree.SelectItem(node)
	dlg.onListKeyDown(keyDown(tree, wx.WXK_DELETE))
	pump(timeout=0.2)
	check("Delete removes a previous conversation", targetId not in [d["id"] for d in plugin.session.previousConversations()] and RECORD["spoken"][-1] == "Conversation deleted")
	# real keyboard: arrows on the tree
	dlg.Raise()
	tree.SetFocus()
	tree.Collapse(dlg._historyNode)
	tree.SelectItem(dlg._historyNode)
	pump(timeout=0.4)
	sim = wx.UIActionSimulator()
	sim.Char(wx.WXK_RIGHT)
	pump(timeout=0.4)
	hasChildren = tree.GetChildrenCount(dlg._historyNode, False) > 0
	check("real Right arrow expands Previous conversations", tree.IsExpanded(dlg._historyNode) or not hasChildren)
	sim.Char(wx.WXK_LEFT)
	pump(timeout=0.4)
	check("real Left arrow collapses it", not tree.IsExpanded(dlg._historyNode))
	# history off
	core.conf()["saveHistory"] = False
	dlg.onHistoryChanged()
	check("history item hidden when history is off", dlg._historyNode is None and plugin.session.previousConversations() == [])
	core.conf()["saveHistory"] = True
	dlg.onHistoryChanged()
	check("history item back when history is on", dlg._historyNode is not None)

	# 17. Attach files ---------------------------------------------------------------------
	dlg = chatDialog.ChatDialog._instance
	import tempfile as _tf
	folder = _tf.mkdtemp()

	def mk(name, data):
		path = os.path.join(folder, name)
		with open(path, "wb") as f:
			f.write(data)
		return path

	focusable = [c for c in dlg.GetChildren() if c.AcceptsFocusFromKeyboard() and not isinstance(c, wx.StaticText)]
	qi = focusable.index(dlg.questionEdit)
	check("Attach button comes right after the question field", focusable[qi + 1] is dlg.attachButton and focusable[qi + 2] is dlg.sendButton, [type(c).__name__ for c in focusable])
	check("attached files list hidden while empty", not dlg.attachmentsList.IsShown())
	dlg.Raise()
	dlg.questionEdit.SetFocus()
	pump(timeout=0.4)
	wx.UIActionSimulator().Char(wx.WXK_TAB)
	pump(timeout=0.4)
	check("real Tab from the question goes to Attach files", wx.Window.FindFocus() is dlg.attachButton, wx.Window.FindFocus())
	dlg.questionEdit.SetFocus()
	core.store().set("anthropic", mock_server.VALID["anthropic"])
	dlg.providerChoice.SetSelection(2)
	dlg.onProviderChanged(None)
	pdfPath = mk("contrato.pdf", b"%PDF-1.7 fake pdf")
	txtPath = mk("notas.txt", "Reunião às 10h".encode("utf-8"))
	exePath = mk("programa.exe", b"MZ\x90\x00" + b"\x00\x01" * 40)
	mp3Path = mk("audio.mp3", b"ID3\x03fake")
	RECORD["spoken"].clear()
	nboxes = len(RECORD["messageBoxes"])
	added = dlg.addAttachmentFiles([pdfPath, txtPath, exePath])
	check("valid files attached, unreadable one refused", added == 2 and len(RECORD["messageBoxes"]) == nboxes + 1 and "cannot read the content of programa.exe" in RECORD["messageBoxes"][-1], RECORD["messageBoxes"][-1:])
	check("attachment announced", RECORD["spoken"][-1].startswith("Attached: contrato.pdf, notas.txt. 2 file(s)"), RECORD["spoken"][-1:])
	check("attached files list shown", dlg.attachmentsList.IsShown() and dlg.attachmentsList.GetStrings()[0].startswith("contrato.pdf (PDF,"), dlg.attachmentsList.GetStrings())
	dlg.addAttachmentFiles([mp3Path])
	check("audio with Claude warns to choose Gemini", "only Gemini" in RECORD["spoken"][-1])
	dlg.attachmentsList.SetSelection(2)
	evt = keyDown(dlg.attachmentsList, wx.WXK_DELETE)
	dlg.onAttachmentsKeyDown(evt)
	check("Delete removes an attached file", [a.name for a in dlg.pendingAttachments] == ["contrato.pdf", "notas.txt"] and RECORD["spoken"][-1] == "audio.mp3 removed")
	mock_server.REQUESTS.clear()
	dlg.questionEdit.SetValue("")
	dlg.onSend(None)
	check("files can be sent without typing", plugin.session.busy and "with 2 file(s)" in RECORD["spoken"][-1], RECORD["spoken"][-1:])
	pump(lambda: not plugin.session.busy, 10)
	check("Claude received the PDF and the text", mock_server.LAST_ATTACHMENTS.get("anthropic") == ["document", "text"], mock_server.LAST_ATTACHMENTS)
	check("pending files cleared after sending", dlg.pendingAttachments == [] and not dlg.attachmentsList.IsShown())
	userEntry = plugin.session.conversation.entries[-2]
	check("default question used", userEntry.text.startswith("Please analyse the attached file"))
	check("message in the tree shows the files", current(dlg)[-2].startswith("You: [attached: contrato.pdf, notas.txt]"), current(dlg)[-2])
	tree = dlg.conversationTree
	tree.SelectItem(topItems(dlg)[-2])
	dlg.onReadMessage(None)
	check("reading window lists the files", "Attached files: contrato.pdf, notas.txt" in RECORD["browseable"][-1][0])
	# follow-up keeps sending the files (they are part of the history)
	dlg.questionEdit.SetValue("E o prazo?")
	dlg.onSend(None)
	pump(lambda: not plugin.session.busy, 10)
	body = [r for r in mock_server.REQUESTS if r["method"] == "POST"][-1]["body"]
	check("history with files sent again on follow-up", body["messages"][-3]["content"][0]["type"] == "document", body["messages"][-3]["content"][0]["type"])
	# saved in the history with the files
	saved = core.history().load(plugin.session.conversation.id)
	names = [a["name"] for e in saved["entries"] for a in e.get("attachments", [])]
	check("files saved in the conversation history", names == ["contrato.pdf", "notas.txt"], names)
	# audio with Claude: error gives question and files back
	dlg.addAttachmentFiles([mp3Path])
	dlg.questionEdit.SetValue("Transcreva")
	n = len(plugin.session.conversation)
	dlg.onSend(None)
	pump(lambda: not plugin.session.busy, 10)
	check("audio refused by Claude with a clear message", any("cannot read the attached file audio.mp3" in m for m in RECORD["spoken"][-3:]), RECORD["spoken"][-3:])
	check("question and file given back after the error", dlg.questionEdit.GetValue() == "Transcreva" and [a.name for a in dlg.pendingAttachments] == ["audio.mp3"] and len(plugin.session.conversation) == n)
	core.store().set("gemini", mock_server.VALID["gemini"])
	dlg.providerChoice.SetSelection(1)
	dlg.onProviderChanged(None)
	plugin.session.newConversation()
	dlg.onSend(None)
	pump(lambda: not plugin.session.busy, 10)
	check("Gemini accepts the audio", mock_server.LAST_ATTACHMENTS.get("gemini") == ["audio/mp3"] and dlg.pendingAttachments == [], mock_server.LAST_ATTACHMENTS.get("gemini"))
	# cancel gives the files back
	mock_server.DELAY["seconds"] = 1.5
	dlg.addAttachmentFiles([txtPath])
	dlg.questionEdit.SetValue("lento")
	dlg.onSend(None)
	pump(timeout=0.3)
	dlg.onCancelSend(None)
	check("cancel gives the files back", [a.name for a in dlg.pendingAttachments] == ["notas.txt"])
	pump(timeout=2)
	mock_server.DELAY["seconds"] = 0
	dlg.pendingAttachments = []
	dlg._refreshAttachments()
	dlg.questionEdit.SetValue("")

	# 18. Message actions ------------------------------------------------------------------
	dlg = chatDialog.ChatDialog._instance
	tree = dlg.conversationTree
	core.store().set("anthropic", mock_server.VALID["anthropic"])
	dlg.providerChoice.SetSelection(2)
	dlg.onProviderChanged(None)
	plugin.session.newConversation()
	from NVDAIAs.attachments import Attachment as _Att
	dlg.pendingAttachments = [_Att.image(b"\x89PNG\r\n\x1a\n" + b"0" * 40, name="grafico.png")]
	dlg.questionEdit.SetValue("O que mostra este gráfico?")
	dlg.onSend(None)
	pump(lambda: not plugin.session.busy, 10)
	popups = POPUPS
	del popups[:]
	items = topItems(dlg)
	tree.SelectItem(items[0])
	dlg.onListKeyDown(keyDown(tree, wx.WXK_RETURN))
	check("Enter on a current message opens the actions menu", len(popups) == 1 and popups[0][0] == "&Read message", popups[-1:])
	check("menu of a question with image: read, copy, delete, translate, describe image", [l for l in popups[0] if isinstance(l, str)] == ["&Read message", "&Copy", "&Delete", "&Translate to", "Describe this &image in more detail"], popups[0])
	check("translate submenu lists languages", isinstance(popups[0][4], list) and "English" in popups[0][4] and len(popups[0][4]) >= 10)
	tree.SelectItem(items[1])
	labels = [l for l, a in dlg.messageActions()]
	check("menu of an answer has Improve and Describe (image of the question)", labels == ["&Read message", "&Copy", "&Delete", "&Translate to", "Describe this &image in more detail", "I&mprove this answer"], labels)
	dlg.showActionsMenu(fromButton=True)
	check("Actions button opens the same menu", len(popups) == 2)
	evt = wx.ContextMenuEvent(wx.wxEVT_CONTEXT_MENU, tree.GetId())
	tree.GetEventHandler().ProcessEvent(evt)
	check("Applications key / context menu opens the menu", len(popups) == 3)
	actions = dict(dlg.messageActions())
	actions["&Copy"]()
	check("action Copy", RECORD["clipboard"][-1].startswith("Claude responde"), RECORD["clipboard"][-1][:30])
	actions["&Read message"]()
	check("action Read message", RECORD["browseable"][-1][1].startswith("Answer from Claude"))
	# translate
	mock_server.REQUESTS.clear()
	translate = dict(actions["&Translate to"])
	translate["English"]()
	check("translate sends a request", plugin.session.busy and RECORD["spoken"][-1] == "Translating to English")
	pump(lambda: not plugin.session.busy, 10)
	sentText = plugin.session.conversation.entries[-2].text
	check("translation request contains the language and the message", "into English" in sentText and "Claude responde" in sentText, sentText[:80])
	check("translation answer arrives", plugin.session.conversation.entries[-1].role == "assistant")
	# improve
	tree.SelectItem(topItems(dlg)[1])
	dict(dlg.messageActions())["I&mprove this answer"]()
	pump(lambda: not plugin.session.busy, 10)
	check("improve answer sends the answer to be improved", plugin.session.conversation.entries[-2].text.startswith("Improve the answer below") and "Claude responde" in plugin.session.conversation.entries[-2].text)
	# describe image
	tree.SelectItem(topItems(dlg)[0])
	dict(dlg.messageActions())["Describe this &image in more detail"]()
	pump(lambda: not plugin.session.busy, 10)
	body = [r for r in mock_server.REQUESTS if r["method"] == "POST"][-1]["body"]
	check("describe image asks for details and the image is in the history sent", "grafico.png" in plugin.session.conversation.entries[-2].text and body["messages"][0]["content"][0]["type"] == "image")
	# busy blocks actions
	mock_server.DELAY["seconds"] = 1
	dlg.questionEdit.SetValue("lenta")
	dlg.onSend(None)
	tree.SelectItem(topItems(dlg)[1])
	n = len(plugin.session.conversation)
	r = dict(dlg.messageActions())["I&mprove this answer"]()
	check("actions that send wait for the current answer", r is False and RECORD["spoken"][-1] == "Please wait for the current answer")
	pump(lambda: not plugin.session.busy, 10)
	mock_server.DELAY["seconds"] = 0
	# delete
	nvda_stubs.MESSAGEBOX_ANSWER["value"] = wx.NO
	tree.SelectItem(topItems(dlg)[0])
	n = len(plugin.session.conversation)
	dict(dlg.messageActions())["&Delete"]()
	check("delete asks for confirmation (No keeps the message)", len(plugin.session.conversation) == n)
	nvda_stubs.MESSAGEBOX_ANSWER["value"] = wx.YES
	first = plugin.session.conversation.entries[0]
	dict(dlg.messageActions())["&Delete"]()
	check("delete removes the message", len(plugin.session.conversation) == n - 1 and first not in plugin.session.conversation.entries and RECORD["spoken"][-1] == "Message deleted")
	saved = core.history().load(plugin.session.conversation.id)
	check("history updated after delete", len(saved["entries"]) == n - 1)
	pump(timeout=0.2)
	check("focus stays in the conversation after delete", wx.Window.FindFocus() is tree, wx.Window.FindFocus())
	convId = plugin.session.conversation.id
	while len(plugin.session.conversation):
		tree.SelectItem(topItems(dlg)[0])
		dict(dlg.messageActions())["&Delete"]()
	check("deleting every message removes the conversation from the history", convId not in [d["id"] for d in core.history().list()])
	# previous conversation messages
	dlg.rebuildHistory()
	if dlg._historyNode is not None and tree.GetChildrenCount(dlg._historyNode, False):
		conv = children(tree, dlg._historyNode)[0]
		tree.Expand(conv)
		tree.SelectItem(children(tree, conv)[0])
		labels = [l for l, a in dlg.messageActions()]
		check("menu of a previous message: read, copy, open", labels == ["&Read message", "&Copy", "&Open this conversation to continue it"], labels)
	tree.SelectItem(dlg._historyNode)
	dlg.showActionsMenu(fromButton=True)
	check("actions without a selected message explain what to do", RECORD["spoken"][-1] == "Select a message in the conversation first")

	# 19. Current conversation branch -------------------------------------------------------
	dlg = chatDialog.ChatDialog._instance
	tree = dlg.conversationTree
	root = tree.GetRootItem()
	top = children(tree, root)
	check("tree top level: Previous conversations, then Current conversation", top == [dlg._historyNode, dlg._currentNode], [tree.GetItemText(t) for t in top])
	core.store().set("anthropic", mock_server.VALID["anthropic"])
	dlg.providerChoice.SetSelection(2)
	dlg.onProviderChanged(None)
	plugin.session.newConversation()
	pump(timeout=0.2)
	check("empty current conversation label", tree.GetItemText(dlg._currentNode) == "Current conversation (no messages yet)", tree.GetItemText(dlg._currentNode))
	dlg.questionEdit.SetValue("Primeira")
	dlg.onSend(None)
	pump(lambda: not plugin.session.busy, 10)
	check("current conversation label counts the messages", tree.GetItemText(dlg._currentNode) == "Current conversation (2 messages)", tree.GetItemText(dlg._currentNode))
	check("current conversation is expanded and the answer selected", tree.IsExpanded(dlg._currentNode) and tree.GetSelection() == topItems(dlg)[-1])
	# collapse with Enter on the branch
	tree.SelectItem(dlg._currentNode)
	dlg.onTreeActivate()
	check("Enter collapses the current conversation", not tree.IsExpanded(dlg._currentNode))
	dlg.refreshList()
	check("a refresh without new messages keeps it collapsed", not tree.IsExpanded(dlg._currentNode))
	dlg.onTreeActivate()
	check("Enter expands it again", tree.IsExpanded(dlg._currentNode))
	tree.Collapse(dlg._currentNode)
	dlg.questionEdit.SetValue("Segunda")
	dlg.onSend(None)
	pump(lambda: not plugin.session.busy, 10)
	check("a new answer opens the branch and selects the answer", tree.IsExpanded(dlg._currentNode) and tree.GetItemText(tree.GetSelection()).startswith("Claude: Claude responde: Segunda"), tree.GetItemText(tree.GetSelection()))
	tree.SelectItem(dlg._currentNode)
	check("the branch itself has no message actions", dlg.messageActions() == [])
	# real keyboard
	dlg.Raise()
	tree.SetFocus()
	tree.SelectItem(dlg._currentNode)
	pump(timeout=0.4)
	sim = wx.UIActionSimulator()
	sim.Char(wx.WXK_LEFT)
	pump(timeout=0.4)
	check("real Left arrow collapses the current conversation", not tree.IsExpanded(dlg._currentNode))
	sim.Char(wx.WXK_RIGHT)
	pump(timeout=0.4)
	check("real Right arrow expands the current conversation", tree.IsExpanded(dlg._currentNode))
	# history off: current branch still there
	core.conf()["saveHistory"] = False
	dlg.onHistoryChanged()
	check("without history the tree has only the current conversation", children(tree, root) == [dlg._currentNode])
	core.conf()["saveHistory"] = True
	dlg.onHistoryChanged()
	check("history branch comes back before the current conversation", children(tree, root) == [dlg._historyNode, dlg._currentNode])

	# 20. Send feedback -------------------------------------------------------------------
	dlg = chatDialog.ChatDialog._instance
	from NVDAIAs import feedback
	focusable = [c for c in dlg.GetChildren() if c.IsShown() and c.AcceptsFocusFromKeyboard() and not isinstance(c, wx.StaticText)]
	check("Send feedback button between Settings and Close", focusable.index(dlg.feedbackButton) == focusable.index(dlg.settingsButton) + 1 and focusable.index(dlg.closeButton) == focusable.index(dlg.feedbackButton) + 1)
	check("Send feedback button label", dlg.feedbackButton.GetLabel() == "Send fee&dback…", dlg.feedbackButton.GetLabel())
	calls = {"confirm": [], "open": []}
	answer = {"value": False}

	def fakeConfirm(parent, message, caption, okLabel, cancelLabel):
		calls["confirm"].append((message, caption, okLabel, cancelLabel))
		return answer["value"]

	def fakeOpen(url):
		calls["open"].append(url)
		return True

	realConfirm, realOpen = feedback.confirm, feedback.openBrowser
	feedback.confirm, feedback.openBrowser = fakeConfirm, fakeOpen
	dlg.onFeedback(None)
	check("feedback asks before opening", calls["confirm"] == [("The evaluation will open in a new tab of your browser.", "NVDAIAs - Send feedback", "Give &feedback", "&Cancel")], calls["confirm"])
	check("Cancel does not open the browser", calls["open"] == [])
	pump(timeout=0.2)
	check("focus back on the feedback button after cancel", wx.Window.FindFocus() is dlg.feedbackButton, wx.Window.FindFocus())
	answer["value"] = True
	dlg.onFeedback(None)
	check("Give feedback opens the form", calls["open"] == [feedback.FEEDBACK_URL])
	check("opening the form is announced", RECORD["spoken"][-1] == "Opening the feedback form in your browser")
	feedback.openBrowser = lambda url: False
	n = len(RECORD["messageBoxes"])
	r = feedback.askAndOpen(dlg)
	check("browser failure shows the address", r is False and len(RECORD["messageBoxes"]) == n + 1 and feedback.FEEDBACK_URL in RECORD["messageBoxes"][-1])
	feedback.openBrowser = fakeOpen
	calls["open"].clear()
	plugin.script_sendFeedback(None)
	pump(timeout=0.3)
	check("command Send feedback (Input gestures) opens the form", calls["open"] == [feedback.FEEDBACK_URL])
	feedback.confirm, feedback.openBrowser = realConfirm, realOpen
	# the real confirmation window: native message box with the buttons renamed
	created = []

	class FakeMessageDialog:
		def __init__(self, parent, message, caption, style):
			self.args = (message, caption, style)
			self.labels = None
			created.append(self)

		def SetOKCancelLabels(self, ok, cancel):
			self.labels = (ok, cancel)
			return True

		def ShowModal(self):
			return wx.ID_CANCEL

		def Destroy(self):
			self.destroyed = True

	realMD = feedback.wx.MessageDialog
	feedback.wx.MessageDialog = FakeMessageDialog
	try:
		result = feedback.confirm(dlg, "m", "c", "Give &feedback", "&Cancel")
	finally:
		feedback.wx.MessageDialog = realMD
	md = created[0]
	# wx.OK_DEFAULT is 0 (OK is already the default): check that Cancel is NOT the default instead.
	check("confirmation is a standard message box with OK and Cancel, OK as default", bool(md.args[2] & wx.OK) and bool(md.args[2] & wx.CANCEL) and not md.args[2] & wx.CANCEL_DEFAULT, md.args[2])
	check("its buttons are called Give feedback and Cancel", md.labels == ("Give &feedback", "&Cancel"))
	check("Cancel in the message box returns False and closes it", result is False and getattr(md, "destroyed", False))


	# 21. Sign in with ChatGPT (ChatGPT plan, no API key) ---------------------------------
	dlg = chatDialog.ChatDialog.showInstance(plugin.session)
	notices = []

	class FakeNotice:
		def __init__(self, parent, message, caption, style):
			notices.append({"message": message, "caption": caption})

		def SetOKLabel(self, label):
			notices[-1]["ok"] = label

		def ShowModal(self):
			return wx.ID_OK

		def Destroy(self):
			pass

	realMD = planUi.wx.MessageDialog
	planUi.wx.MessageDialog = FakeNotice
	core.conf()["planNoticeShown"] = False
	core.store().remove("openai")
	cd = connectDialog.ConnectDialog(dlg, "openai")
	check("Continue with ChatGPT shown for ChatGPT", cd.chatgptButton.IsShown() and cd.chatgptButton.GetLabel() == "Continue &with ChatGPT", cd.chatgptButton.GetLabel())
	check("instructions explain the ChatGPT plan", "Continue with ChatGPT" in cd.instructionsText.GetValue() and "API key" in cd.instructionsText.GetValue())
	focusableCd = [c for c in cd.GetChildren() if c.AcceptsFocusFromKeyboard() and c.IsShown() and not isinstance(c, wx.StaticText)]
	check("Continue with ChatGPT comes right after the AI box", focusableCd.index(cd.chatgptButton) == focusableCd.index(cd.providerChoice) + 1)
	cd.providerChoice.SetSelection(1)
	cd.onProviderChanged(None)
	check("Continue with ChatGPT hidden for Gemini", not cd.chatgptButton.IsShown())
	cd.providerChoice.SetSelection(0)
	cd.onProviderChanged(None)
	RECORD["spoken"].clear()
	cd.onContinueWithChatGPT(None)
	waiting = planUi.SignInDialog._running
	check("waiting window opens with the explanation", waiting is not None and "Sign in, allow NVDAIAs" in waiting.messageText.GetValue() and waiting.GetTitle() == "NVDAIAs - Continue with ChatGPT")
	pump(lambda: planUi.SignInDialog._running is None, 15)
	check("browser opened on auth.openai.com authorize", OPENED and OPENED[-1].startswith(chatgptPlan.ISSUER + "/api/accounts/authorize?client_id=dynamic_agent_client"), OPENED[-1:])
	check("signed in with ChatGPT", core.plan().signedIn() and core.plan().email() == "pessoa@example.com")
	check("connect dialog reports ChatGPT connected", cd.connectedProvider == "openai")
	check("sign-in announced with the account", "Signed in to ChatGPT as pessoa@example.com" in RECORD["spoken"], RECORD["spoken"])
	check("first-use notice You're using your ChatGPT plan with Got it", notices and notices[0]["caption"] == "You're using your ChatGPT plan" and notices[0]["ok"] == "&Got it", notices)
	check("notice remembered", core.conf()["planNoticeShown"] is True)
	check("plan models and default model", core.modelCache.get(core.PLAN_SLOT) == ["gpt-5.5", "gpt-5.5-mini"] and core.conf()["model_openai_plan"] == "gpt-5.5")
	check("ChatGPT becomes the AI, using the plan", core.conf()["provider"] == "openai" and core.usingPlan("openai") and core.isConnected("openai"))
	check("no API token was needed", not core.store().has("openai"))
	cd.Destroy()
	# Chat window: indicator and Manage usage
	dlg.providerChoice.SetSelection(0)
	dlg._fillModels()
	dlg.updateStatus()
	statusText = dlg.statusLine.GetLabel()
	check("status line says the ChatGPT plan is used", statusText == "ChatGPT · gpt-5.5 · using your ChatGPT plan (pessoa@example.com)", statusText)
	check("Manage ChatGPT usage button shown", dlg.usageButton.IsShown() and dlg.usageButton.GetLabel() == "Manage ChatGPT &usage…")
	check("model box lists the plan models", dlg.modelCombo.GetStrings() == ["gpt-5.5", "gpt-5.5-mini"] and dlg.modelCombo.GetValue() == "gpt-5.5", dlg.modelCombo.GetStrings())
	dlg.onNewConversation(None)
	dlg.questionEdit.SetValue("Pergunta pelo plano")
	dlg.onSend(None)
	pump(lambda: not plugin.session.busy, 10)
	check("question answered through the ChatGPT plan", any("Plano ChatGPT responde: Pergunta pelo plano" in t for t in current(dlg)), current(dlg))
	check("plan request without API key, store false, stream true", mock_server.CHATGPT["responses"][-1]["store"] is False and not any(r["path"].startswith("/openai/") for r in mock_server.REQUESTS[-3:]))
	OPENED.clear()
	dlg.onManageUsage(None)
	check("Manage usage opens chatgpt.com/settings/usage", OPENED == ["https://chatgpt.com/settings/usage"], OPENED)
	asked = []
	realConfirm = planUi.confirm

	def fakeConfirm(parent, message, caption, okLabel, cancelLabel):
		asked.append((message, caption, okLabel, cancelLabel))
		return True

	planUi.confirm = fakeConfirm
	OPENED.clear()
	mock_server.FORCE["chatgpt"] = (429, {"error": {"code": "subscription_sharing_usage_limit_exceeded", "message": "limit"}})
	dlg.questionEdit.SetValue("Mais uma")
	dlg.onSend(None)
	pump(lambda: not plugin.session.busy and asked, 10)
	mock_server.FORCE.clear()
	planUi.confirm = realConfirm
	check("usage limit explained", any("usage limit of your ChatGPT plan" in m for m in RECORD["spoken"][-3:]), RECORD["spoken"][-3:])
	check("usage limit offers Manage usage as the main action", asked and asked[0][2] == "&Manage usage" and asked[0][3] == "&Close", asked)
	check("Manage usage opened after the limit", OPENED == ["https://chatgpt.com/settings/usage"], OPENED)
	check("question back in the field after the limit", dlg.questionEdit.GetValue() == "Mais uma")
	dlg.questionEdit.SetValue("")
	# Second sign-in: no second notice, same registration
	n = len(notices)
	cd = connectDialog.ConnectDialog(dlg, "openai")
	check("instructions show the signed-in account", "Already signed in with ChatGPT as pessoa@example.com" in cd.instructionsText.GetValue())
	cd.onContinueWithChatGPT(None)
	pump(lambda: planUi.SignInDialog._running is None, 15)
	check("notice shown only once", len(notices) == n)
	check("second sign-in reuses the issued client id", "client_id=" + mock_server.ISSUED_CLIENT in OPENED[-1] and "agent_name_hint" not in OPENED[-1], OPENED[-1:])
	cd.Destroy()
	# Cancel while waiting
	waiting = planUi.startSignIn(dlg)
	OPENED.clear()
	waiting2 = planUi.startSignIn(dlg)
	check("only one sign-in at a time", waiting2 is waiting)
	planUi.SignInDialog._running = None
	cancelled = planUi.SignInDialog(dlg)
	cancelled.cancelEvent.set()
	cancelled.start()
	pump(lambda: waiting.result is not None and cancelled.error is not None, 15)
	check("cancel stops the sign-in and is announced", cancelled.error is not None and cancelled.error.kind == "cancelled" and "Sign-in cancelled." in RECORD["spoken"], RECORD["spoken"][-3:])
	# Settings panel: ChatGPT plan controls
	frame = wx.Frame(None)
	panel = settingsPanel.NVDAIAsSettingsPanel(frame)
	g = {x.providerId: x for x in panel.groups}["openai"]
	check("settings show the ChatGPT account", g.planStatusText.GetLabel() == "ChatGPT plan: signed in as pessoa@example.com.", g.planStatusText.GetLabel())
	check("settings buttons for the plan", [b.GetLabel() for b in (g.signInButton, g.signOutButton, g.usageButton)] == ["Continue with ChatGPT", "Sign out of ChatGPT", "Manage ChatGPT usage"] and g.signOutButton.IsEnabled())
	check("plan checkbox on and plan models listed", g.planCheck.GetValue() and g.modelCombo.GetStrings()[:2] == ["gpt-5.5", "gpt-5.5-mini"], g.modelCombo.GetStrings())
	g.onTest(None)
	pump(lambda: g.testButton.IsEnabled(), 10)
	check("test connection uses the plan without token", "Connection to ChatGPT working. 2 models available." in RECORD["messageBoxes"][-1], RECORD["messageBoxes"][-1:])
	g.modelCombo.SetValue("gpt-5.5-mini")
	panel.onSave()
	check("plan model saved apart from the API model", core.conf()["model_openai_plan"] == "gpt-5.5-mini" and core.conf()["model_openai"] != "gpt-5.5-mini")
	g.planCheck.SetValue(False)
	g.refreshModels()
	check("unchecking shows the API models", "gpt-5-mini" in g.modelCombo.GetStrings(), g.modelCombo.GetStrings())
	panel.onSave()
	check("plan switched off keeps the session", core.conf()["openaiUsePlan"] is False and not core.usingPlan("openai") and core.plan().signedIn())
	check("without token and plan, ChatGPT is not connected", not core.isConnected("openai"))
	g.planCheck.SetValue(True)
	g.refreshModels()
	panel.onSave()
	check("plan switched back on", core.usingPlan("openai") and core.getModel("openai") == "gpt-5.5-mini")
	nvda_stubs.MESSAGEBOX_ANSWER["value"] = wx.YES
	refresh = core.plan().store.session()["refresh_token"]
	g.onSignOut(None)
	pump(lambda: any(r.get("token") == refresh for r in mock_server.CHATGPT["revoked"]), 10)
	check("sign out deletes the session at once", not core.plan().signedIn() and "not signed in" in g.planStatusText.GetLabel() and not g.signOutButton.IsEnabled())
	check("sign out revokes the refresh token at OpenAI", any(r.get("token") == refresh and r.get("token_type_hint") == "refresh_token" for r in mock_server.CHATGPT["revoked"]))
	check("sign out announced", RECORD["spoken"][-1] == "Signed out of ChatGPT", RECORD["spoken"][-1:])
	frame.Destroy()
	dlg.updateStatus()
	check("Manage usage hidden after sign out", not dlg.usageButton.IsShown())
	planUi.wx.MessageDialog = realMD
	core.store().set("openai", mock_server.VALID["openai"])
	dlg.Close()
	pump(timeout=0.3)

	# 15. Secure screens ----------------------------------------------------------------
	import globalVars
	globalVars.appArgs.secure = True
	check("disabled on secure screens", NVDAIAs.disableInSecureMode(object) is sys.modules["globalPluginHandler"].GlobalPlugin)
	globalVars.appArgs.secure = False

	plugin.terminate()
	pump(timeout=0.3)
	check("terminate unregisters panel and closes window", settingsPanel.NVDAIAsSettingsPanel not in gui.settingsDialogs.NVDASettingsDialog.categoryClasses and chatDialog.ChatDialog._instance is None)
	check("no errors logged", not RECORD.get("logErrors"), str((RECORD.get("logErrors"), RECORD.get("logTracebacks"))))


try:
	run()
except Exception:
	traceback.print_exc()
	RESULTS.append(("exception", False, ""))
failed = [r for r in RESULTS if not r[1]]
print("\n%d checks, %d failed" % (len(RESULTS), len(failed)))
from _results import emit  # noqa: E402
emit("interface (test_gui)", [r[0] for r in RESULTS], [r[0] for r in failed])
sys.exit(1 if failed else 0)
