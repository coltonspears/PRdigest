"""`prdigest` CLI — thin wrapper around `build_digest`."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import typer

from prdigest.core import build_digest
from prdigest.github import GitHubError

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Render a GitHub pull request as a single LLM-ready markdown digest.",
)


@app.command()
def digest(
    ref: str = typer.Argument(
        ...,
        help="PR reference: github.com URL, or 'owner/repo#123' / 'owner/repo/123'.",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Write to this file instead of stdout.",
    ),
    token: str | None = typer.Option(
        None,
        "--token",
        envvar="GITHUB_TOKEN",
        help="GitHub token. Falls back to GITHUB_TOKEN env var. Optional for public PRs.",
    ),
) -> None:
    """Render the PR to markdown."""
    try:
        markdown = asyncio.run(build_digest(ref, token=token))
    except GitHubError as e:
        typer.secho(f"error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    except ValueError as e:
        typer.secho(f"error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(2)

    if output is None:
        sys.stdout.write(markdown)
    else:
        output.write_text(markdown, encoding="utf-8")
        typer.secho(f"wrote {len(markdown):,} chars to {output}", fg=typer.colors.GREEN, err=True)


if __name__ == "__main__":
    app()
