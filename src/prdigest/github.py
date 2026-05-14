"""GitHub API client.

We use GraphQL for everything we can (single round trip for PR metadata,
review threads, reviews, linked issues, checks) and the REST `files`
endpoint for patches — GraphQL doesn't expose the unified diff text, and
the REST endpoint paginates cleanly.
"""

from __future__ import annotations

import re
from typing import Any

import httpx

from prdigest.models import (
    CheckRun,
    FileDiff,
    IssueComment,
    LinkedIssue,
    PullRequest,
    PRRef,
    ReviewComment,
    ReviewState,
)

GITHUB_API = "https://api.github.com"
GITHUB_GRAPHQL = "https://api.github.com/graphql"

PR_URL_RE = re.compile(
    r"(?:https?://)?(?:www\.)?github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)/pull/(?P<num>\d+)"
)
SLUG_RE = re.compile(r"(?P<owner>[^/]+)/(?P<repo>[^/#]+)[#/](?P<num>\d+)")


class GitHubError(RuntimeError):
    pass


def parse_pr_ref(s: str) -> PRRef:
    """Accept either a github.com URL or owner/repo#123 / owner/repo/123."""
    s = s.strip()
    m = PR_URL_RE.search(s) or SLUG_RE.fullmatch(s)
    if not m:
        raise ValueError(f"Could not parse PR reference: {s!r}")
    return PRRef(owner=m["owner"], repo=m["repo"], number=int(m["num"]))


# GraphQL query — one round trip for everything except patches.
# Notes on caps:
#   - first: 100 is GitHub's connection max; for v0 we accept that as the
#     ceiling and surface a warning in the renderer if we hit it.
PR_QUERY = """
query($owner: String!, $repo: String!, $number: Int!) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $number) {
      title
      body
      state
      isDraft
      author { login }
      baseRefName
      headRefName
      headRefOid
      additions
      deletions
      changedFiles
      reviewThreads(first: 100) {
        nodes {
          id
          isOutdated
          comments(first: 50) {
            nodes {
              author { login }
              body
              path
              line
              originalLine
              diffHunk
              replyTo { id }
            }
          }
        }
      }
      comments(first: 100) {
        nodes { author { login } body }
      }
      reviews(first: 50) {
        nodes { author { login } state body }
      }
      closingIssuesReferences(first: 20) {
        nodes { number title body state }
      }
      commits(last: 1) {
        nodes {
          commit {
            statusCheckRollup {
              contexts(first: 50) {
                nodes {
                  __typename
                  ... on CheckRun {
                    name
                    status
                    conclusion
                    detailsUrl
                  }
                  ... on StatusContext {
                    context
                    state
                    targetUrl
                  }
                }
              }
            }
          }
        }
      }
    }
  }
}
"""


class GitHubClient:
    def __init__(self, token: str | None = None, timeout: float = 30.0):
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "prdigest/0.1",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._client = httpx.AsyncClient(headers=headers, timeout=timeout)
        self._token = token

    async def __aenter__(self) -> "GitHubClient":
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self._client.aclose()

    async def fetch_pr(self, ref: PRRef) -> PullRequest:
        meta = await self._graphql(ref)
        files = await self._fetch_files(ref)
        pr = self._build_pull_request(ref, meta, files)
        return pr

    async def _graphql(self, ref: PRRef) -> dict[str, Any]:
        resp = await self._client.post(
            GITHUB_GRAPHQL,
            json={
                "query": PR_QUERY,
                "variables": {
                    "owner": ref.owner,
                    "repo": ref.repo,
                    "number": ref.number,
                },
            },
        )
        if resp.status_code == 401:
            raise GitHubError("GitHub rejected the request (401). Token invalid or missing scopes.")
        if resp.status_code == 403:
            raise GitHubError(
                "GitHub rate-limited or blocked the request (403). "
                "Set GITHUB_TOKEN to lift the 60/hr anonymous limit."
            )
        resp.raise_for_status()
        payload = resp.json()
        if "errors" in payload:
            raise GitHubError(f"GraphQL error: {payload['errors']}")
        pr = payload["data"]["repository"]["pullRequest"] if payload["data"].get("repository") else None
        if pr is None:
            raise GitHubError(f"PR {ref.slug} not found, or repo is private.")
        return pr

    async def _fetch_files(self, ref: PRRef) -> list[dict[str, Any]]:
        files: list[dict[str, Any]] = []
        page = 1
        while True:
            resp = await self._client.get(
                f"{GITHUB_API}/repos/{ref.owner}/{ref.repo}/pulls/{ref.number}/files",
                params={"per_page": 100, "page": page},
            )
            resp.raise_for_status()
            batch = resp.json()
            files.extend(batch)
            if len(batch) < 100:
                break
            page += 1
            if page > 30:  # 3000-file safety stop
                break
        return files

    def _build_pull_request(
        self,
        ref: PRRef,
        meta: dict[str, Any],
        raw_files: list[dict[str, Any]],
    ) -> PullRequest:
        file_diffs = [
            FileDiff(
                path=f["filename"],
                previous_path=f.get("previous_filename"),
                status=f["status"],
                additions=f["additions"],
                deletions=f["deletions"],
                patch=f.get("patch"),
            )
            for f in raw_files
        ]

        review_comments: list[ReviewComment] = []
        for thread in meta["reviewThreads"]["nodes"]:
            thread_id = thread["id"]
            outdated = bool(thread["isOutdated"])
            for c in thread["comments"]["nodes"]:
                review_comments.append(
                    ReviewComment(
                        author=_login(c.get("author")),
                        body=c["body"],
                        path=c["path"],
                        line=c.get("line") if not outdated else c.get("originalLine"),
                        side="RIGHT",
                        thread_id=thread_id,
                        in_reply_to=(c.get("replyTo") or {}).get("id"),
                        is_outdated=outdated,
                    )
                )

        issue_comments = [
            IssueComment(author=_login(c.get("author")), body=c["body"])
            for c in meta["comments"]["nodes"]
        ]

        reviews = [
            ReviewState(
                author=_login(r.get("author")),
                state=r["state"],
                body=r.get("body") or "",
            )
            for r in meta["reviews"]["nodes"]
        ]

        linked = [
            LinkedIssue(
                number=i["number"],
                title=i["title"],
                body=i.get("body") or "",
                state=i["state"],
            )
            for i in meta["closingIssuesReferences"]["nodes"]
        ]

        checks: list[CheckRun] = []
        commits = meta["commits"]["nodes"]
        if commits:
            rollup = commits[0]["commit"].get("statusCheckRollup")
            if rollup:
                for ctx in rollup["contexts"]["nodes"]:
                    if ctx["__typename"] == "CheckRun":
                        checks.append(
                            CheckRun(
                                name=ctx["name"],
                                status=ctx["status"].lower(),
                                conclusion=(ctx.get("conclusion") or "").lower() or None,
                                details_url=ctx.get("detailsUrl"),
                            )
                        )
                    elif ctx["__typename"] == "StatusContext":
                        # Legacy commit statuses (Travis-era).
                        state = ctx.get("state", "").lower()
                        checks.append(
                            CheckRun(
                                name=ctx.get("context", "status"),
                                status="completed",
                                conclusion=state or None,
                                details_url=ctx.get("targetUrl"),
                            )
                        )

        return PullRequest(
            ref=ref,
            title=meta["title"],
            author=_login(meta.get("author")),
            state=meta["state"],
            is_draft=bool(meta.get("isDraft")),
            body=meta.get("body") or "",
            base_ref=meta["baseRefName"],
            head_ref=meta["headRefName"],
            head_sha=meta["headRefOid"],
            additions=meta["additions"],
            deletions=meta["deletions"],
            changed_files=meta["changedFiles"],
            files=file_diffs,
            review_comments=review_comments,
            issue_comments=issue_comments,
            reviews=reviews,
            checks=checks,
            linked_issues=linked,
        )


def _login(actor: dict[str, Any] | None) -> str:
    if not actor:
        return "ghost"
    return actor.get("login") or "ghost"
