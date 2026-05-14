"""Dataclasses describing a PR and everything we hang off of it.

The shapes here intentionally do not mirror GitHub's API. They are the minimum
surface the renderer needs, so the GraphQL client can collapse REST/GraphQL
quirks into one stable view.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class PRRef:
    """Canonical identifier for a pull request."""

    owner: str
    repo: str
    number: int

    @property
    def slug(self) -> str:
        return f"{self.owner}/{self.repo}#{self.number}"


@dataclass
class ReviewComment:
    """An inline review comment anchored to a specific line in a diff hunk."""

    author: str
    body: str
    path: str
    # Line in the file *after* the diff is applied (the RIGHT side).
    # None for outdated comments where the line no longer exists.
    line: int | None
    side: Literal["LEFT", "RIGHT"]
    # GitHub groups inline comments into threads; replies share a thread id.
    thread_id: str
    in_reply_to: str | None = None
    is_outdated: bool = False


@dataclass
class IssueComment:
    """A top-level conversation comment on the PR (not anchored to a line)."""

    author: str
    body: str


@dataclass
class FileDiff:
    """One file's patch as returned by GitHub."""

    path: str
    previous_path: str | None
    status: str  # added, modified, removed, renamed
    additions: int
    deletions: int
    patch: str | None  # None when GitHub omits it (binary / oversized)


@dataclass
class CheckRun:
    name: str
    status: str  # queued, in_progress, completed
    conclusion: str | None  # success, failure, neutral, cancelled, skipped, timed_out, action_required, None
    details_url: str | None = None


@dataclass
class ReviewState:
    author: str
    state: str  # APPROVED, CHANGES_REQUESTED, COMMENTED, DISMISSED, PENDING
    body: str = ""


@dataclass
class LinkedIssue:
    number: int
    title: str
    body: str
    state: str  # OPEN, CLOSED


@dataclass
class PullRequest:
    ref: PRRef
    title: str
    author: str
    state: str  # OPEN, CLOSED, MERGED
    is_draft: bool
    body: str
    base_ref: str
    head_ref: str
    head_sha: str
    additions: int
    deletions: int
    changed_files: int
    files: list[FileDiff] = field(default_factory=list)
    review_comments: list[ReviewComment] = field(default_factory=list)
    issue_comments: list[IssueComment] = field(default_factory=list)
    reviews: list[ReviewState] = field(default_factory=list)
    checks: list[CheckRun] = field(default_factory=list)
    linked_issues: list[LinkedIssue] = field(default_factory=list)
