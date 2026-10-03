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
from NVDAIAs import core, providers, chatDialog, connectDialog, settingsPanel  # noqa: E402

for cls, path in ((providers.OpenAIProvider, "/openai/v1"), (providers.GeminiProvider, "/gemini/v1beta"), (providers.AnthropicProvider, "/anthropic/v1")):
	cls.defaultBaseUrl = BASE + path

RESULTS = []


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
	check("question is right after conversation list in tab order", focusable[qi - 1] is dlg.conversationList, names)
	check("tab order starts with AI, Model, Conversation", focusable[:3] == [dlg.providerChoice, dlg.modelCombo, dlg.conversationList], names)
	dlg.questionEdit.SetFocus()
	pump(timeout=0.3)
	dlg.questionEdit.Navigate(wx.NavigationKeyEvent.IsBackward)
	pump(timeout=0.3)
	focused = wx.Window.FindFocus()
	check("Shift+Tab from question focuses the conversation list (real navigation)", focused is dlg.conversationList, focused)

	# 3. Ask a question with Enter -------------------------------------------------------
	RECORD["spoken"].clear()
	dlg.questionEdit.SetValue("Qual é a capital do Brasil?")
	dlg.questionEdit.SetFocus()
	pump(timeout=0.2)
	dlg.onCharHook(keyDown(dlg.questionEdit, wx.WXK_RETURN))
	check("Enter sends", core.ChatSession and plugin.session.busy and dlg.questionEdit.GetValue() == "")
	check("waiting item shown", dlg.conversationList.GetString(dlg.conversationList.GetCount() - 1) == "Claude is answering…")
	check("send button disabled while waiting", not dlg.sendButton.IsEnabled() and dlg.cancelButton.IsEnabled())
	pump(lambda: not plugin.session.busy, 10)
	items = dlg.conversationList.GetStrings()
	check("conversation list has question and answer", items[0] == "You: Qual é a capital do Brasil?" and items[1].startswith("Claude: Claude responde: Qual é a capital do Brasil?"), items)
	check("answer spoken automatically", any("Claude responde" in s for s in RECORD["spoken"]), RECORD["spoken"])
	check("'Sent to Claude' announced", "Sent to Claude" in RECORD["spoken"], RECORD["spoken"])
	check("last item selected", dlg.conversationList.GetSelection() == 1)

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
	check("real Shift+Tab goes to the conversation list", wx.Window.FindFocus() is dlg.conversationList, wx.Window.FindFocus())
	n = len(RECORD["browseable"])
	sim.Char(wx.WXK_RETURN)
	pump(lambda: len(RECORD["browseable"]) > n, 2)
	check("real Enter on the list opens the reading window", len(RECORD["browseable"]) > n)
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
	last = dlg.conversationList.GetString(dlg.conversationList.GetCount() - 1)
	check("ChatGPT answer in list, Markdown removed", last.startswith("ChatGPT: Resposta Olá!") and "#" not in last and "*" not in last, last)
	check("ChatGPT received whole conversation", "5 mensagens" in plugin.session.conversation.lastAnswer().text, plugin.session.conversation.lastAnswer().text)

	# 6. Read message (Enter on the list) and copy (Ctrl+C) -----------------------------------
	dlg.conversationList.SetSelection(dlg.conversationList.GetCount() - 1)
	dlg.onListKeyDown(keyDown(dlg.conversationList, wx.WXK_RETURN))
	html, title, isHtml = RECORD["browseable"][-1]
	check("Enter opens the answer in a reading window", isHtml and "<h1>Resposta</h1>" in html and title.startswith("Answer from ChatGPT"), (title, html))
	dlg.onListKeyDown(keyDown(dlg.conversationList, ord("C"), ctrl=True))
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
	check("list shows [image attached]", "[image attached]" in dlg.conversationList.GetString(dlg.conversationList.GetCount() - 2))
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
	check("new conversation clears list", dlg.conversationList.GetCount() == 0 and not dlg.saveButton.IsEnabled())
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
	check("conversation kept after reopening", dlg.conversationList.GetStrings() == ["You: persistente"])
	check("escape id is Close", dlg.GetEscapeId() == wx.ID_CLOSE)
	dlg.Raise()
	dlg.questionEdit.SetFocus()
	pump(timeout=0.5)
	sim.Char(wx.WXK_ESCAPE)
	pump(lambda: chatDialog.ChatDialog._instance is None, 2)
	check("real Escape closes the window", chatDialog.ChatDialog._instance is None)
	plugin.script_openChat(None)
	pump(lambda: chatDialog.ChatDialog._instance is not None, 3)

	# 15. Secure screens ----------------------------------------------------------------
	import globalVars
	globalVars.appArgs.secure = True
	check("disabled on secure screens", NVDAIAs.disableInSecureMode(object) is sys.modules["globalPluginHandler"].GlobalPlugin)
	globalVars.appArgs.secure = False

	plugin.terminate()
	pump(timeout=0.3)
	check("terminate unregisters panel and closes window", settingsPanel.NVDAIAsSettingsPanel not in gui.settingsDialogs.NVDASettingsDialog.categoryClasses and chatDialog.ChatDialog._instance is None)
	check("no errors logged", not RECORD.get("logErrors"), RECORD.get("logErrors"))


try:
	run()
except Exception:
	traceback.print_exc()
	RESULTS.append(("exception", False, ""))
failed = [r for r in RESULTS if not r[1]]
print("\n%d checks, %d failed" % (len(RESULTS), len(failed)))
sys.exit(1 if failed else 0)
