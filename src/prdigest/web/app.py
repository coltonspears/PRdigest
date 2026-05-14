"""FastAPI app — the URL-swap surface.

Route shape mirrors GitHub's PR URLs so users can replace `github.com`
with `prdigest.com` (or wherever this is hosted) and land here.

Routes
------
- GET  /                                 → landing page
- GET  /{owner}/{repo}/pull/{number}     → HTML digest page
- GET  /api/digest/{owner}/{repo}/{n}    → raw markdown (text/markdown)
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from prdigest.core import build_digest
from prdigest.github import GitHubError, parse_pr_ref
from prdigest.models import PRRef

TEMPLATES_DIR = Path(__file__).parent / "templates"

app = FastAPI(
    title="prdigest",
    description="Render a GitHub pull request as one LLM-ready markdown document.",
    version="0.1.0",
)

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@app.get("/", include_in_schema=False)
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.get("/go", include_in_schema=False)
async def go(url: str):
    """Form target on the landing page — parse pasted URL and redirect."""
    try:
        ref = parse_pr_ref(url)
    except ValueError:
        return RedirectResponse(url="/", status_code=303)
    return RedirectResponse(
        url=f"/{ref.owner}/{ref.repo}/pull/{ref.number}", status_code=303
    )


@app.get("/api/digest/{owner}/{repo}/{number}", response_class=PlainTextResponse)
async def api_digest(owner: str, repo: str, number: int) -> str:
    try:
        md = await build_digest(PRRef(owner=owner, repo=repo, number=number))
    except GitHubError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return md


@app.get("/{owner}/{repo}/pull/{number}", include_in_schema=False)
async def digest_page(request: Request, owner: str, repo: str, number: int):
    try:
        md = await build_digest(PRRef(owner=owner, repo=repo, number=number))
        error = None
    except GitHubError as e:
        md = ""
        error = str(e)
    return templates.TemplateResponse(
        request,
        "digest.html",
        {
            "owner": owner,
            "repo": repo,
            "number": number,
            "markdown": md,
            "error": error,
        },
    )
