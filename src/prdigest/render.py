"""Top-level markdown assembly: PR → one big markdown document."""

from __future__ import annotations

from prdigest.diff import render_patch_with_comments
from prdigest.models import PullRequest, ReviewComment


_CHECK_ICON = {
    "success": "[OK]",
    "failure": "[FAIL]",
    "neutral": "[--]",
    "cancelled": "[--]",
    "skipped": "[--]",
    "timed_out": "[FAIL]",
    "action_required": "[!]",
    None: "[..]",
}


def render_markdown(pr: PullRequest) -> str:
    """Render the full digest. Pure function over a populated PullRequest."""
    parts: list[str] = []
    parts.append(_header(pr))
    parts.append(_description(pr))
    if pr.linked_issues:
        parts.append(_linked_issues(pr))
    if pr.reviews or pr.review_comments:
        parts.append(_review_summary(pr))
    if pr.issue_comments:
        parts.append(_conversation(pr))
    parts.append(_diff(pr))
    if pr.checks:
        parts.append(_checks(pr))
    return "\n\n".join(p for p in parts if p).rstrip() + "\n"


def _header(pr: PullRequest) -> str:
    status = "Merged" if pr.state == "MERGED" else ("Draft" if pr.is_draft else pr.state.title())
    return (
        f"# PR #{pr.ref.number}: {pr.title}\n"
        f"**Repo:** {pr.ref.owner}/{pr.ref.repo}  \n"
        f"**Author:** @{pr.author}  \n"
        f"**Status:** {status}  \n"
        f"**Branch:** `{pr.head_ref}` → `{pr.base_ref}`  \n"
        f"**Changes:** +{pr.additions} / -{pr.deletions} across {pr.changed_files} file(s)  \n"
        f"**Head SHA:** `{pr.head_sha[:12]}`"
    )


def _description(pr: PullRequest) -> str:
    body = pr.body.strip() or "_(no description provided)_"
    return f"## Description\n\n{body}"


def _linked_issues(pr: PullRequest) -> str:
    lines = ["## Linked issues", ""]
    for i in pr.linked_issues:
        lines.append(f"### #{i.number} — {i.title} _({i.state.lower()})_")
        lines.append("")
        lines.append((i.body.strip() or "_(no body)_"))
        lines.append("")
    return "\n".join(lines).rstrip()


def _review_summary(pr: PullRequest) -> str:
    if not pr.reviews:
        return ""
    lines = ["## Review state", ""]
    for r in pr.reviews:
        verb = {
            "APPROVED": "approved",
            "CHANGES_REQUESTED": "requested changes",
            "COMMENTED": "commented",
            "DISMISSED": "dismissed",
            "PENDING": "pending",
        }.get(r.state, r.state.lower())
        lines.append(f"- **@{r.author}**: {verb}")
        if r.body.strip():
            for bl in r.body.strip().splitlines():
                lines.append(f"  > {bl}")
    return "\n".join(lines)


def _conversation(pr: PullRequest) -> str:
    lines = ["## Conversation", ""]
    for c in pr.issue_comments:
        lines.append(f"**@{c.author}:**")
        lines.append("")
        for bl in (c.body.strip() or "_(empty)_").splitlines():
            lines.append(f"> {bl}")
        lines.append("")
    return "\n".join(lines).rstrip()


def _diff(pr: PullRequest) -> str:
    if not pr.files:
        return "## Diff\n\n_(no file changes)_"

    comments_by_path: dict[str, list[ReviewComment]] = {}
    for c in pr.review_comments:
        comments_by_path.setdefault(c.path, []).append(c)

    out = ["## Diff (annotated)", ""]
    for f in pr.files:
        renamed = f" (renamed from `{f.previous_path}`)" if f.previous_path else ""
        out.append(f"### `{f.path}` — {f.status}{renamed} (+{f.additions} / -{f.deletions})")
        out.append("")
        if f.patch is None:
            out.append("_Patch omitted by GitHub (binary or oversized file)._")
            out.append("")
            continue
        annotated = render_patch_with_comments(f.patch, comments_by_path.get(f.path, []))
        out.append("```diff")
        out.append(annotated)
        out.append("```")
        out.append("")
    return "\n".join(out).rstrip()


def _checks(pr: PullRequest) -> str:
    lines = ["## CI checks", ""]
    for c in pr.checks:
        icon = _CHECK_ICON.get(c.conclusion, "[..]")
        suffix = ""
        if c.status != "completed":
            suffix = f" _({c.status})_"
        lines.append(f"- {icon} **{c.name}**{suffix}")
    return "\n".join(lines)
