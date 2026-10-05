# -*- coding: UTF-8 -*-
"""Vulnerability tests (SEG-xx in docs/SDD-TESTES.md).

Run (Linux): xvfb-run -a python3 tests/test_security.py
"""
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
ADDON = os.path.join(ROOT, "addon")
PKG = os.path.join(ADDON, "globalPlugins", "NVDAIAs")
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ADDON, "globalPlugins"))
sys.path.insert(0, ADDON)
import wx  # noqa: E402

import nvda_stubs  # noqa: E402
from nvda_stubs import RECORD  # noqa: E402
from _results import Recorder  # noqa: E402

CONFIG = nvda_stubs.install()
import mock_server  # noqa: E402

SERVER, BASE = mock_server.start()
app = wx.App(False)
import gui  # noqa: E402

gui.mainFrame = gui.MainFrame()
import NVDAIAs  # noqa: E402
from NVDAIAs import attachments, chatDialog, core, credentials, history, providers  # noqa: E402

for cls, path in ((providers.OpenAIProvider, "/openai/v1"), (providers.GeminiProvider, "/gemini/v1beta"), (providers.AnthropicProvider, "/anthropic/v1")):
	cls.defaultBaseUrl = BASE + path
REAL_BASES = {"openai": "https://api.openai.com/v1", "gemini": "https://generativelanguage.googleapis.com/v1beta", "anthropic": "https://api.anthropic.com/v1"}

R = Recorder("security (test_security)")


class XorCodec:
	def protect(self, data):
		return bytes(b ^ 0x5A for b in data)

	def unprotect(self, data):
		return bytes(b ^ 0x5A for b in data)


def pump(until=lambda: False, timeout=5.0):
	end = time.time() + timeout
	while time.time() < end:
		wx.Yield()
		if until():
			return True
		time.sleep(0.02)
	return until()


def addonSources():
	out = {}
	for folder, _dirs, files in os.walk(ADDON):
		for name in files:
			if name.endswith(".py"):
				path = os.path.join(folder, name)
				with open(path, encoding="utf-8") as f:
					out[os.path.relpath(path, ROOT)] = f.read()
	return out


def zipDoc(xml, name="word/document.xml", extra=None):
	buf = io.BytesIO()
	with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
		z.writestr(name, xml)
		for k, v in (extra or {}).items():
			z.writestr(k, v)
	return buf.getvalue()


def run():
	sources = addonSources()

	# SEG-01 tokens at rest --------------------------------------------------------
	folder = tempfile.mkdtemp()
	store = credentials.CredentialStore(folder, codec=XorCodec())
	token = "sk-proj-SEGREDO-1234567890abcdef"
	store.set("openai", token)
	with open(store.path, "rb") as f:
		raw = f.read()
	R.check("SEG-01 token file does not contain the token", token.encode() not in raw and b"SEGREDO" not in raw)
	R.check("SEG-01 token is not stored in the NVDA configuration", token not in json.dumps(dict(nvda_stubs.sys.modules["config"].conf), default=str))

	# SEG-02 no token leaks ---------------------------------------------------------
	plugin = NVDAIAs.GlobalPlugin()
	secret = mock_server.VALID["openai"]
	core.store().set("openai", secret)
	core.conf()["provider"] = "openai"
	dlg = chatDialog.ChatDialog.showInstance(plugin.session)
	dlg.questionEdit.SetValue("oi")
	dlg.onSend(None)
	pump(lambda: not plugin.session.busy, 10)
	core.store().set("openai", "sk-ERRADO-" + "x" * 30)
	dlg.questionEdit.SetValue("vai falhar")
	dlg.onSend(None)
	pump(lambda: not plugin.session.busy, 10)
	wrong = "sk-ERRADO-" + "x" * 30
	everything = "\n".join(RECORD.get("log", []) + RECORD["spoken"] + RECORD["messageBoxes"])
	R.check("SEG-02 token never in log, speech or messages", secret not in everything and wrong not in everything, [l for l in everything.split("\n") if "sk-" in l][:3])
	hist = json.dumps(core.history().list(), default=str)
	R.check("SEG-02 token never in the conversation history", secret not in hist and wrong not in hist)
	core.store().set("openai", secret)

	# SEG-03 TLS ---------------------------------------------------------------------
	ctx = providers._getSslContext()
	import ssl
	R.check("SEG-03 certificate and host name verification on", ctx.verify_mode == ssl.CERT_REQUIRED and ctx.check_hostname)
	bad = [p for p, src in sources.items() if re.search(r"CERT_NONE|check_hostname\s*=\s*False|_create_unverified_context|verify\s*=\s*False", src)]
	R.check("SEG-03 no code that disables TLS verification", not bad, bad)

	# SEG-04 timeouts ---------------------------------------------------------------
	seen = []

	def opener(req, timeout):
		seen.append(timeout)
		raise providers.ProviderError("network", "stop")

	for cls in providers.PROVIDERS:
		p = cls("k", opener=opener, timeout=30)
		for call in (lambda: p.chat([providers.Message("user", "x")]), p.listModels):
			try:
				call()
			except providers.ProviderError:
				pass
	R.check("SEG-04 every request has a time limit", seen and all(t and t > 0 for t in seen), seen)
	R.check("SEG-04 the connection always receives the time limit", re.search(r"(urlopen|\.open)\(req, timeout=timeout", sources[os.path.join("addon", "globalPlugins", "NVDAIAs", "providers.py")]) is not None)

	# SEG-05 HTTPS ----------------------------------------------------------------------
	R.check("SEG-05 default API addresses use HTTPS", all(u.startswith("https://") for u in REAL_BASES.values()))
	srcProviders = sources[os.path.join("addon", "globalPlugins", "NVDAIAs", "providers.py")]
	R.check("SEG-05 provider code declares only HTTPS addresses", all(u in srcProviders for u in REAL_BASES.values()) and "http://" not in srcProviders)

	# SEG-06 HTML injection --------------------------------------------------------------
	evil = core.ChatEntry(
		"assistant",
		"<script>alert(1)</script> <img src=x onerror=alert(2)> [a](javascript:alert(3)) [b](data:text/html;base64,PHNjcmlwdD4=) [c](https://ok.example)",
		providerName="X",
		attachments=[attachments.Attachment("<b onmouseover=alert(4)>.txt", "text", "text/plain", text="t")],
	)
	chatDialog.showMessageText(evil, "t")
	html = RECORD["browseable"][-1][0]
	R.check("SEG-06 no script tag reaches the reading window", "<script" not in html.lower(), html)
	R.check("SEG-06 no HTML event handlers", not re.search(r"<[^>]+\son\w+\s*=", html, re.I), html)
	R.check("SEG-06 javascript: and data: links removed", 'href="javascript' not in html and 'href="data' not in html, html)
	R.check("SEG-06 safe https links kept", 'href="https://ok.example"' in html)
	R.check("SEG-06 attachment names escaped", "<b onmouseover" not in html)

	# SEG-07 path traversal --------------------------------------------------------------
	hs = history.HistoryStore(tempfile.mkdtemp(), codec=XorCodec())
	refused = []
	for bad in ("../../evil", "..\\evil", "a/b", "", "x" * 200, "C:evil"):
		try:
			hs.save({"id": bad, "entries": [{"role": "user", "text": "x"}]})
			refused.append(False)
		except ValueError:
			refused.append(True)
	R.check("SEG-07 conversation ids with paths are refused", all(refused), refused)
	try:
		hs.load("../../etc/passwd")
		ok = False
	except (KeyError, ValueError):
		ok = True
	R.check("SEG-07 loading with a path is refused", ok)

	# SEG-08 history at rest ---------------------------------------------------------------
	conv = {"id": "teste-1", "created": 1, "entries": [{"role": "user", "text": "SEGREDO DO USUARIO", "attachments": [attachments.Attachment("x.txt", "text", "text/plain", text="CONTEUDO SECRETO").toDict()]}]}
	hs.save(conv)
	with open(os.path.join(hs.folder, "teste-1" + history.EXTENSION), "rb") as f:
		raw = f.read()
	import base64
	decoded = base64.b64decode(raw)
	R.check("SEG-08 conversation and attachments encrypted on disk", b"SEGREDO" not in raw and b"SEGREDO" not in decoded and b"SECRETO" not in decoded)

	# SEG-09 zip bomb -----------------------------------------------------------------------
	W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
	bomb = zipDoc("<w:document %s><w:body><w:p><w:r><w:t>" % W + "A" * (80 * 1024 * 1024) + "</w:t></w:r></w:p></w:body></w:document>")
	start = time.time()
	try:
		attachments.fromBytes("bomba.docx", bomb)
		refusedBomb = False
	except attachments.AttachmentError:
		refusedBomb = True
	elapsed = time.time() - start
	R.check("SEG-09 compressed document that expands to 80 MB is refused (file has %d KB)" % (len(bomb) // 1024), refusedBomb, "accepted")
	R.check("SEG-09 zip bomb handled quickly (%.1fs)" % elapsed, elapsed < 3, elapsed)

	# SEG-10 billion laughs -------------------------------------------------------------------
	lol = '<?xml version="1.0"?><!DOCTYPE lolz [<!ENTITY lol "lol">' + "".join(
		'<!ENTITY lol%d "%s">' % (i, ("&lol%d;" % (i - 1) if i > 1 else "&lol;") * 10) for i in range(1, 10)
	) + ']><w:document %s><w:body><w:p><w:r><w:t>&lol9;</w:t></w:r></w:p></w:body></w:document>' % W
	start = time.time()
	try:
		a = attachments.fromBytes("lol.docx", zipDoc(lol))
		size = len(a.text or "")
	except attachments.AttachmentError:
		size = 0
	elapsed = time.time() - start
	R.check("SEG-10 XML entity expansion does not blow up (%.2fs, %d chars)" % (elapsed, size), elapsed < 2 and size < 100000, (elapsed, size))

	# SEG-11 XXE ------------------------------------------------------------------------------------
	secretFile = os.path.join(tempfile.mkdtemp(), "segredo.txt")
	with open(secretFile, "w") as f:
		f.write("CONTEUDO-DO-DISCO")
	xxe = '<?xml version="1.0"?><!DOCTYPE d [<!ENTITY x SYSTEM "file://%s">]><w:document %s><w:body><w:p><w:r><w:t>&x;</w:t></w:r></w:p></w:body></w:document>' % (secretFile, W)
	try:
		a = attachments.fromBytes("xxe.docx", zipDoc(xxe))
		text = a.text or ""
	except attachments.AttachmentError:
		text = ""
	R.check("SEG-11 external XML entities are not read", "CONTEUDO-DO-DISCO" not in text)

	# SEG-12 model name injection -----------------------------------------------------------------
	mock_server.REQUESTS.clear()
	try:
		providers.GeminiProvider(mock_server.VALID["gemini"], model="../../v1/files?key=x#", baseUrl=BASE + "/gemini/v1beta", timeout=5).chat([providers.Message("user", "x")], "s")
	except providers.ProviderError:
		pass
	path = mock_server.REQUESTS[-1]["path"] if mock_server.REQUESTS else ""
	R.check("SEG-12 model name cannot change the API address", path.startswith("/gemini/v1beta/models/") and "?" not in path and "/../" not in path, path)

	# SEG-13 bandit -------------------------------------------------------------------------------
	proc = subprocess.run([sys.executable, "-m", "bandit", "-r", ADDON, "-f", "json", "-q"], capture_output=True, text=True)
	try:
		report = json.loads(proc.stdout or "{}")
	except ValueError:
		report = {}
	issues = [r for r in report.get("results", []) if r.get("issue_severity") in ("MEDIUM", "HIGH")]
	summary = ["%s %s %s:%s" % (r["test_id"], r["issue_severity"], os.path.relpath(r["filename"], ROOT), r["line_number"]) for r in issues]
	R.check("SEG-13 bandit: no medium or high severity issue", "results" in report and not issues, summary or proc.stderr[-300:])

	# SEG-14 dangerous functions ---------------------------------------------------------------------
	pattern = re.compile(r"\b(eval|exec)\s*\(|\bpickle\b|\bmarshal\b|\bsubprocess\b|os\.system|os\.popen|shell\s*=\s*True|__import__\(")
	found = ["%s: %s" % (p, m.group(0)) for p, src in sources.items() for m in pattern.finditer(src)]
	R.check("SEG-14 no eval, exec, pickle, shell or subprocess", not found, found)

	# SEG-15 secure screens ----------------------------------------------------------------------------
	import globalVars
	globalVars.appArgs.secure = True
	R.check("SEG-15 add-on disabled on secure screens", NVDAIAs.disableInSecureMode(object) is sys.modules["globalPluginHandler"].GlobalPlugin)
	globalVars.appArgs.secure = False

	# SEG-16 uninstall ------------------------------------------------------------------------------------
	core.store().set("gemini", "abc")
	plugin.session.saveToHistory()
	import importlib
	installTasks = importlib.import_module("installTasks")
	installTasks.onUninstall()
	R.check("SEG-16 uninstall deletes the tokens", not os.path.exists(os.path.join(CONFIG, credentials.FILE_NAME)))
	R.check("SEG-16 uninstall deletes the history", not os.path.exists(os.path.join(CONFIG, history.FOLDER_NAME)))

	# SEG-17 attachment size ----------------------------------------------------------------------------
	big = os.path.join(tempfile.mkdtemp(), "grande.bin")
	with open(big, "wb") as f:
		f.seek(attachments.MAX_FILE_BYTES + 10)
		f.write(b"x")
	try:
		attachments.load(big)
		reason = None
	except attachments.AttachmentError as e:
		reason = e.reason
	R.check("SEG-17 files above the limit are refused", reason == "tooBig", reason)

	# SEG-18 huge response -------------------------------------------------------------------------------
	limit = getattr(providers, "MAX_RESPONSE_BYTES", None)
	R.check("SEG-18 there is a limit for the size of an answer", limit is not None and limit <= 64 * 1024 * 1024, limit)
	if limit is not None:
		old = providers.MAX_RESPONSE_BYTES
		providers.MAX_RESPONSE_BYTES = 2000
		mock_server.FORCE["openai"] = ("raw", json.dumps({"choices": [{"message": {"content": "a" * 50000}}]}))
		try:
			providers.OpenAIProvider(secret, baseUrl=BASE + "/openai/v1", timeout=5).chat([providers.Message("user", "x")])
			kind = None
		except providers.ProviderError as e:
			kind = e.kind
		providers.MAX_RESPONSE_BYTES = old
		mock_server.FORCE.clear()
		R.check("SEG-18 an answer above the limit is refused", kind == "server", kind)

	# SEG-19 redirects ----------------------------------------------------------------------------------
	captured = []

	class Evil(BaseHTTPRequestHandler):
		def log_message(self, *a):
			pass

		def do_POST(self):
			captured.append(dict(self.headers))
			self.send_response(200)
			self.send_header("Content-Length", "2")
			self.end_headers()
			self.wfile.write(b"{}")

		do_GET = do_POST

	evil = ThreadingHTTPServer(("127.0.0.1", 0), Evil)
	threading.Thread(target=evil.serve_forever, daemon=True).start()
	for pid, key, header in (("openai", mock_server.VALID["openai"], "Authorization"), ("anthropic", mock_server.VALID["anthropic"], "x-api-key")):
		mock_server.FORCE[pid] = ("redirect", "http://127.0.0.1:%d/roubar" % evil.server_address[1])
		cls = providers.getProviderClass(pid)
		client = cls(key, baseUrl=BASE + {"openai": "/openai/v1", "anthropic": "/anthropic/v1"}[pid], timeout=5)
		for call in (lambda: client.chat([providers.Message("user", "x")], "s"), client.testConnection):
			try:
				call()
			except providers.ProviderError:
				pass
		mock_server.FORCE.clear()
	leaked = [h for h in captured if any(key in str(v) for v in h.values() for key in (mock_server.VALID["openai"], mock_server.VALID["anthropic"]))]
	R.check("SEG-19 API key is never re-sent to another address by a redirect", not leaked, len(leaked))
	evil.shutdown()

	# SEG-20 screenshots only on command --------------------------------------------------------------------
	users = [p for p, src in sources.items() if "captureRect(" in src and not p.endswith("screenshot.py")]
	R.check("SEG-20 screen capture only called from the user commands", users == [os.path.join("addon", "globalPlugins", "NVDAIAs", "__init__.py")], users)
	initSrc = sources[os.path.join("addon", "globalPlugins", "NVDAIAs", "__init__.py")]
	R.check("SEG-20 no timer triggers a capture", "Timer" not in initSrc and "CallLater" not in initSrc)

	# SEG-22 addresses opened in the browser
	from NVDAIAs import feedback
	R.check("SEG-22 feedback form address is HTTPS on docs.google.com", feedback.FEEDBACK_URL.startswith("https://docs.google.com/forms/"))
	opens = ["%s: %s" % (p, line.strip()) for p, src in sources.items() for line in src.splitlines() if "webbrowser.open(" in line]
	openers = sorted(o.split(":")[0] for o in opens)
	expected = sorted(os.path.join("addon", "globalPlugins", "NVDAIAs", n) for n in ("connectDialog.py", "feedback.py", "planUi.py"))
	R.check("SEG-22 the browser is only opened by the feedback form, the token pages and the ChatGPT sign-in/usage", openers == expected and all(("(url" in o) for o in opens), opens)
	R.check("SEG-22 token pages are HTTPS", all(cls.tokenUrl.startswith("https://") for cls in providers.PROVIDERS))
	from NVDAIAs import chatgptPlan, planUi
	R.check("SEG-22 ChatGPT usage page is HTTPS on chatgpt.com", chatgptPlan.USAGE_URL == "https://chatgpt.com/settings/usage")

	# SEG-23 Sign in with ChatGPT: OAuth with PKCE ----------------------------------------------------------
	srcPlan = sources[os.path.join("addon", "globalPlugins", "NVDAIAs", "chatgptPlan.py")]
	R.check("SEG-23 OpenAI addresses are HTTPS", all(u.startswith("https://") for u in (chatgptPlan.ISSUER, chatgptPlan.API_BASE, chatgptPlan.RESOURCE)) and chatgptPlan.ISSUER == "https://auth.openai.com")
	httpUses = re.findall(r'"http://[^"]*"', srcPlan)
	R.check("SEG-23 the only plain HTTP address is the loopback 127.0.0.1/callback", httpUses == ['"http://127.0.0.1:%d/callback"'], httpUses)
	R.check("SEG-23 public client: no client secret anywhere", not any("client_secret" in src for src in sources.values()))
	client = chatgptPlan.OAuthClient()
	verifier, challenge = chatgptPlan.pkcePair()
	url = client.buildAuthorizeUrl("dynamic_agent_client", "urn:uuid:x", "http://127.0.0.1:1234/callback", chatgptPlan.randomToken(), chatgptPlan.randomToken(), challenge)
	import urllib.parse
	q = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query))
	R.check("SEG-23 authorize request uses PKCE S256, random state and nonce", url.startswith("https://auth.openai.com/api/accounts/authorize?") and q["code_challenge_method"] == "S256" and len(q["state"]) >= 40 and len(q["nonce"]) >= 40 and verifier not in url, q)
	states = {chatgptPlan.randomToken() for _ in range(200)}
	R.check("SEG-23 state values never repeat", len(states) == 200)
	receiver = chatgptPlan.LoopbackReceiver("s")
	R.check("SEG-23 the sign-in listener only accepts this computer (127.0.0.1)", receiver._server.server_address[0] == "127.0.0.1")
	import urllib.request
	import urllib.error
	try:
		urllib.request.urlopen("http://127.0.0.1:%d/callback?state=atacante&code=roubado" % receiver.port, timeout=5)
		forged = True
	except urllib.error.HTTPError:
		forged = receiver.result is not None
	receiver.close()
	R.check("SEG-23 an answer with another state is refused (CSRF)", not forged)
	R.check("SEG-23 the listener never logs the address (it carries the code)", "def log_message(self, *args):\n\t\t# Never log" in srcPlan)
	R.check("SEG-23 OAuth requests have a time limit", "self._opener(req, self.timeout)" in srcPlan and "_urlopen(req, self.timeout)" in srcPlan)

	# SEG-24 ChatGPT session at rest and in logs ---------------------------------------------------------------
	mock_server.resetChatGPT()
	planFolder = tempfile.mkdtemp()
	planCreds = credentials.CredentialStore(planFolder, codec=XorCodec())
	planSession = chatgptPlan.PlanSession(chatgptPlan.PlanStore(planCreds), chatgptPlan.OAuthClient(issuer=BASE + "/chatgpt/auth", timeout=5))
	sess = planSession.signIn(mock_server.fakeBrowser, timeout=10)
	with open(planCreds.path, "rb") as f:
		raw = f.read()
	R.check("SEG-24 ChatGPT tokens encrypted on disk", all(t.encode() not in raw for t in (sess["access_token"], sess["refresh_token"], sess["id_token"][:30])))
	core._plan = planSession
	core.store = lambda: planCreds
	core.conf()["openaiUsePlan"] = True
	chatgptPlan.ChatGPTPlanProvider.defaultBaseUrl = BASE + "/chatgpt/v1"
	core.conf()["model_openai_plan"] = "gpt-5.5"
	RECORD.setdefault("log", [])
	plugin2 = NVDAIAs.GlobalPlugin()
	plugin2.session.send("oi", providerId="openai")
	pump(lambda: not plugin2.session.busy, 10)
	mock_server.FORCE["chatgpt"] = (401, {"error": {"code": "subscription_sharing_invalid_user", "message": "x"}})
	plugin2.session.send("falha", providerId="openai")
	pump(lambda: not plugin2.session.busy, 10)
	mock_server.FORCE.clear()
	current = planSession.store.session()
	secrets = [s for s in (sess["access_token"], sess["refresh_token"], current.get("access_token"), current.get("refresh_token")) if s]
	everything = "\n".join(RECORD.get("log", []) + RECORD["spoken"] + RECORD["messageBoxes"]) + json.dumps(dict(nvda_stubs.sys.modules["config"].conf), default=str)
	R.check("SEG-24 ChatGPT tokens never in log, speech, messages or NVDA configuration", not any(re.search(r"\b%s\b" % re.escape(s), everything) for s in secrets), secrets)
	R.check("SEG-24 ChatGPT answer arrived through the plan", any("Plano ChatGPT responde" in e.text for e in plugin2.session.conversation.entries))
	plugin2.terminate()

	# SEG-25 ID token checks ----------------------------------------------------------------------------------------
	import _testkey
	keys = {_testkey.KID: (_testkey.N, _testkey.E)}
	good = {"iss": "https://auth.openai.com", "aud": "c", "sub": "u", "exp": time.time() + 60, "nonce": "n"}
	refusedTokens = []
	for label, token in (
		("bad signature", mock_server.signJwt(good, corrupt=True)),
		("alg none", chatgptPlan.b64url(b'{"alg":"none"}') + "." + chatgptPlan.b64url(json.dumps(good).encode()) + "."),
		("alg HS256", chatgptPlan.b64url(b'{"alg":"HS256"}') + "." + chatgptPlan.b64url(json.dumps(good).encode()) + ".YQ"),
		("other issuer", mock_server.signJwt(dict(good, iss="https://evil.example"))),
		("other audience", mock_server.signJwt(dict(good, aud="x"))),
		("replayed nonce", mock_server.signJwt(dict(good, nonce="velho"))),
	):
		try:
			chatgptPlan.validateIdToken(token, keys, "https://auth.openai.com", "c", "n")
		except providers.ProviderError:
			refusedTokens.append(label)
	R.check("SEG-25 forged or replayed ID tokens are refused", len(refusedTokens) == 6, refusedTokens)

	# SEG-26 ChatGPT access token never follows a redirect ----------------------------------------------------------
	capturedPlan = []

	class Evil2(BaseHTTPRequestHandler):
		def log_message(self, *a):
			pass

		def do_GET(self):
			capturedPlan.append(dict(self.headers))
			self.send_response(200)
			self.send_header("Content-Length", "2")
			self.end_headers()
			self.wfile.write(b"{}")

		do_POST = do_GET

	evil2 = ThreadingHTTPServer(("127.0.0.1", 0), Evil2)
	threading.Thread(target=evil2.serve_forever, daemon=True).start()
	mock_server.FORCE["chatgpt"] = ("redirect", "http://127.0.0.1:%d/roubar" % evil2.server_address[1])
	planProvider = chatgptPlan.ChatGPTPlanProvider(planSession, model="gpt-5.5", baseUrl=BASE + "/chatgpt/v1", timeout=5)
	for call in (lambda: planProvider.chat([providers.Message("user", "x")]), planProvider.listModels):
		try:
			call()
		except providers.ProviderError:
			pass
	mock_server.FORCE.clear()
	evil2.shutdown()
	R.check("SEG-26 ChatGPT access token is never re-sent to another address by a redirect", not any("Bearer" in str(h) for h in capturedPlan), len(capturedPlan))
	R.check("SEG-26 sign out revokes the session at OpenAI", planSession.signOut() and not planSession.signedIn())

	# SEG-21 error detail size ----------------------------------------------------------------------------------
	msg = core.errorMessage(providers.ProviderError("other", "x" * 5000), "Claude")
	R.check("SEG-21 error details are limited", len(msg) < 600, len(msg))
	plugin.terminate()


try:
	run()
except Exception:
	import traceback
	traceback.print_exc()
	R.check("suite ran to the end", False, "exception")
sys.exit(R.finish())
