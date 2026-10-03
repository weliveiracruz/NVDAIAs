# -*- coding: UTF-8 -*-
"""Renders the NVDAIAs windows and saves PNG previews in docs/design/.

Run (Linux): NVDAIAS_LANG=pt_BR xvfb-run -a -s "-screen 0 1400x1000x24" python3 tests/screenshots.py
The look of native widgets (buttons, combo boxes) follows the Linux GTK theme;
on Windows they look like normal Windows controls. Colours, header, fonts and
focus frame are the same.
"""
import os
import sys
import time

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
from NVDAIAs import core, chatDialog, connectDialog  # noqa: E402

OUT = os.path.join(HERE, "..", "docs", "design")
os.makedirs(OUT, exist_ok=True)


def pump(t=0.6):
	end = time.time() + t
	while time.time() < end:
		wx.Yield()
		time.sleep(0.02)


def shot(win, name):
	"""Captures the window with ImageMagick (reads the real X server pixels)."""
	import subprocess
	win.Raise()
	win.Refresh()
	win.Update()
	pump(0.8)
	x, y = win.GetScreenPosition()
	w, h = win.GetSize()
	path = os.path.join(OUT, name)
	subprocess.run(["import", "-window", "root", "-crop", "%dx%d+%d+%d" % (w, h, x, y), "+repage", path], check=True)
	print("saved", os.path.relpath(path, os.path.join(HERE, "..")))


plugin = NVDAIAs.GlobalPlugin()
core.store().set("anthropic", "sk-ant-demo-123456")
core.conf()["provider"] = "anthropic"
from NVDAIAs.conversation import Conversation  # noqa: E402

core.history().deleteAll()
for question, answer, ai, model, ts in (
	("Como faço um bolo de cenoura?", "Bata no liquidificador 3 cenouras, 3 ovos e 1 xícara de óleo...", "ChatGPT", "gpt-5-mini", 1790950000),
	("Resuma a reunião de ontem sobre o orçamento", "Principais pontos: corte de 10% em viagens...", "Gemini", "gemini-2.5-flash", 1791030000),
):
	old = Conversation()
	old.add(core.ChatEntry("user", question, timestamp=ts))
	old.add(core.ChatEntry("assistant", answer, providerName=ai, model=model, timestamp=ts + 30))
	core.history().save(old.toDict())
conv = plugin.session.conversation
conv.add(core.ChatEntry("user", "Qual é a capital do Brasil?"))
conv.add(core.ChatEntry("assistant", "A capital do Brasil é **Brasília**, inaugurada em 1960 e planejada por Lúcio Costa e Oscar Niemeyer.", providerName="Claude", model="claude-sonnet-5-5"))
conv.add(core.ChatEntry("user", "E quantos habitantes ela tem?"))
conv.add(core.ChatEntry("assistant", "Segundo o Censo de 2022 do IBGE, Brasília tem cerca de 2,8 milhões de habitantes.", providerName="Claude", model="claude-sonnet-5-5"))

dlg = chatDialog.ChatDialog.showInstance(plugin.session)
dlg.SetPosition((40, 40))
dlg.questionEdit.SetValue("Quais são os principais pontos turísticos?")
dlg.questionEdit.SetFocus()
shot(dlg, "chat-foco-pergunta.png")

dlg.conversationTree.SetFocus()
shot(dlg, "chat-foco-lista.png")

tree = dlg.conversationTree
tree.Expand(dlg._historyNode)
first = tree.GetFirstChild(dlg._historyNode)[0]
tree.Expand(first)
tree.SelectItem(tree.GetFirstChild(first)[0])
tree.SetFocus()
shot(dlg, "chat-historico.png")
tree.Collapse(dlg._historyNode)
tree.SelectItem(dlg._historyNode)

plugin.session.busy = True
dlg.refreshList()
shot(dlg, "chat-aguardando.png")
plugin.session.busy = False
dlg.refreshList()
dlg.updateStatus(errorText="x")
shot(dlg, "chat-erro.png")
dlg.Close()
pump()

cd = connectDialog.ConnectDialog(gui.mainFrame, "gemini")
cd.SetPosition((40, 40))
cd.Show()
cd.tokenEdit.SetFocus()
shot(cd, "conectar-conta.png")
cd.Destroy()

core.conf()["visualTheme"] = False
dlg = chatDialog.ChatDialog.showInstance(plugin.session)
dlg.SetPosition((40, 40))
shot(dlg, "chat-sem-tema.png")
dlg.Close()
plugin.terminate()
