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

from NVDAIAs import providers, textutils, credentials, conversation  # noqa: E402
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
		self.assertEqual(msgs[0].image, PNG)
		self.assertEqual(c.lastAnswer().text, "Olá")
		text = c.toText("Você", "[imagem]")
		self.assertIn("Você:\n[imagem]\nOi", text)
		self.assertIn("Claude (claude-sonnet-5-5):\nOlá", text)
		c.remove(u)
		self.assertEqual(len(c), 1)
		c.clear()
		self.assertEqual(len(c), 0)


if __name__ == "__main__":
	unittest.main(verbosity=2)
