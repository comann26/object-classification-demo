# Commands

- `bin/uv.exe lock` — resolve dependencies
- `bin/uv.exe sync` — install dependencies into `.venv`
- `bin/uv.exe run pytest tests/unit -v` — run unit tests
- `bin/uv.exe run python scripts/export_schemas.py` — regenerate `schemas/*.json`
- `bin/uv.exe run python scripts/export_schemas.py --check` — fail if the schemas have drifted
- `bin/uv.exe run ruff check .` — lint
