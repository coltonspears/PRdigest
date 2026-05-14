# prdigest

Render any GitHub pull request as a single, LLM-ready markdown document.

Replace `github.com` with your prdigest host on any PR URL — get the PR description, linked issues, the full diff with review comments threaded inline next to the lines they target, review state, and CI results. No AI summarization. Lossless.

![prdigest landing page](docs/screenshot.png)

## Install

```pwsh
uv sync --extra dev
```

## Use

**CLI:**

```pwsh
uv run prdigest octocat/Hello-World#1
uv run prdigest https://github.com/octocat/Hello-World/pull/1 -o digest.md
```

**Web app:**

```pwsh
uv run uvicorn prdigest.web.app:app --reload
```

Then visit `http://localhost:8000/octocat/Hello-World/pull/1`.

**Library:**

```python
import asyncio
from prdigest import build_digest

md = asyncio.run(build_digest("octocat/Hello-World#1"))
```

## Auth

Public PRs work without a token (60 req/hr anonymous limit). For private PRs or higher rate limits, set `GITHUB_TOKEN`:

```pwsh
$env:GITHUB_TOKEN = "ghp_..."
```

## Layout

- `src/prdigest/core.py` — `build_digest()` entry point
- `src/prdigest/github.py` — GraphQL + REST client
- `src/prdigest/diff.py` — patch parser + review-comment inliner
- `src/prdigest/render.py` — markdown assembly
- `src/prdigest/cli.py` — Typer CLI
- `src/prdigest/web/` — FastAPI app + Jinja templates

## Tests

```pwsh
uv run pytest -q
```
