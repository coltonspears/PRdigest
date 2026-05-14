from prdigest.models import (
    CheckRun,
    FileDiff,
    LinkedIssue,
    PullRequest,
    PRRef,
    ReviewComment,
    ReviewState,
)
from prdigest.render import render_markdown


def _pr() -> PullRequest:
    return PullRequest(
        ref=PRRef("octocat", "hello", 7),
        title="Add retry logic",
        author="alice",
        state="OPEN",
        is_draft=False,
        body="Closes #1.",
        base_ref="main",
        head_ref="alice/retry",
        head_sha="abcdef1234567890abcdef1234567890abcdef12",
        additions=12,
        deletions=3,
        changed_files=1,
        files=[
            FileDiff(
                path="src/handler.py",
                previous_path=None,
                status="modified",
                additions=12,
                deletions=3,
                patch="@@ -1,2 +1,3 @@\n a\n-b\n+b changed\n+c new",
            )
        ],
        review_comments=[
            ReviewComment(
                author="bob",
                body="nit: rename",
                path="src/handler.py",
                line=2,
                side="RIGHT",
                thread_id="t",
            )
        ],
        reviews=[ReviewState(author="bob", state="CHANGES_REQUESTED", body="see comments")],
        checks=[
            CheckRun(name="lint", status="completed", conclusion="success"),
            CheckRun(name="test", status="completed", conclusion="failure"),
        ],
        linked_issues=[LinkedIssue(number=1, title="Webhooks fail", body="silently", state="OPEN")],
    )


def test_render_markdown_contains_all_sections():
    md = render_markdown(_pr())
    assert "# PR #7: Add retry logic" in md
    assert "## Description" in md
    assert "Closes #1." in md
    assert "## Linked issues" in md
    assert "## Review state" in md
    assert "requested changes" in md
    assert "## Diff (annotated)" in md
    assert "src/handler.py" in md
    assert "@bob" in md
    assert "## CI checks" in md
    assert "[OK]" in md
    assert "[FAIL]" in md


def test_render_markdown_handles_empty_description():
    pr = _pr()
    pr.body = ""
    md = render_markdown(pr)
    assert "_(no description provided)_" in md


def test_render_markdown_handles_binary_files():
    pr = _pr()
    pr.files[0].patch = None
    md = render_markdown(pr)
    assert "Patch omitted by GitHub" in md
