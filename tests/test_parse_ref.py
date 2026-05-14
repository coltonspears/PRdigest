import pytest

from prdigest.github import parse_pr_ref


@pytest.mark.parametrize(
    "raw,owner,repo,num",
    [
        ("https://github.com/octocat/Hello-World/pull/1", "octocat", "Hello-World", 1),
        ("github.com/octocat/Hello-World/pull/42", "octocat", "Hello-World", 42),
        ("octocat/Hello-World#7", "octocat", "Hello-World", 7),
        ("octocat/Hello-World/7", "octocat", "Hello-World", 7),
    ],
)
def test_parse_pr_ref(raw, owner, repo, num):
    ref = parse_pr_ref(raw)
    assert ref.owner == owner
    assert ref.repo == repo
    assert ref.number == num
    assert ref.slug == f"{owner}/{repo}#{num}"


def test_parse_pr_ref_rejects_garbage():
    with pytest.raises(ValueError):
        parse_pr_ref("nope")
