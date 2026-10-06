# -*- coding: UTF-8 -*-
"""Checks of the visual theme: contrast of every token pair (WCAG 2.2 AA),
high contrast fallback, theme on/off and that the tab order is unchanged.

Run (Linux): xvfb-run -a python3 tests/test_theme.py
"""
import os
import sys

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
from NVDAIAs import core, chatDialog, theme  # noqa: E402

results = []


def check(name, ok, info=""):
	results.append((name, bool(ok)))
	print(("PASS " if ok else "FAIL ") + name + ("" if ok else "  -> %s" % (info,)))


t = theme.tokens()
colors = t["color"]
for fg, bg in t["contrast"]["text"]:
	ratio = theme.contrastRatio(colors[fg], colors[bg])
	check("text contrast %s on %s = %.2f (>= 4.5)" % (fg, bg, ratio), ratio >= 4.5, ratio)
for fg, bg in t["contrast"].get("largeText", []):
	ratio = theme.contrastRatio(colors[fg], colors[bg])
	check("large bold text contrast %s on %s = %.2f (>= 3)" % (fg, bg, ratio), ratio >= 3.0, ratio)
check("every colour token is a valid hex colour", all(len(v) == 7 and v.startswith("#") and int(v[1:], 16) >= 0 for v in colors.values()))
check("radius tokens for cards, focus ring and chips", all(theme.radius(n) > 0 for n in ("card", "focus", "chip")))
check("font falls back to an installed font", theme.fontFace() in t["font"]["family"] and theme.fontFace("family.display") in t["font"]["family.display"], (theme.fontFace(), theme.fontFace("family.display")))
check("header title is large bold text (WCAG large text)", t["font"]["size.title"] >= 14)
for fg, bg in t["contrast"]["nonText"]:
	ratio = theme.contrastRatio(colors[fg], colors[bg])
	check("non-text contrast %s on %s = %.2f (>= 3)" % (fg, bg, ratio), ratio >= 3.0, ratio)
check("contrast formula (black/white = 21)", abs(theme.contrastRatio("#000000", "#FFFFFF") - 21) < 0.01)

plugin = NVDAIAs.GlobalPlugin()
check("theme on by default", theme.isEnabled())


def focusOrder(dlg):
	return [c for c in dlg.GetChildren() if c.IsShown() and c.AcceptsFocusFromKeyboard() and not isinstance(c, wx.StaticText)]


dlg = chatDialog.ChatDialog.showInstance(plugin.session)
order = focusOrder(dlg)
expected = [dlg.providerChoice, dlg.modelCombo, dlg.conversationTree, dlg.questionEdit, dlg.attachButton, dlg.sendButton, dlg.cancelButton, dlg.readButton, dlg.copyButton, dlg.actionsButton, dlg.newButton, dlg.saveButton, dlg.connectButton, dlg.settingsButton, dlg.feedbackButton, dlg.closeButton]
check("tab order with theme", order == expected, [type(c).__name__ for c in order])
check("header present and not focusable", hasattr(dlg, "header") and not dlg.header.AcceptsFocusFromKeyboard())
check("page colour applied", dlg.GetBackgroundColour() == theme.color("surface.page"))
check("buttons keep native colours", dlg.sendButton.GetBackgroundColour() != theme.color("surface.page") or sys.platform != "win32")
check("status line has text", "not connected" in dlg.statusLine.GetLabel(), dlg.statusLine.GetLabel())
core.store().set("openai", "x")
dlg.updateStatus()
check("status line connected", dlg.statusLine.GetLabel() == "ChatGPT · gpt-5-mini · connected", dlg.statusLine.GetLabel())
check("status colour ok", dlg.statusLine.GetForegroundColour() == theme.color("status.ok"))
check("status shown as a chip (tinted background)", dlg.statusLine.GetBackgroundColour() == theme.color("status.okBg") and dlg.statusLine in dlg.focusFrames.chips)
dlg.updateStatus(errorText="x")
check("error chip colours", dlg.statusLine.GetForegroundColour() == theme.color("status.error") and dlg.statusLine.GetBackgroundColour() == theme.color("status.errorBg"))
dlg.updateStatus()
cards = dlg.focusFrames.cards
check("three cards: AI and model, conversation, question", len(cards) == 3 and dlg.conversationTree in cards[1].windows and dlg.questionEdit in cards[2].windows)
check("conversation and question cards have a title with the accent bar", cards[1].title is not None and cards[2].title is not None and cards[0].title is None)
for _i in range(10):
	wx.Yield()
rects = [dlg.focusFrames.cardRect(c) for c in cards]
inside = all(any(r is not None and r.Contains(ctrl.GetRect()) for r in rects) for ctrl in dlg.focusFrames.controls if ctrl.IsShown())
check("every control with the focus ring sits on a white card (ring contrast 3:1)", inside, [(type(c).__name__, c.GetRect()) for c in dlg.focusFrames.controls])
overlap = any(rects[i].Intersects(rects[i + 1]) for i in range(len(rects) - 1) if rects[i] and rects[i + 1])
check("cards do not overlap", not overlap, rects)
labelsOnCards = [w for c in cards for w in c.windows if isinstance(w, wx.StaticText)]
check("labels on cards use the card colour", all(w.GetBackgroundColour() == theme.color("surface.card") for w in labelsOnCards))
check("header title on the orange bar, subtitle on the page", dlg.header.bar.GetBackgroundColour() == theme.color("surface.header") and dlg.header.subtitleText.GetForegroundColour() == theme.color("text.secondary"))
from NVDAIAs import connectDialog  # noqa: E402
cd = connectDialog.ConnectDialog(dlg, "openai")
check("connect dialog uses two cards", len(cd.focusFrames.cards) == 2 and cd.chatgptButton in cd.focusFrames.cards[0].windows)
check("connect dialog tab order unchanged", focusOrder(cd)[:5] == [cd.providerChoice, cd.chatgptButton, cd.instructionsText, cd.openPageButton, cd.tokenEdit], [type(c).__name__ for c in focusOrder(cd)])
cd.Destroy()
dlg.Close()

core.conf()["visualTheme"] = False
dlg = chatDialog.ChatDialog.showInstance(plugin.session)
check("theme off: no header", not hasattr(dlg, "header"))
check("theme off: same tab order", focusOrder(dlg) == [dlg.providerChoice, dlg.modelCombo, dlg.conversationTree, dlg.questionEdit, dlg.attachButton, dlg.sendButton, dlg.cancelButton, dlg.readButton, dlg.copyButton, dlg.actionsButton, dlg.newButton, dlg.saveButton, dlg.connectButton, dlg.settingsButton, dlg.feedbackButton, dlg.closeButton])
check("theme off: status line still informs", "connected" in dlg.statusLine.GetLabel())
dlg.Close()
core.conf()["visualTheme"] = True

original = theme.isHighContrast
theme.isHighContrast = lambda: True
check("high contrast turns the theme off", not theme.isEnabled())
theme.isHighContrast = original

core.conf()["largeText"] = True
check("larger text scale", theme.fontScale() == 1.25 and theme.font("size.body", scale=theme.fontScale()).GetPointSize() == 14)
plugin.terminate()
failedNames = [n for n, ok in results if not ok]
print("\n%d checks, %d failed" % (len(results), len(failedNames)))
from _results import emit  # noqa: E402
emit("visual theme (test_theme)", [n for n, ok in results], failedNames)
sys.exit(1 if failedNames else 0)
