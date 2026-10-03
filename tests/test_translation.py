# -*- coding: UTF-8 -*-
"""Loads the add-on with the Portuguese (Brazil) translation and builds every
window, checking that the translated strings are used and that the keyboard
shortcuts (&) of each window are unique.

Run (Linux): NVDAIAS_LANG=pt_BR xvfb-run -a python3 tests/test_translation.py
"""
import os
import re
import sys

os.environ.setdefault("NVDAIAS_LANG", "pt_BR")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "addon", "globalPlugins"))
import wx  # noqa: E402
import nvda_stubs  # noqa: E402

nvda_stubs.install()
app = wx.App(False)
import gui  # noqa: E402

gui.mainFrame = gui.MainFrame()
import NVDAIAs  # noqa: E402
from NVDAIAs import core, chatDialog, connectDialog, settingsPanel, providers  # noqa: E402

failures = []


def mnemonics(window):
	keys = []
	for c in window.GetChildren():
		label = c.GetLabel() if hasattr(c, "GetLabel") else ""
		m = re.search(r"&(\w)", label or "")
		if m:
			keys.append((m.group(1).lower(), label))
		if isinstance(c, wx.StaticBox) or (isinstance(c, wx.Panel) and not isinstance(c, wx.Dialog)):
			keys.extend(mnemonics(c))
	return keys


def checkUnique(name, window):
	keys = mnemonics(window)
	seen = {}
	for k, label in keys:
		if k in seen:
			failures.append("%s: duplicated shortcut %s in %r and %r" % (name, k, seen[k], label))
		seen[k] = label
	print("%s shortcuts: %s" % (name, " ".join(sorted(k for k, _l in keys))))


plugin = NVDAIAs.GlobalPlugin()
core.store().set("openai", "x")
dlg = chatDialog.ChatDialog.showInstance(plugin.session)
if dlg.GetTitle() != "NVDAIAs - Conversa com IA":
	failures.append("chat title not translated: %s" % dlg.GetTitle())
checkUnique("chat", dlg)
cd = connectDialog.ConnectDialog(dlg, "gemini")
if "aistudio.google.com" not in cd.instructionsText.GetValue() or "Pressione" not in cd.instructionsText.GetValue():
	failures.append("connect instructions not translated")
checkUnique("connect", cd)
cd.Destroy()
frame = wx.Frame(None)
panel = settingsPanel.NVDAIAsSettingsPanel(frame)
checkUnique("settings (top level)", panel)
for kind in ("auth", "quota", "network", "timeout", "model", "blocked", "server", "other"):
	msg = core.errorMessage(providers.ProviderError(kind, "detalhe"), "Claude")
	print(kind, "->", msg)
	if "{" in msg:
		failures.append("placeholder left in " + kind)
print("system prompt:", core.getSystemPrompt())
if not core.getSystemPrompt().startswith("Você é"):
	failures.append("default instructions not translated")
plugin.terminate()
frame.Destroy()
print("\nFAILURES:" if failures else "\nall translation checks passed")
for f in failures:
	print(" -", f)
CHECKS = {
	"pt_BR chat window title": "chat title",
	"pt_BR connection instructions": "connect instructions",
	"unique Alt shortcuts: chat": "chat: duplicated",
	"unique Alt shortcuts: connect": "connect: duplicated",
	"unique Alt shortcuts: settings": "settings (top level): duplicated",
	"pt_BR error messages without placeholders": "placeholder left",
	"pt_BR default instructions": "default instructions",
}
failedChecks = [name for name, key in CHECKS.items() if any(key in f for f in failures)]
from _results import emit  # noqa: E402
emit("translation (test_translation)", list(CHECKS), failedChecks)
sys.exit(1 if failures else 0)
