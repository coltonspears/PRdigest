"""Library-facing entry point.

`build_digest(ref, token=None)` is the one function the CLI, the web app,
and any third party will call.
"""

from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # python-dotenv is optional
    load_dotenv = None  # type: ignore[assignment]

from prdigest.github import GitHubClient, parse_pr_ref
from prdigest.models import PRRef, PullRequest
from prdigest.render import render_markdown


_DOTENV_LOADED = False


def _ensure_dotenv() -> None:
    """Load .env from CWD on first call. Existing env vars take precedence."""
    global _DOTENV_LOADED
    if _DOTENV_LOADED or load_dotenv is None:
        return
    env_path = Path.cwd() / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=False)
    _DOTENV_LOADED = True


async def build_digest(
    ref: str | PRRef,
    *,
    token: str | None = None,
) -> str:
    """Fetch a PR and return its markdown digest.

    `ref` accepts a github.com URL or `owner/repo#123` / `owner/repo/123`.
    `token` falls back to the GITHUB_TOKEN env var; pass an empty string
    to force anonymous mode even when the env var is set.
    """
    if isinstance(ref, str):
        pr_ref = parse_pr_ref(ref)
    else:
        pr_ref = ref

    if token is None:
        _ensure_dotenv()
        token = os.environ.get("GITHUB_TOKEN")
    if token == "":
        token = None

    async with GitHubClient(token=token) as client:
        pr: PullRequest = await client.fetch_pr(pr_ref)
    return render_markdown(pr)
