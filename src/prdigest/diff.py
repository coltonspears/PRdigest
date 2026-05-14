"""Unified-diff parser plus review-comment inliner.

GitHub gives us:
  - A unified diff patch per file (REST `files` endpoint).
  - Review comments anchored by `(path, line, side)` where `line` is the
    NEW-file line number on the RIGHT side (or the original line if outdated).

We parse the patch into hunks, then for each comment we find the matching
hunk line and emit a `> @author: …` blockquote underneath it. The result
is still a valid-looking unified diff with annotations interleaved.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from prdigest.models import ReviewComment


HUNK_HEADER_RE = re.compile(
    r"^@@ -(?P<old_start>\d+)(?:,(?P<old_len>\d+))? \+(?P<new_start>\d+)(?:,(?P<new_len>\d+))? @@"
)


@dataclass
class HunkLine:
    kind: str  # " ", "+", "-", "\\"
    text: str
    old_lineno: int | None
    new_lineno: int | None


@dataclass
class Hunk:
    header: str
    lines: list[HunkLine] = field(default_factory=list)


def parse_patch(patch: str) -> list[Hunk]:
    """Parse a unified diff (one file) into hunks with per-line line numbers."""
    hunks: list[Hunk] = []
    current: Hunk | None = None
    old_ln = new_ln = 0

    for raw in patch.splitlines():
        if raw.startswith("@@"):
            m = HUNK_HEADER_RE.match(raw)
            if not m:
                # Malformed header; keep going but treat as plain text.
                continue
            old_ln = int(m["old_start"])
            new_ln = int(m["new_start"])
            current = Hunk(header=raw)
            hunks.append(current)
            continue

        if current is None:
            # Lines before any hunk header are headers like "diff --git";
            # GitHub's per-file patch omits these, but be defensive.
            continue

        if not raw:
            # Blank line inside a hunk = context line that's literally empty.
            current.lines.append(HunkLine(" ", "", old_ln, new_ln))
            old_ln += 1
            new_ln += 1
            continue

        kind = raw[0]
        text = raw[1:]
        if kind == "+":
            current.lines.append(HunkLine("+", text, None, new_ln))
            new_ln += 1
        elif kind == "-":
            current.lines.append(HunkLine("-", text, old_ln, None))
            old_ln += 1
        elif kind == "\\":
            # "\ No newline at end of file" — no line numbers move.
            current.lines.append(HunkLine("\\", text, None, None))
        else:
            # context line (leading space, but also tolerate weird patches)
            current.lines.append(HunkLine(" ", text, old_ln, new_ln))
            old_ln += 1
            new_ln += 1

    return hunks


def render_patch_with_comments(
    patch: str,
    comments: list[ReviewComment],
) -> str:
    """Re-emit `patch`, threading review comments below their target lines.

    Comments whose line we can't locate (outdated, file-level, or weird
    targets) are appended at the end as a "## Unanchored comments" block so
    we never silently drop content.
    """
    if not patch:
        return ""

    hunks = parse_patch(patch)

    # Group comments by their RIGHT-side new line number. Replies follow their
    # parent in GitHub's order; preserve that.
    by_line: dict[int, list[ReviewComment]] = {}
    unanchored: list[ReviewComment] = []
    for c in comments:
        if c.line is None or c.is_outdated:
            unanchored.append(c)
            continue
        by_line.setdefault(c.line, []).append(c)

    out: list[str] = []
    placed: set[int] = set()
    for hunk in hunks:
        out.append(hunk.header)
        for ln in hunk.lines:
            sigil = ln.kind if ln.kind != " " else " "
            out.append(f"{sigil}{ln.text}")
            target_ln = ln.new_lineno
            if target_ln is not None and target_ln in by_line and target_ln not in placed:
                placed.add(target_ln)
                for c in by_line[target_ln]:
                    out.extend(_format_comment(c))

    # Anything we never placed (e.g. comment line falls outside any hunk we
    # have a patch for — happens for huge files where GitHub elides patches)
    # goes to the unanchored bucket.
    for ln, cs in by_line.items():
        if ln not in placed:
            unanchored.extend(cs)

    if unanchored:
        out.append("")
        out.append("> _Unanchored review comments (outdated or off-patch):_")
        for c in unanchored:
            out.extend(_format_comment(c, prefix="> "))

    return "\n".join(out)


def _format_comment(c: ReviewComment, prefix: str = "") -> list[str]:
    header = f"{prefix}> **@{c.author}**"
    if c.in_reply_to:
        header += " _(reply)_"
    if c.is_outdated:
        header += " _(outdated)_"
    body_lines = [f"{prefix}> {line}" for line in c.body.splitlines() or [""]]
    return [header, *body_lines, prefix.rstrip() or ""]
