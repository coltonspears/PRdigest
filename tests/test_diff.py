from prdigest.diff import parse_patch, render_patch_with_comments
from prdigest.models import ReviewComment


SAMPLE_PATCH = """@@ -1,3 +1,4 @@
 first
-second
+second changed
+third inserted
 fourth"""


def test_parse_patch_assigns_line_numbers():
    hunks = parse_patch(SAMPLE_PATCH)
    assert len(hunks) == 1
    lines = hunks[0].lines
    # First context: old=1 new=1
    assert lines[0].kind == " "
    assert (lines[0].old_lineno, lines[0].new_lineno) == (1, 1)
    # Deletion of "second": old=2, no new
    assert lines[1].kind == "-"
    assert lines[1].old_lineno == 2
    assert lines[1].new_lineno is None
    # Addition of "second changed": new=2, no old
    assert lines[2].kind == "+"
    assert lines[2].new_lineno == 2
    # Addition of "third inserted": new=3
    assert lines[3].new_lineno == 3
    # Final context "fourth": old=3 new=4
    assert lines[4].old_lineno == 3
    assert lines[4].new_lineno == 4


def test_render_patch_inlines_comments():
    c = ReviewComment(
        author="alice",
        body="should this be exponential backoff?",
        path="x.py",
        line=3,
        side="RIGHT",
        thread_id="t1",
    )
    out = render_patch_with_comments(SAMPLE_PATCH, [c])
    # The comment lands directly under the "+third inserted" line (new line 3).
    assert "+third inserted" in out
    idx_line = out.index("+third inserted")
    idx_comment = out.index("@alice")
    assert idx_comment > idx_line
    assert "exponential backoff" in out


def test_outdated_comment_falls_to_unanchored():
    c = ReviewComment(
        author="bob",
        body="this used to matter",
        path="x.py",
        line=None,
        side="RIGHT",
        thread_id="t2",
        is_outdated=True,
    )
    out = render_patch_with_comments(SAMPLE_PATCH, [c])
    assert "Unanchored review comments" in out
    assert "@bob" in out
