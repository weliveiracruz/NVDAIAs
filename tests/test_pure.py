# -*- coding: UTF-8 -*-
"""Tests of the parts of NVDAIAs that do not need NVDA or wxPython:
API clients (against a local imitation of the three APIs), text conversion,
credential storage and the conversation model.

Run: python -m unittest tests/test_pure.py
"""

import base64
import json
import os
import sys
import tempfile
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PKG_DIR = os.path.join(HERE, "..", "addon", "globalPlugins", "NVDAIAs")
sys.path.insert(0, HERE)

# Load the add-on sub modules without running the package __init__ (which needs NVDA).
pkg = types.ModuleType("NVDAIAs")
pkg.__path__ = [PKG_DIR]
sys.modules["NVDAIAs"] = pkg

from NVDAIAs import providers, textutils, credentials, conversation, history, attachments, chatgptPlan  # noqa: E402
import mock_server  # noqa: E402

SERVER, BASE = mock_server.start()
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==")


def make(providerId, token=None, model=None, **kw):
	cls = providers.getProviderClass(providerId)
	base = {"openai": "/openai/v1", "gemini": "/gemini/v1beta", "anthropic": "/anthropic/v1"}[providerId]
	return cls(mock_server.VALID[providerId] if token is None else token, model=model, baseUrl=BASE + base, timeout=5, **kw)


class ProviderTests(unittest.TestCase):
	def setUp(self):
		mock_server.REQUESTS.clear()
		mock_server.FORCE.clear()

	def test_all_providers_answer(self):
		for pid in providers.PROVIDER_IDS:
			with self.subTest(pid):
				p = make(pid)
				answer = p.chat([providers.Message("user", "Qual é a capital do Brasil?")], "Seja breve.")
				self.assertIn("Qual é a capital do Brasil?", answer)

	def test_multi_turn_history_is_sent(self):
		for pid in providers.PROVIDER_IDS:
			with self.subTest(pid):
				msgs = [
					providers.Message("user", "Oi"),
					providers.Message("assistant", "Olá!"),
					providers.Message("user", "Tudo bem?"),
				]
				answer = make(pid).chat(msgs, "sys")
				self.assertIn("3 mensagens", answer)

	def test_images(self):
		for pid in providers.PROVIDER_IDS:
			with self.subTest(pid):
				answer = make(pid).chat([providers.Message("user", "Descreva", image=PNG)], "sys")
				self.assertTrue(answer)

	def test_gemini_skips_thoughts(self):
		answer = make("gemini").chat([providers.Message("user", "x")], "sys")
		self.assertNotIn("pensando", answer)

	def test_headers(self):
		make("anthropic").chat([providers.Message("user", "x")], "sys")
		h = {k.lower(): v for k, v in mock_server.REQUESTS[-1]["headers"].items()}
		self.assertEqual(h["anthropic-version"], "2023-06-01")
		self.assertEqual(h["content-type"], "application/json")
		self.assertTrue(h["user-agent"].startswith("NVDAIAs"))

	def test_invalid_token_is_auth_error(self):
		for pid in providers.PROVIDER_IDS:
			with self.subTest(pid):
				with self.assertRaises(providers.ProviderError) as cm:
					make(pid, token="wrong").chat([providers.Message("user", "x")], "sys")
				self.assertEqual(cm.exception.kind, "auth")
				with self.assertRaises(providers.ProviderError) as cm:
					make(pid, token="wrong").testConnection()
				self.assertEqual(cm.exception.kind, "auth")

	def test_missing_token(self):
		with self.assertRaises(providers.ProviderError) as cm:
			make("openai", token="").chat([providers.Message("user", "x")])
		self.assertEqual(cm.exception.kind, "auth")
		self.assertEqual(mock_server.REQUESTS, [])

	def test_quota_and_server_errors(self):
		mock_server.FORCE["openai"] = (429, {"error": {"message": "You exceeded your current quota", "type": "insufficient_quota"}})
		with self.assertRaises(providers.ProviderError) as cm:
			make("openai").chat([providers.Message("user", "x")])
		self.assertEqual(cm.exception.kind, "quota")
		mock_server.FORCE["anthropic"] = (529, {"type": "error", "error": {"type": "overloaded_error", "message": "Overloaded"}})
		with self.assertRaises(providers.ProviderError) as cm:
			make("anthropic").chat([providers.Message("user", "x")])
		self.assertEqual(cm.exception.kind, "server")
		mock_server.FORCE["gemini"] = (500, "not json")
		with self.assertRaises(providers.ProviderError) as cm:
			make("gemini").chat([providers.Message("user", "x")])
		self.assertEqual(cm.exception.kind, "server")

	def test_unknown_model(self):
		with self.assertRaises(providers.ProviderError) as cm:
			make("gemini", model="gemini-que-nao-existe").chat([providers.Message("user", "x")], "sys")
		self.assertEqual(cm.exception.kind, "model")

	def test_blocked_answers(self):
		mock_server.FORCE["gemini"] = (200, {"promptFeedback": {"blockReason": "SAFETY"}})
		with self.assertRaises(providers.ProviderError) as cm:
			make("gemini").chat([providers.Message("user", "x")])
		self.assertEqual(cm.exception.kind, "blocked")
		mock_server.FORCE["openai"] = (200, {"choices": [{"message": {"role": "assistant", "content": None, "refusal": "Não posso ajudar."}, "finish_reason": "stop"}]})
		with self.assertRaises(providers.ProviderError) as cm:
			make("openai").chat([providers.Message("user", "x")])
		self.assertEqual(cm.exception.kind, "blocked")

	def test_network_error(self):
		p = providers.OpenAIProvider("k", baseUrl="http://127.0.0.1:9/v1", timeout=3)
		with self.assertRaises(providers.ProviderError) as cm:
			p.chat([providers.Message("user", "x")])
		self.assertEqual(cm.exception.kind, "network")

	def test_timeout(self):
		mock_server.DELAY["seconds"] = 2
		try:
			p = make("openai")
			p.timeout = 0.5
			with self.assertRaises(providers.ProviderError) as cm:
				p.chat([providers.Message("user", "x")])
			self.assertEqual(cm.exception.kind, "timeout")
		finally:
			mock_server.DELAY["seconds"] = 0

	def test_list_models(self):
		self.assertEqual(make("openai").listModels(), ["gpt-4o-realtime-preview", "gpt-5", "gpt-5-mini"][1:])
		self.assertEqual(make("gemini").listModels(), ["gemini-2.5-flash", "gemini-2.5-pro"])
		self.assertEqual(make("anthropic").listModels(), ["claude-haiku-4-5-20251001", "claude-sonnet-5-5"])

	def test_test_connection_reports_missing_model(self):
		models, found = make("openai", model="gpt-inexistente").testConnection()
		self.assertFalse(found)
		models, found = make("openai").testConnection()
		self.assertTrue(found)

	def test_anthropic_merges_consecutive_roles(self):
		body = make("anthropic").buildBody([providers.Message("user", "a"), providers.Message("user", "b")], "")
		self.assertEqual(len(body["messages"]), 1)
		self.assertNotIn("system", body)

	def test_default_models_are_suggested(self):
		for cls in providers.PROVIDERS:
			self.assertIn(cls.defaultModel, cls.suggestedModels)
			self.assertTrue(cls.tokenUrl.startswith("https://"))
			self.assertTrue(cls.defaultBaseUrl.startswith("https://"))

	def test_ssl_context(self):
		ctx = providers._getSslContext()
		import ssl
		self.assertEqual(ctx.verify_mode, ssl.CERT_REQUIRED)
		self.assertTrue(ctx.check_hostname)


class TextTests(unittest.TestCase):
	MD = "# Título\n\nTexto com **negrito**, *itálico* e `código`.\n\n- item 1\n- item 2\n  - sub\n\n1. um\n2. dois\n\n| A | B |\n|---|---|\n| 1 | 2 |\n\n```python\nprint('<oi>')\n```\n\n> citação\n\nVeja [site](https://exemplo.com) e [x](javascript:alert(1)).\n<script>alert(1)</script>"

	def test_plain(self):
		t = textutils.toPlainText(self.MD)
		for sym in ("#", "**", "`", "|", "---"):
			self.assertNotIn(sym, t)
		self.assertIn("negrito", t)
		self.assertIn("A, B", t)
		self.assertIn("print('<oi>')", t)
		self.assertIn("site (https://exemplo.com)", t)

	def test_html(self):
		h = textutils.toHtml(self.MD)
		self.assertIn("<h1>Título</h1>", h)
		self.assertIn("<strong>negrito</strong>", h)
		self.assertIn("<em>itálico</em>", h)
		self.assertIn("<code>código</code>", h)
		self.assertIn("<ul>", h)
		self.assertIn("<ol>", h)
		self.assertIn("<th>A</th>", h)
		self.assertIn("&lt;oi&gt;", h)
		self.assertIn('<a href="https://exemplo.com">site</a>', h)
		self.assertNotIn('href="javascript', h)
		self.assertNotIn("<script>", h)
		self.assertIn("<blockquote>", h)
		self.assertEqual(h.count("<ul>"), h.count("</ul>"))
		self.assertEqual(h.count("<ol>"), h.count("</ol>"))

	def test_snake_case_not_italic(self):
		self.assertEqual(textutils.toPlainText("use nome_de_variavel_aqui"), "use nome_de_variavel_aqui")
		self.assertEqual(textutils.toPlainText("2 * 3 * 4"), "2 * 3 * 4")

	def test_one_line(self):
		self.assertEqual(textutils.oneLine("a\n\nb   c"), "a b c")
		self.assertEqual(len(textutils.oneLine("x" * 100, 10)), 10)


class CredentialTests(unittest.TestCase):
	def test_roundtrip_and_file_has_no_plain_token(self):
		class FakeDPAPI:
			def protect(self, data):
				return bytes(b ^ 0x5A for b in data)

			def unprotect(self, data):
				return bytes(b ^ 0x5A for b in data)

		folder = tempfile.mkdtemp()
		store = credentials.CredentialStore(folder, codec=FakeDPAPI())
		store.set("openai", "  sk-segredo-1234  ")
		self.assertEqual(store.get("openai"), "sk-segredo-1234")
		with open(store.path, encoding="utf-8") as f:
			raw = f.read()
		self.assertNotIn("sk-segredo", raw)
		# new instance reads from disk
		store2 = credentials.CredentialStore(folder, codec=FakeDPAPI())
		self.assertTrue(store2.has("openai"))
		self.assertFalse(store2.has("gemini"))
		store2.remove("openai")
		self.assertFalse(credentials.CredentialStore(folder, codec=FakeDPAPI()).has("openai"))

	def test_damaged_file(self):
		folder = tempfile.mkdtemp()
		with open(os.path.join(folder, credentials.FILE_NAME), "w") as f:
			f.write("{not json")
		store = credentials.CredentialStore(folder, codec=credentials._PlainCodec())
		self.assertEqual(store.get("openai"), "")
		store.set("gemini", "abc")
		with open(store.path) as f:
			self.assertEqual(json.load(f)["gemini"], base64.b64encode(b"abc").decode())

	def test_mask(self):
		self.assertEqual(credentials.maskToken("sk-1234567890abcd"), "…abcd")
		self.assertEqual(credentials.maskToken("short"), "…")


class ConversationTests(unittest.TestCase):
	def test_model(self):
		c = conversation.Conversation()
		calls = []
		c.listeners.append(lambda: calls.append(1))
		u = c.add(conversation.ChatEntry("user", "Oi", image=PNG))
		c.add(conversation.ChatEntry("assistant", "Olá", providerName="Claude", model="claude-sonnet-5-5"))
		self.assertEqual(len(calls), 2)
		msgs = c.apiMessages()
		self.assertEqual([m.role for m in msgs], ["user", "assistant"])
		self.assertEqual(msgs[0].attachments[0].data, PNG)
		self.assertEqual(c.lastAnswer().text, "Olá")
		text = c.toText("Você", "[imagem]")
		self.assertIn("Você:\n[imagem]\nOi", text)
		self.assertIn("Claude (claude-sonnet-5-5):\nOlá", text)
		c.remove(u)
		self.assertEqual(len(c), 1)
		c.clear()
		self.assertEqual(len(c), 0)


class XorCodec:
	def protect(self, data):
		return bytes(b ^ 0x5A for b in data)

	def unprotect(self, data):
		return bytes(b ^ 0x5A for b in data)


class HistoryTests(unittest.TestCase):
	def make(self, n=2, question="Pergunta secreta"):
		c = conversation.Conversation()
		c.add(conversation.ChatEntry("user", question, image=PNG if n > 2 else None))
		c.add(conversation.ChatEntry("assistant", "Resposta", providerName="Gemini", model="gemini-2.5-flash"))
		return c

	def test_save_list_load_encrypted(self):
		folder = tempfile.mkdtemp()
		store = history.HistoryStore(folder, codec=XorCodec())
		c = self.make(3)
		self.assertTrue(store.save(c.toDict()))
		files = os.listdir(store.folder)
		self.assertEqual(files, [c.id + history.EXTENSION])
		with open(os.path.join(store.folder, files[0]), "rb") as f:
			raw = f.read()
		self.assertNotIn(b"Pergunta", raw)
		self.assertNotIn(base64.b64encode(b"Pergunta"), raw)
		store2 = history.HistoryStore(folder, codec=XorCodec())
		data = store2.load(c.id)
		c2 = conversation.Conversation()
		c2.load(data)
		self.assertEqual(c2.id, c.id)
		self.assertEqual([e.text for e in c2.entries], ["Pergunta secreta", "Resposta"])
		self.assertEqual(c2.entries[0].image, PNG)
		self.assertEqual(c2.entries[1].model, "gemini-2.5-flash")
		self.assertEqual(store2.list(excludeId=c.id), [])
		title, providers_, count, updated = history.summary(data)
		self.assertEqual((title, providers_, count), ("Pergunta secreta", ["Gemini"], 2))

	def test_empty_not_saved_and_order_and_prune(self):
		folder = tempfile.mkdtemp()
		store = history.HistoryStore(folder, codec=XorCodec(), maxConversations=3)
		self.assertFalse(store.save(conversation.Conversation().toDict()))
		ids = []
		for i in range(5):
			c = self.make(question="q%d" % i)
			for e in c.entries:
				e.timestamp = 1000 + i
			store.save(c.toDict())
			ids.append(c.id)
		listed = [d["id"] for d in store.list()]
		self.assertEqual(listed, list(reversed(ids))[:3])
		store.delete(ids[4])
		self.assertEqual(len(store.list()), 2)
		store.deleteAll()
		self.assertEqual(store.list(), [])

	def test_damaged_or_foreign_file_is_ignored(self):
		folder = tempfile.mkdtemp()
		store = history.HistoryStore(folder, codec=XorCodec())
		store.save(self.make().toDict())
		with open(os.path.join(store.folder, "lixo" + history.EXTENSION), "wb") as f:
			f.write(b"nao e base64 @@@")
		self.assertEqual(len(store.list()), 1)

	def test_invalid_id_rejected(self):
		store = history.HistoryStore(tempfile.mkdtemp(), codec=XorCodec())
		data = self.make().toDict()
		data["id"] = "../../fora"
		with self.assertRaises(ValueError):
			store.save(data)

	def test_clear_gives_new_id(self):
		c = self.make()
		old = c.id
		c.clear()
		self.assertNotEqual(c.id, old)
		self.assertEqual(len(c), 0)


def _zip(files):
	import io
	import zipfile
	buf = io.BytesIO()
	with zipfile.ZipFile(buf, "w") as z:
		for name, content in files.items():
			z.writestr(name, content)
	return buf.getvalue()


W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
DOCX = _zip({
	"[Content_Types].xml": "<Types/>",
	"word/document.xml": '<w:document %s><w:body><w:p><w:r><w:t>Relatório anual</w:t></w:r></w:p><w:p><w:r><w:t>Receita</w:t></w:r><w:r><w:tab/><w:t>100</w:t></w:r></w:p></w:body></w:document>' % W,
})
S = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
XLSX = _zip({
	"xl/workbook.xml": '<workbook %s><sheets><sheet name="Vendas" sheetId="1" r:id="rId1"/></sheets></workbook>' % S,
	"xl/_rels/workbook.xml.rels": '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>',
	"xl/sharedStrings.xml": '<sst %s><si><t>Produto</t></si><si><t>Total</t></si><si><t>Café</t></si></sst>' % S,
	"xl/worksheets/sheet1.xml": '<worksheet %s><sheetData><row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c></row><row r="2"><c r="A2" t="s"><v>2</v></c><c r="C2"><v>42.5</v></c></row></sheetData></worksheet>' % S,
})
A = 'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"'
PPTX = _zip({
	"ppt/presentation.xml": "<p:presentation %s/>" % A,
	"ppt/slides/slide2.xml": "<p:sld %s><a:p><a:r><a:t>Segundo slide</a:t></a:r></a:p></p:sld>" % A,
	"ppt/slides/slide1.xml": "<p:sld %s><a:p><a:r><a:t>Título do deck</a:t></a:r></a:p></p:sld>" % A,
	"ppt/notesSlides/notesSlide1.xml": "<p:notes %s><a:p><a:r><a:t>Falar devagar</a:t></a:r></a:p></p:notes>" % A,
})
ODT = _zip({
	"mimetype": "application/vnd.oasis.opendocument.text",
	"content.xml": '<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"><office:body><office:text><text:h>Capítulo 1</text:h><text:p>Era uma vez</text:p></office:text></office:body></office:document-content>',
})
EPUB = _zip({
	"META-INF/container.xml": "<container/>",
	"OEBPS/cap1.xhtml": "<html><body><h1>Capítulo</h1><p>Texto do livro</p><script>x()</script></body></html>",
})


class AttachmentTests(unittest.TestCase):
	def load(self, name, data, **kw):
		return attachments.fromBytes(name, data, **kw)

	def test_images_pdf_media(self):
		a = self.load("foto.PNG", PNG)
		self.assertEqual((a.kind, a.mime), ("image", "image/png"))
		jpg = self.load("x.jpg", b"\xff\xd8\xff\xe0" + b"0" * 20)
		self.assertEqual(jpg.mime, "image/jpeg")
		bmp = self.load("scan.bmp", b"BM" + b"0" * 50, convertImage=lambda d: PNG)
		self.assertEqual((bmp.kind, bmp.mime, bmp.name), ("image", "image/png", "scan.png"))
		with self.assertRaises(attachments.AttachmentError):
			self.load("scan.tiff", b"II*\x00garbage", convertImage=lambda d: None)
		pdf = self.load("contrato.pdf", b"%PDF-1.7 ...")
		self.assertEqual(pdf.kind, "pdf")
		self.assertTrue(pdf.dataUrl().startswith("data:application/pdf;base64,"))
		for name, mime in (("audio.mp3", "audio/mp3"), ("reuniao.m4a", "audio/aac"), ("video.mp4", "video/mp4"), ("aula.mkv", "video/webm")):
			m = self.load(name, b"\x00\x01binary")
			self.assertEqual((m.kind, m.mime), ("media", mime))

	def test_text_files(self):
		t = self.load("notas.txt", "Olá, mundo".encode("utf-8"))
		self.assertEqual((t.kind, t.text), ("text", "Olá, mundo"))
		t = self.load("antigo.txt", "Ação".encode("cp1252"))
		self.assertEqual(t.text, "Ação")
		t = self.load("dados.csv", b"a;b\n1;2\n")
		self.assertEqual(t.text, "a;b\n1;2")
		t = self.load("codigo.py", b"print('oi')\n")
		self.assertIn("print", t.text)
		t = self.load("unicode.txt", "Olá".encode("utf-16"))
		self.assertEqual(t.text, "Olá")
		t = self.load("pagina.html", b"<html><head><style>p{}</style></head><body><h1>Oi</h1><p>Mundo &amp; mais</p><script>alert(1)</script></body></html>")
		self.assertEqual(t.text, "Oi\n\nMundo & mais")
		t = self.load("doc.rtf", b"{\\rtf1\\ansi{\\fonttbl{\\f0 Arial;}}\\f0 Ol\\'e1 mundo\\par Segunda linha}")
		self.assertIn("Olá mundo", t.text)
		self.assertIn("Segunda linha", t.text)
		self.assertIn("<file name=\"doc.rtf\">", t.asPromptText())

	def test_office_documents(self):
		self.assertEqual(self.load("rel.docx", DOCX).text, "Relatório anual\nReceita\t100")
		x = self.load("vendas.xlsx", XLSX).text
		self.assertIn("# Vendas", x)
		self.assertIn("Produto\tTotal", x)
		self.assertIn("Café\t\t42.5", x)
		pptx = self.load("deck.pptx", PPTX).text
		self.assertLess(pptx.index("Título do deck"), pptx.index("Segundo slide"))
		self.assertIn("(notes) Falar devagar", pptx)
		self.assertEqual(self.load("livro.odt", ODT).text, "Capítulo 1\nEra uma vez")
		e = self.load("livro.epub", EPUB).text
		self.assertIn("Texto do livro", e)
		self.assertNotIn("x()", e)

	def test_refused_files(self):
		cases = {
			"velho.doc": (b"\xd0\xcf\x11\xe0" + b"\x00" * 50, "legacyOffice"),
			"programa.exe": (b"MZ\x90\x00\x03\x00\x00\x00" * 10, "binary"),
			"pacote.zip": (_zip({"a.bin": b"\x00\x01"}), "binary"),
			"vazio.txt": (b"   \n", "empty"),
		}
		for name, (data, reason) in cases.items():
			with self.subTest(name):
				with self.assertRaises(attachments.AttachmentError) as cm:
					self.load(name, data)
				self.assertEqual(cm.exception.reason, reason)

	def test_load_from_disk_limits(self):
		folder = tempfile.mkdtemp()
		path = os.path.join(folder, "grande.txt")
		with open(path, "wb") as f:
			f.write(b"a" * 100)
		old = attachments.MAX_FILE_BYTES
		attachments.MAX_FILE_BYTES = 50
		try:
			with self.assertRaises(attachments.AttachmentError) as cm:
				attachments.load(path)
			self.assertEqual(cm.exception.reason, "tooBig")
		finally:
			attachments.MAX_FILE_BYTES = old
		self.assertEqual(attachments.load(path).text, "a" * 100)
		oldT = attachments.MAX_TEXT_CHARS
		attachments.MAX_TEXT_CHARS = 10
		try:
			t = attachments.load(path)
			self.assertTrue(t.truncated)
			self.assertEqual(len(t.text), 10)
		finally:
			attachments.MAX_TEXT_CHARS = oldT
		with self.assertRaises(attachments.AttachmentError):
			attachments.load(os.path.join(folder, "nao-existe.txt"))

	def test_roundtrip_dict(self):
		for a in (self.load("a.pdf", b"%PDF-1"), self.load("b.txt", b"oi"), attachments.Attachment.image(PNG)):
			b = attachments.Attachment.fromDict(a.toDict())
			self.assertEqual((b.name, b.kind, b.mime, b.data, b.text), (a.name, a.kind, a.mime, a.data, a.text))

	def test_send_attachments_to_each_provider(self):
		pdf = self.load("contrato.pdf", b"%PDF-1.7 fake")
		txt = self.load("notas.txt", b"anotacoes")
		img = attachments.Attachment.image(PNG, name="foto.png")
		msg = providers.Message("user", "Resuma", attachments=[pdf, txt, img])
		for pid in providers.PROVIDER_IDS:
			with self.subTest(pid):
				self.assertTrue(make(pid).chat([msg], "sys"))
		self.assertEqual(mock_server.LAST_ATTACHMENTS["openai"], ["pdf", "texto", "imagem"])
		self.assertEqual(mock_server.LAST_ATTACHMENTS["gemini"], ["application/pdf", "texto", "image/png"])
		self.assertEqual(mock_server.LAST_ATTACHMENTS["anthropic"], ["document", "text", "image"])

	def test_media_only_gemini(self):
		audio = self.load("reuniao.mp3", b"ID3\x03binary")
		msg = providers.Message("user", "Transcreva", attachments=[audio])
		self.assertTrue(make("gemini").chat([msg], "sys"))
		self.assertEqual(mock_server.LAST_ATTACHMENTS["gemini"], ["audio/mp3"])
		for pid in ("openai", "anthropic"):
			mock_server.REQUESTS.clear()
			with self.assertRaises(providers.ProviderError) as cm:
				make(pid).chat([msg], "sys")
			self.assertEqual((cm.exception.kind, cm.exception.detail), ("attachment", "reuniao.mp3"))
			self.assertEqual(mock_server.REQUESTS, [], "nothing must be sent")

	def test_entry_keeps_attachments_and_legacy_image(self):
		e = conversation.ChatEntry("user", "x", attachments=[self.load("a.txt", b"oi")])
		d = e.toDict()
		self.assertEqual(conversation.ChatEntry.fromDict(d).attachmentNames(), ["a.txt"])
		legacy = {"role": "user", "text": "x", "time": 1, "image": base64.b64encode(PNG).decode(), "imageMime": "image/png"}
		self.assertEqual(conversation.ChatEntry.fromDict(legacy).image, PNG)

# ---------------------------------------------------------------------------
# Sign in with ChatGPT (ChatGPT plan, no API key)
# ---------------------------------------------------------------------------

class _FlipCodec:
	def protect(self, data):
		return bytes(b ^ 0x33 for b in data)

	def unprotect(self, data):
		return bytes(b ^ 0x33 for b in data)


class ChatGPTPlanTests(unittest.TestCase):
	def setUp(self):
		mock_server.REQUESTS.clear()
		mock_server.FORCE.clear()
		mock_server.resetChatGPT()
		self.folder = tempfile.mkdtemp()
		self.creds = credentials.CredentialStore(self.folder, codec=_FlipCodec())
		self.store = chatgptPlan.PlanStore(self.creds)
		self.session = chatgptPlan.PlanSession(self.store, chatgptPlan.OAuthClient(issuer=BASE + "/chatgpt/auth", timeout=5))

	def signIn(self, **kw):
		return self.session.signIn(mock_server.fakeBrowser, timeout=kw.pop("timeout", 10), **kw)

	def provider(self, model=None):
		return chatgptPlan.ChatGPTPlanProvider(self.session, model=model, baseUrl=BASE + "/chatgpt/v1", timeout=5)

	# Sign in ---------------------------------------------------------------

	def test_sign_in_stores_session(self):
		s = self.signIn()
		self.assertTrue(self.session.signedIn())
		self.assertEqual(self.session.email(), "pessoa@example.com")
		self.assertEqual(s["client_id"], mock_server.ISSUED_CLIENT)
		self.assertIn(chatgptPlan.PLAN_SCOPE, s["scopes"])
		self.assertEqual(s["subject"], "user-123")
		q = mock_server.CHATGPT["authorize"][0]
		self.assertEqual(q["client_id"], "dynamic_agent_client")
		self.assertEqual(q["agent_name_hint"], "NVDAIAs")
		self.assertTrue(q["redirect_uri"].startswith("http://127.0.0.1:"))
		self.assertEqual(len(q["state"]) >= 32 and len(q["nonce"]) >= 32, True)

	def test_second_sign_in_reuses_client_and_host(self):
		self.signIn()
		self.session.signOut()
		self.signIn()
		first, second = mock_server.CHATGPT["authorize"][:2]
		self.assertEqual(second["client_id"], mock_server.ISSUED_CLIENT)
		self.assertNotIn("agent_name_hint", second)
		self.assertEqual(second["login_hint"], "pessoa@example.com")
		self.assertEqual(first["ext_agent_host_id"], second["ext_agent_host_id"])
		self.assertNotEqual(first["state"], second["state"])
		self.assertNotEqual(first["code_challenge"], second["code_challenge"])

	def test_pkce_pair(self):
		verifier, challenge = chatgptPlan.pkcePair()
		self.assertTrue(43 <= len(verifier) <= 128)
		self.assertEqual(challenge, chatgptPlan.b64url(__import__("hashlib").sha256(verifier.encode()).digest()))
		self.assertNotIn("=", challenge)

	def test_access_denied(self):
		mock_server.CHATGPT["deny"] = True
		with self.assertRaises(providers.ProviderError) as cm:
			self.signIn()
		self.assertEqual(cm.exception.kind, "denied")
		self.assertFalse(self.session.signedIn())

	def test_callback_with_other_state_is_ignored(self):
		mock_server.CHATGPT["wrong_state"] = True
		with self.assertRaises(providers.ProviderError) as cm:
			self.signIn(timeout=1.5)
		self.assertEqual((cm.exception.kind, cm.exception.detail), ("timeout", "sign-in"))
		self.assertFalse(self.session.signedIn())
		self.assertEqual(mock_server.CHATGPT["codes"] != {}, True, "the code was never exchanged")

	def test_cancel(self):
		import threading
		cancel = threading.Event()
		cancel.set()
		with self.assertRaises(providers.ProviderError) as cm:
			self.session.signIn(lambda url: True, cancelEvent=cancel, timeout=5)
		self.assertEqual(cm.exception.kind, "cancelled")

	def test_browser_not_opened(self):
		with self.assertRaises(providers.ProviderError) as cm:
			self.session.signIn(lambda url: False, timeout=5)
		self.assertEqual(cm.exception.kind, "browser")
		self.assertTrue(cm.exception.detail.startswith(BASE + "/chatgpt/auth/api/accounts/authorize?"))

	def test_wrong_nonce_refused(self):
		mock_server.CHATGPT["bad_nonce"] = True
		with self.assertRaises(providers.ProviderError) as cm:
			self.signIn()
		self.assertEqual(cm.exception.kind, "signin")
		self.assertIn("nonce", cm.exception.detail)
		self.assertFalse(self.session.signedIn())

	def test_bad_signature_refused(self):
		mock_server.CHATGPT["bad_signature"] = True
		with self.assertRaises(providers.ProviderError) as cm:
			self.signIn()
		self.assertIn("signature", cm.exception.detail)
		self.assertFalse(self.session.signedIn())

	def test_plan_scope_required(self):
		mock_server.CHATGPT["scope"] = "openid profile email offline_access"
		with self.assertRaises(providers.ProviderError) as cm:
			self.signIn()
		self.assertEqual(cm.exception.kind, "planNotEligible")
		self.assertFalse(self.session.signedIn())

	def test_session_encrypted_at_rest(self):
		s = self.signIn()
		with open(self.creds.path, "rb") as f:
			raw = f.read()
		for secret in (s["access_token"], s["refresh_token"], s["id_token"][:40], "pessoa@example.com"):
			self.assertNotIn(secret.encode(), raw)
			self.assertNotIn(secret.encode(), base64.b64decode(json.loads(raw)[chatgptPlan.SESSION_KEY]))

	def test_store_safe_with_threads(self):
		"""Sign-in and token refresh write from background threads (P-10)."""
		import threading
		errors = []

		def writer(n):
			try:
				for i in range(40):
					self.creds.set("k%d" % n, "valor-%d-%d" % (n, i))
			except Exception as e:  # noqa: BLE001
				errors.append(repr(e))

		threads = [threading.Thread(target=writer, args=(n,)) for n in range(6)]
		for t in threads:
			t.start()
		for t in threads:
			t.join()
		self.assertEqual(errors, [])
		fresh = credentials.CredentialStore(self.folder, codec=_FlipCodec())
		self.assertEqual([fresh.get("k%d" % n) for n in range(6)], ["valor-%d-39" % n for n in range(6)])
		self.assertEqual([f for f in os.listdir(self.folder) if f.endswith(".tmp")], [])

	# ID token ---------------------------------------------------------------

	def _claims(self, **kw):
		import time as _t
		c = {"iss": "https://auth.openai.com", "aud": "oaiapp_x", "sub": "u", "exp": _t.time() + 600, "nonce": "n1"}
		c.update(kw)
		return c

	def _keys(self):
		import _testkey
		return {_testkey.KID: (_testkey.N, _testkey.E)}

	def test_id_token_valid(self):
		tok = mock_server.signJwt(self._claims())
		claims = chatgptPlan.validateIdToken(tok, self._keys(), "https://auth.openai.com", "oaiapp_x", "n1")
		self.assertEqual(claims["sub"], "u")

	def test_id_token_refusals(self):
		import time as _t
		cases = {
			"issuer": mock_server.signJwt(self._claims(iss="https://evil.example")),
			"audience": mock_server.signJwt(self._claims(aud="oaiapp_other")),
			"expired": mock_server.signJwt(self._claims(exp=_t.time() - 3600)),
			"nonce": mock_server.signJwt(self._claims(nonce="other")),
			"signature": mock_server.signJwt(self._claims(), corrupt=True),
		}
		for what, tok in cases.items():
			with self.subTest(what):
				with self.assertRaises(providers.ProviderError) as cm:
					chatgptPlan.validateIdToken(tok, self._keys(), "https://auth.openai.com", "oaiapp_x", "n1")
				self.assertEqual(cm.exception.kind, "signin")
				self.assertIn(what, cm.exception.detail)
		# alg "none" and HMAC algorithms are refused.
		for alg in ("none", "HS256"):
			with self.subTest(alg):
				h = chatgptPlan.b64url(json.dumps({"alg": alg}).encode())
				p = chatgptPlan.b64url(json.dumps(self._claims()).encode())
				with self.assertRaises(providers.ProviderError):
					chatgptPlan.validateIdToken(h + "." + p + ".", self._keys(), "https://auth.openai.com", "oaiapp_x", "n1")

	def test_rs256_needs_strong_key(self):
		self.assertFalse(chatgptPlan.verifyRs256(b"x", b"\x01" * 64, (1 << 511) + 1, 65537))

	def test_discovery_from_other_host_refused(self):
		def opener(req, timeout):
			return json.dumps({"jwks_uri": "https://evil.example/jwks"}).encode()

		client = chatgptPlan.OAuthClient(opener=opener)
		with self.assertRaises(providers.ProviderError):
			client.keys()
		for url, ok in (("https://auth.openai.com/.well-known/jwks.json", True), ("https://keys.openai.com/jwks", True),
				("http://auth.openai.com/jwks", False), ("https://openai.com.evil.example/jwks", False), ("https://evilopenai.com/jwks", False)):
			with self.subTest(url):
				self.assertEqual(chatgptPlan._trustedUrl(url, "https://auth.openai.com"), ok)

	# Tokens ------------------------------------------------------------------

	def test_refresh_when_expired(self):
		s = self.signIn()
		s["expires_at"] = 0
		self.store.saveSession(s)
		token = self.session.accessToken()
		self.assertNotEqual(token, s["access_token"])
		new = self.store.session()
		self.assertNotEqual(new["refresh_token"], s["refresh_token"], "refresh token rotates")
		form = [r for r in mock_server.REQUESTS if r["path"].endswith("/oauth/token")][-1]["body"]
		self.assertEqual((form["grant_type"], form["client_id"], form["resource"]), ("refresh_token", mock_server.ISSUED_CLIENT, "https://api.openai.com/v1"))
		self.assertNotIn("scope", form)

	def test_valid_token_not_refreshed(self):
		s = self.signIn()
		self.assertEqual(self.session.accessToken(), s["access_token"])

	def test_reused_refresh_token_ends_session(self):
		s = self.signIn()
		self.session.accessToken(force=True)
		self.store.saveSession(s)  # an old copy with the already used refresh token
		with self.assertRaises(providers.ProviderError) as cm:
			self.session.accessToken(force=True)
		self.assertEqual((cm.exception.kind, cm.exception.detail), ("signin", "refresh_token_reused"))
		self.assertFalse(self.session.signedIn())
		self.assertEqual(self.store.registration()["client_id"], mock_server.ISSUED_CLIENT, "registration kept for the next sign-in")

	def test_sign_out_revokes(self):
		s = self.signIn()
		self.assertTrue(self.session.signOut())
		self.assertFalse(self.session.signedIn())
		self.assertEqual(mock_server.CHATGPT["revoked"][0], {"token": s["refresh_token"], "token_type_hint": "refresh_token", "client_id": mock_server.ISSUED_CLIENT})

	def test_not_signed_in(self):
		with self.assertRaises(providers.ProviderError) as cm:
			self.provider("gpt-5.5").chat([providers.Message("user", "oi")])
		self.assertEqual(cm.exception.kind, "signin")

	# Inference -----------------------------------------------------------------

	def test_chat_with_plan(self):
		self.signIn()
		msgs = [providers.Message("user", "Oi"), providers.Message("assistant", "Olá!"), providers.Message("user", "Tudo bem?")]
		answer = self.provider("gpt-5.5").chat(msgs, "Seja breve.")
		self.assertEqual(answer, "Plano ChatGPT responde: Tudo bem? (3 mensagens)")
		body = mock_server.CHATGPT["responses"][-1]
		self.assertEqual((body["store"], body["stream"], body["instructions"]), (False, True, "Seja breve."))
		self.assertEqual(set(body), {"model", "input", "store", "stream", "instructions"})
		req = [r for r in mock_server.REQUESTS if r["path"].endswith("/responses")][-1]
		self.assertEqual(req["headers"]["Authorization"], "Bearer " + self.store.session()["access_token"])

	def test_attachments(self):
		self.signIn()
		files = [
			attachments.Attachment.image(PNG, name="tela.png"),
			attachments.Attachment("doc.pdf", "pdf", "application/pdf", data=b"%PDF-1.4 x"),
			attachments.Attachment("a.txt", "text", "text/plain", text="conteudo"),
		]
		self.provider("gpt-5.5").chat([providers.Message("user", "Veja", attachments=files)])
		self.assertEqual(mock_server.LAST_ATTACHMENTS["chatgpt"], ["imagem", "pdf", "texto"])
		media = attachments.Attachment("a.mp3", "media", "audio/mp3", data=b"ID3")
		mock_server.REQUESTS.clear()
		with self.assertRaises(providers.ProviderError) as cm:
			self.provider("gpt-5.5").chat([providers.Message("user", "x", attachments=[media])])
		self.assertEqual((cm.exception.kind, cm.exception.detail), ("attachment", "a.mp3"))
		self.assertFalse([r for r in mock_server.REQUESTS if r["path"].endswith("/responses")])

	def test_models_only_listed(self):
		self.signIn()
		self.assertEqual(self.provider().listModels(), ["gpt-5.5", "gpt-5.5-mini"])
		models, found = self.provider("gpt-internal").testConnection()
		self.assertFalse(found)

	def test_empty_model_uses_first(self):
		self.signIn()
		p = self.provider()
		p.chat([providers.Message("user", "oi")])
		self.assertEqual(p.model, "gpt-5.5")

	def test_401_refreshes_once_and_retries(self):
		s = self.signIn()
		mock_server.CHATGPT["access"].discard(s["access_token"])  # revoked on the server
		self.assertIn("oi", self.provider("gpt-5.5").chat([providers.Message("user", "oi")]))
		self.assertNotEqual(self.store.session()["access_token"], s["access_token"])

	def test_plan_errors(self):
		self.signIn()
		cases = [
			((429, {"error": {"code": "subscription_sharing_usage_limit_exceeded", "message": "limit"}}), "planLimit"),
			((403, {"error": {"code": "subscription_sharing_user_not_eligible", "message": "no"}}), "planNotEligible"),
			((403, {"error": {"code": "chatpass_v2_scope_not_authorized"}}), "planNotEligible"),
			((400, {"error": {"code": "subscription_sharing_unsupported_capability", "param": "tools"}}), "unsupported"),
			((503, {"error": {"code": "subscription_sharing_usage_unavailable"}}), "server"),
			((403, {"detail": "region not supported"}), "planNotEligible"),
			((401, {"error": {"code": "subscription_sharing_invalid_user"}}), "signin"),
		]
		for (status, body), kind in cases:
			with self.subTest(kind=kind, status=status):
				mock_server.FORCE["chatgpt"] = (status, body)
				with self.assertRaises(providers.ProviderError) as cm:
					self.provider("gpt-5.5").chat([providers.Message("user", "oi")])
				self.assertEqual(cm.exception.kind, kind)
		mock_server.FORCE["chatgpt"] = (400, {"error": {"code": "subscription_sharing_unsupported_capability", "param": "input[0].content[0]"}})
		with self.assertRaises(providers.ProviderError) as cm:
			self.provider("gpt-5.5").chat([providers.Message("user", "oi")])
		self.assertEqual(cm.exception.detail, "input[0].content[0]")

	def test_stream_events(self):
		def ev(*events):
			return "".join("data: %s\n\n" % json.dumps(e) for e in events)

		self.assertEqual(chatgptPlan.parseStream(ev(
			{"type": "response.output_text.delta", "delta": "Olá "},
			{"type": "response.output_text.delta", "delta": "mundo"},
			{"type": "response.completed", "response": {}},
		) + "data: [DONE]\n\n"), "Olá mundo")
		self.assertEqual(chatgptPlan.parseStream(ev({"type": "response.completed", "response": {"output": [
			{"type": "message", "content": [{"type": "output_text", "text": "só no fim"}]}]}})), "só no fim")
		bad = {
			"planLimit": ev({"type": "response.failed", "response": {"error": {"code": "subscription_sharing_usage_limit_exceeded", "message": "x"}}}),
			"server": ev({"type": "response.output_text.delta", "delta": "metade"}),
			"blocked": ev({"type": "response.refusal.delta", "delta": "não"}, {"type": "response.completed", "response": {}}),
		}
		for kind, text in bad.items():
			with self.subTest(kind):
				with self.assertRaises(providers.ProviderError) as cm:
					chatgptPlan.parseStream(text)
				self.assertEqual(cm.exception.kind, kind)
		with self.assertRaises(providers.ProviderError) as cm:
			chatgptPlan.parseStream(ev({"type": "response.output_text.delta", "delta": "a"}, {"type": "response.incomplete", "response": {"incomplete_details": {"reason": "max_output_tokens"}}}))
		self.assertIn("max_output_tokens", cm.exception.detail)

	def test_stream_from_server(self):
		self.signIn()
		mock_server.CHATGPT["stream"] = "data: " + json.dumps({"type": "error", "code": "subscription_sharing_usage_limit_exceeded", "message": "x"}) + "\n\n"
		with self.assertRaises(providers.ProviderError) as cm:
			self.provider("gpt-5.5").chat([providers.Message("user", "oi")])
		self.assertEqual(cm.exception.kind, "planLimit")

	# Loopback --------------------------------------------------------------------

	def test_loopback_only_local_and_callback(self):
		import urllib.error
		import urllib.request
		r = chatgptPlan.LoopbackReceiver("estado", pages={"done": "<b>pronto</b>"})
		try:
			self.assertEqual(r._server.server_address[0], "127.0.0.1")
			self.assertEqual(r.redirectUri, "http://127.0.0.1:%d/callback" % r.port)
			with self.assertRaises(urllib.error.HTTPError) as cm:
				urllib.request.urlopen("http://127.0.0.1:%d/outro?state=estado&code=c" % r.port, timeout=5)
			self.assertEqual(cm.exception.code, 404)
			with self.assertRaises(urllib.error.HTTPError) as cm:
				urllib.request.urlopen("http://127.0.0.1:%d/callback?state=errado&code=c" % r.port, timeout=5)
			self.assertEqual(cm.exception.code, 400)
			self.assertIsNone(r.result)
			with urllib.request.urlopen("http://127.0.0.1:%d/callback?state=estado&code=c1" % r.port, timeout=5) as resp:
				page = resp.read().decode()
				self.assertEqual(resp.headers["Cache-Control"], "no-store")
			self.assertIn("&lt;b&gt;pronto&lt;/b&gt;", page)
			self.assertEqual(r.wait(1)["code"], "c1")
		finally:
			r.close()


if __name__ == "__main__":
	unittest.main(verbosity=2)
