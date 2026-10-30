# Contributing

1. Install for development: `uv venv && uv pip install -e . pytest ruff 'hatchling>=1.25,<2'`.
   hal-kit and hal-hub must be installed too (see `docs/dev/testing.md`).
2. Make one logical change per commit, with its tests and doc updates.
3. Run the checks before each commit:

   ```bash
   .venv/bin/python -m pytest -q        # tests
   ruff check . && ruff format --check .   # lint and format
   scripts/ascii-check.sh               # ASCII only
   ```

4. Commit subjects follow the repo history: `Add X`, `Fix X`, one line, no body.
5. Add user-visible changes to `CHANGELOG.md`.

Do not commit secrets, `.env` files, build output or caches.
