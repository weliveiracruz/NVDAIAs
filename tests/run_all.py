# -*- coding: UTF-8 -*-
"""Runs every NVDAIAs test suite, counts the results and keeps the history.

Usage:  python tests/run_all.py [--note "text"]

Needs Linux with python3-wxgtk4.0 and xvfb (the GitHub workflow installs them).
Writes:
  reports/execucoes.json     - every execution (date, version, results per suite)
  reports/ULTIMA-EXECUCAO.md - summary of the last execution, in Portuguese
Exit code 0 only when every test passed.
"""

import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
REPORTS = os.path.join(ROOT, "reports")
HISTORY = os.path.join(REPORTS, "execucoes.json")


def version():
	with open(os.path.join(ROOT, "addon", "manifest.ini"), encoding="utf-8") as f:
		return re.search(r"^version\s*=\s*(\S+)", f.read(), re.M).group(1)


def findWxPython():
	for candidate in (sys.executable, "/usr/bin/python3", "python3.12", "python3"):
		exe = shutil.which(candidate) or (candidate if os.path.exists(candidate) else None)
		if exe and subprocess.run([exe, "-c", "import wx"], capture_output=True).returncode == 0:
			return exe
	return None


def unitPythons():
	found = []
	for v in ("3.11", "3.12", "3.13"):
		exe = shutil.which("python" + v)
		if exe:
			found.append(exe)
	return found or [sys.executable]


def runSuite(cmd, env=None, timeout=600):
	e = dict(os.environ)
	e.update(env or {})
	try:
		proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, env=e, timeout=timeout)
		out = proc.stdout + proc.stderr
	except subprocess.TimeoutExpired as ex:
		out = (ex.stdout or "") if isinstance(ex.stdout, str) else ""
		out += "\nTIMEOUT"
	results = [json.loads(line[7:]) for line in out.splitlines() if line.startswith("RESULT ")]
	if not results:
		name = " ".join(os.path.basename(c) for c in cmd[-2:])
		return {"suite": name, "total": 1, "passed": 0, "failed": 1, "failures": ["suite did not finish: " + name], "tests": ["suite did not finish: " + name], "log": out[-3000:]}
	r = results[-1]
	r["log"] = out[-3000:] if r["failed"] else ""
	return r


def buildSuite():
	tests = ["FUN-13 build.py validates the manifest and builds", "FUN-13 package has manifest, plugin, docs, translation and installTasks"]
	failures = []
	proc = subprocess.run([sys.executable, "build.py"], cwd=ROOT, capture_output=True, text=True)
	pkg = os.path.join(ROOT, "dist", "NVDAIAs-%s.nvda-addon" % version())
	if proc.returncode != 0 or not os.path.exists(pkg):
		failures.append(tests[0])
		failures.append(tests[1])
	else:
		names = set(zipfile.ZipFile(pkg).namelist())
		needed = {"manifest.ini", "installTasks.py", "globalPlugins/NVDAIAs/__init__.py", "doc/en/readme.html", "doc/pt_BR/readme.html", "locale/pt_BR/LC_MESSAGES/nvda.mo", "locale/pt_BR/manifest.ini", "globalPlugins/NVDAIAs/design/tokens.json"}
		if not needed <= names or any(n.endswith((".pyc", ".po")) for n in names):
			failures.append(tests[1])
	return {"suite": "package (build.py)", "total": 2, "passed": 2 - len(failures), "failed": len(failures), "failures": failures, "tests": tests, "log": proc.stdout[-1500:] + proc.stderr[-1500:] if failures else ""}


def main():
	note = ""
	if "--note" in sys.argv:
		note = sys.argv[sys.argv.index("--note") + 1]
	wxPython = findWxPython()
	xvfb = [] if os.environ.get("DISPLAY") else (["xvfb-run", "-a", "-s", "-screen 0 1400x1000x24"] if shutil.which("xvfb-run") else [])
	suites = []
	for exe in unitPythons():
		suites.append(runSuite([exe, os.path.join("tests", "_run_unittest.py")]))
	if wxPython:
		for script, env in (("test_gui.py", {}), ("test_theme.py", {}), ("test_translation.py", {"NVDAIAS_LANG": "pt_BR"}), ("test_accessibility.py", {}), ("test_security.py", {}), ("test_update.py", {})):
			suites.append(runSuite(xvfb + [wxPython, "-u", os.path.join("tests", script)], env=env))
	else:
		suites.append({"suite": "wxPython", "total": 1, "passed": 0, "failed": 1, "failures": ["wxPython not found: install python3-wxgtk4.0"], "tests": ["wxPython"], "log": ""})
	suites.append(buildSuite())

	os.makedirs(REPORTS, exist_ok=True)
	try:
		with open(HISTORY, encoding="utf-8") as f:
			runs = json.load(f)
	except (OSError, ValueError):
		runs = []
	previous = runs[-1] if runs else None
	prevFailed = set()
	if previous:
		for s in previous["suites"]:
			prevFailed.update("%s :: %s" % (s["suite"], t) for t in s["failures"])
	nowFailed = set()
	nowAll = set()
	for s in suites:
		nowFailed.update("%s :: %s" % (s["suite"], t) for t in s["failures"])
		nowAll.update("%s :: %s" % (s["suite"], t) for t in s.get("tests", []))
	corrected = sorted(t for t in prevFailed if t in nowAll and t not in nowFailed) if previous and previous["version"] == version() else []

	total = sum(s["total"] for s in suites)
	passed = sum(s["passed"] for s in suites)
	failed = sum(s["failed"] for s in suites)
	run = {
		"number": len(runs) + 1,
		"date": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
		"version": version(),
		"note": note,
		"total": total,
		"passed": passed,
		"failed": failed,
		"corrected": corrected,
		"suites": [{k: s[k] for k in ("suite", "total", "passed", "failed", "failures")} for s in suites],
	}
	runs.append(run)
	with open(HISTORY, "w", encoding="utf-8") as f:
		json.dump(runs, f, ensure_ascii=False, indent=1)

	sameVersion = [r for r in runs if r["version"] == run["version"]]
	lines = [
		"# Última execução dos testes",
		"",
		"* Execução nº %d (%d nesta versão) em %s" % (run["number"], len(sameVersion), run["date"]),
		"* Versão: %s" % run["version"],
	]
	if note:
		lines.append("* Observação: %s" % note)
	lines += [
		"* **Testes: %d · Aprovados: %d · Falharam: %d · Corrigidos desde a execução anterior: %d**" % (total, passed, failed, len(corrected)),
		"",
		"| Suíte | Testes | Aprovados | Falharam |",
		"|---|---|---|---|",
	]
	for s in suites:
		lines.append("| %s | %d | %d | %d |" % (s["suite"], s["total"], s["passed"], s["failed"]))
	if failed:
		lines += ["", "## Falhas", ""]
		for s in suites:
			for t in s["failures"]:
				lines.append("* %s: %s" % (s["suite"], t))
	if corrected:
		lines += ["", "## Corrigidos desde a execução anterior", ""]
		lines += ["* %s" % t for t in corrected]
	with open(os.path.join(REPORTS, "ULTIMA-EXECUCAO.md"), "w", encoding="utf-8") as f:
		f.write("\n".join(lines) + "\n")

	print("\n".join(lines))
	for s in suites:
		if s.get("log"):
			print("\n--- %s (log) ---\n%s" % (s["suite"], s["log"]))
	return 1 if failed else 0


if __name__ == "__main__":
	sys.exit(main())
