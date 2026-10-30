# Testing

```bash
uv venv && uv pip install pytest ruff 'hatchling>=1.25,<2' -e .   # the tests need hal-kit and hal-hub
.venv/bin/python -m pytest -q          # fast, hermetic: no network, no GPU, no real models
.venv/bin/python -m pytest -q -m slow  # builds a wheel
ruff check . && ruff format --check .
scripts/ascii-check.sh                 # no non-ASCII in tracked files
```

- Tests use throwaway `HOME`, `HAL_CONFIG`, `HAL_DATA_DIR` and `HAL_STATE_DIR`, and a fake model.
- `tests/test_mcp.py` starts `python -m halmem mcp` and lists the tools over stdio.
- `tests/test_skills.py` checks the skill format and the installer against a temp home.
- CI runs ruff, the ASCII gate, the tests on Python 3.11 to 3.13, and gitleaks.
