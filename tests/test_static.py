"""Static scans over the source: every subprocess and network call has a timeout."""

import ast
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

PACKAGE = Path(__file__).resolve().parents[1] / "halmem"
SUBPROCESS_CALLS = {"run", "call", "check_call", "check_output"}
# Programs the ingest scripts start; each must run under `timeout`.
SHELL_TOOLS = ("pandoc", "pdftotext", "pdftoppm", "pdfinfo", "tesseract", "git", "python3")


def _calls(tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            yield node


def test_every_subprocess_call_has_a_timeout():
    missing = []
    for path in sorted(PACKAGE.glob("*.py")):
        for call in _calls(ast.parse(path.read_text())):
            owner = call.func.value
            if not (isinstance(owner, ast.Name) and owner.id == "subprocess"):
                continue
            if call.func.attr == "Popen":
                missing.append(f"{path.name}:{call.lineno} uses Popen, which has no timeout")
            elif call.func.attr in SUBPROCESS_CALLS and "timeout" not in {
                k.arg for k in call.keywords
            }:
                missing.append(f"{path.name}:{call.lineno} subprocess.{call.func.attr}")
    assert not missing, missing


def test_every_urlopen_call_has_a_timeout():
    missing = [
        f"{path.name}:{call.lineno}"
        for path in sorted(PACKAGE.glob("*.py"))
        for call in _calls(ast.parse(path.read_text()))
        if call.func.attr == "urlopen" and "timeout" not in {k.arg for k in call.keywords}
    ]
    assert not missing, missing


def test_every_ingest_tool_call_runs_under_timeout():
    pattern = re.compile(r"(?<![\w$\"'/.-])(" + "|".join(SHELL_TOOLS) + r")\s+(?=[-\"$\w])")
    missing = []
    for script in sorted((PACKAGE / "ingest").glob("*.sh")):
        for number, line in enumerate(script.read_text().splitlines(), 1):
            code = re.sub(r"(^|\s)#.*$", "", line)
            for match in pattern.finditer(code):
                before = code[: match.start()].rstrip()
                if before.endswith('timeout "$TOOL_TIMEOUT"'):
                    continue
                # Prose in echo/printf/err/warn lines and `have x` probes do not start tools.
                if re.match(r"\s*(echo|printf|err|warn|ok|log)\b", code) or before.endswith("have"):
                    continue
                if '"' in before and before.count('"') % 2:
                    continue
                missing.append(f"{script.name}:{number}: {line.strip()}")
    assert not missing, missing
