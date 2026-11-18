"""gh-issue skill の issues.py を、gh と git の呼び出しを作り物に差し替えて確かめる。

ネットワークにも GitHub にも触れない。期待する値は、SKILL.md の「着手中か確かめる」「優先度と難易度」
「作者の信頼」「書き込み先」「手放す・済ませる」の記述から決める。
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

ISSUES_PY = Path(__file__).resolve().parents[1] / "ansible/roles/claude/files/skills/gh-issue/scripts/issues.py"
WORK = "o/work"
TRACKER = "o/tracker"
# SKILL.md の「着手する」「優先度と難易度」にあるラベルを、issues.py の定数に頼らずに並べる。
ALL_LABELS = [
    "agent:doing",
    "agent:skip",
    "priority:high",
    "priority:medium",
    "priority:low",
    "difficulty:expert",
    "difficulty:hard",
    "difficulty:medium",
    "difficulty:easy",
]


def load_issues():
    # scripts/ は丸ごと ~/.claude/skills/ へコピーされるので、読み込みで __pycache__ を作ると配布先にも入る。
    spec = importlib.util.spec_from_file_location("gh_issue_issues", ISSUES_PY)
    module = importlib.util.module_from_spec(spec)
    saved = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = saved
    return module


issues = load_issues()


def at(minute):
    return f"2026-01-01T00:{minute:02d}:00Z"


def day(n):
    return f"2026-01-{n:02d}T00:00:00Z"


def comment(body, minute, *, association="OWNER", login="owner", typename="User"):
    return {
        "author": {"__typename": typename, "login": login},
        "authorAssociation": association,
        "createdAt": at(minute),
        "body": body,
    }


def claim(branch, minute, session=None, **author):
    line = f"着手: ブランチ `{branch}`" + (f" セッション `{session}`" if session else "")
    return comment(f"{line}\n範囲と閉じ方", minute, **author)


def release(branch, minute, session=None, kind="手放し", **author):
    line = f"{kind}: ブランチ `{branch}`" + (f" セッション `{session}`" if session else "")
    return comment(f"{line}\nどこまで済んだか", minute, **author)


def unlabeled(minute, label="agent:doing"):
    return {"createdAt": at(minute), "label": {"name": label}}


def pr(number, *, state="OPEN", association="OWNER", typename="User", repo=WORK):
    return {
        "number": number,
        "state": state,
        "author": {"__typename": typename},
        "authorAssociation": association,
        "repository": {"nameWithOwner": repo},
    }


def blocker(number, *, state="OPEN", repo=WORK):
    return {"number": number, "state": state, "repository": {"nameWithOwner": repo}}


def issue(
    number=1,
    *,
    state="OPEN",
    created=None,
    title="タイトル",
    body="本文",
    author="owner",
    typename="User",
    association="OWNER",
    labels=(),
    branches=(),
    closing_prs=(),
    referencing_prs=(),
    unlabeled_events=(),
    blocked_by=(),
    sub_issues=(0, 0),
    comments=(),
):
    """GraphQL が返す Issue のノード。コメントは全件を持ち、FakeGitHub が要求の件数に切る。"""
    return {
        "number": number,
        "title": title,
        "state": state,
        "stateReason": None if state == "OPEN" else "COMPLETED",
        "body": body,
        "createdAt": created or at(0),
        "updatedAt": at(59),
        "author": {"__typename": typename, "login": author},
        "authorAssociation": association,
        "labels": {"nodes": [{"name": name} for name in labels]},
        "linkedBranches": {"nodes": [{"ref": {"name": name}} for name in branches]},
        "closedByPullRequestsReferences": {"nodes": list(closing_prs)},
        "timelineItems": {"nodes": [{"source": {"__typename": "PullRequest", **p}} for p in referencing_prs]},
        "unlabeled": {"nodes": list(unlabeled_events)},
        "blockedBy": {"nodes": list(blocked_by)},
        "parent": None,
        "subIssuesSummary": {"total": sub_issues[0], "completed": sub_issues[1]},
        "comments": {"totalCount": len(comments), "nodes": list(comments)},
    }


def last_comments(node, count):
    connection = node["comments"]
    return {**node, "comments": {"totalCount": connection["totalCount"], "nodes": connection["nodes"][-count:]}}


def completed(args, returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(args, returncode, stdout, stderr)


class FakeGitHub:
    """issues.run の代わりに呼ばれ、gh と git に作り物の出力を返す。知らない呼び出しは AssertionError で落とす。

    GraphQL の要求は variables で見分ける（number は view、first は backlog、ほかは repo）。backlog の Issue は
    足した順に返す。
    """

    def __init__(self):
        self.work = WORK
        # None はキーが無い（git config が exit 1）。int はその終了コードで git config が失敗する。
        self.tracker_config = None
        self.repos = {}
        self.failures = {}
        self.calls = []
        self.queries = []
        self.add_repo(WORK)

    def add_repo(self, name, *, visibility="PRIVATE", labels=ALL_LABELS, default_branch="master"):
        self.repos[name] = {
            "visibility": visibility,
            "labels": set(labels),
            "default_branch": default_branch,
            "issues": {},
        }

    def add_issue(self, node, repo=WORK):
        self.repos[repo]["issues"][node["number"]] = node

    def fail(self, repo, kind, *, returncode=0, stdout="", stderr=""):
        self.failures[(repo, kind)] = (returncode, stdout, stderr)

    def backlog_queries(self, repo):
        return [variables for kind, name, variables in self.queries if kind == "backlog" and name == repo]

    def __call__(self, args, stdin=None):
        self.calls.append(list(args))
        if args[:3] == ["gh", "api", "graphql"]:
            return self.graphql(args, json.loads(stdin))
        if args[:3] == ["gh", "repo", "view"]:
            if self.work is None:
                return completed(args, 1, stderr="no git remotes found")
            return completed(args, stdout=self.work + "\n")
        if args == ["git", "config", "--local", "--get", "gh-issue.tracker"]:
            if self.tracker_config is None:
                return completed(args, 1)
            if isinstance(self.tracker_config, int):
                return completed(args, self.tracker_config, stderr="fatal: bad config")
            return completed(args, stdout=self.tracker_config + "\n")
        raise AssertionError(f"想定していない呼び出し: {args}")

    def graphql(self, args, request):
        variables = request["variables"]
        name = f"{variables['owner']}/{variables['name']}"
        kind = "view" if "number" in variables else "backlog" if "first" in variables else "repo"
        self.queries.append((kind, name, variables))
        if (name, kind) in self.failures:
            return completed(args, *self.failures[(name, kind)])
        repo = self.repos.get(name)
        if repo is None:
            return self.respond(args, None, f"Could not resolve to a Repository with the name '{name}'.")
        if kind == "repo":
            data = {
                "nameWithOwner": name,
                "visibility": repo["visibility"],
                "defaultBranchRef": {"name": repo["default_branch"]},
            }
            for key, label in variables.items():
                if re.fullmatch(r"l\d+", key):
                    data[key] = {"name": label} if label in repo["labels"] else None
            return self.respond(args, data)
        if kind == "backlog":
            wanted = variables["labels"] or []
            matched = [
                node
                for node in repo["issues"].values()
                if node["state"] == "OPEN" and all({"name": label} in node["labels"]["nodes"] for label in wanted)
            ]
            page = [last_comments(node, 20) for node in matched[: variables["first"]]]
            return self.respond(args, {"issues": {"totalCount": len(matched), "nodes": page}})
        node = repo["issues"].get(variables["number"])
        if node is None:
            return self.respond(args, {"issue": None}, "Could not resolve to an issue or pull request.")
        return self.respond(args, {"issue": last_comments(node, variables["comments"])})

    @staticmethod
    def respond(args, repository, error=None):
        payload = {"data": {"repository": repository}}
        if error:
            payload["errors"] = [{"type": "NOT_FOUND", "message": error}]
        return completed(args, stdout=json.dumps(payload))


class IssuesTestCase(unittest.TestCase):
    def setUp(self):
        self.gh = FakeGitHub()
        patcher = mock.patch.object(issues, "run", self.gh)
        patcher.start()
        self.addCleanup(patcher.stop)
        # 差し替えを外れた呼び出しが、本物の gh や git に届かないようにする。
        guard = mock.patch.object(issues.subprocess, "run", side_effect=AssertionError("subprocess.run が呼ばれた"))
        guard.start()
        self.addCleanup(guard.stop)

    def call(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = issues.main(list(argv))
            except SystemExit as e:
                code = e.code
        return code, out.getvalue(), err.getvalue()

    def output(self, *argv):
        code, out, err = self.call(*argv)
        self.assertEqual(code, 0, err)
        return json.loads(out)

    def view(self, node, *argv):
        self.gh.add_issue(node)
        return self.output("view", str(node["number"]), "--repo", WORK, *argv)

    def claims(self, comments, unlabeled_events=()):
        return self.view(issue(labels=["agent:doing"], comments=comments, unlabeled_events=unlabeled_events))


class StatusTest(IssuesTestCase):
    def test_status_follows_precedence(self):
        # 上の行の条件があれば、下の行の条件が揃っていても上の status になる。
        expected = [
            ("closed", ["state が CLOSED"]),
            ("skip", ["ラベル agent:skip"]),
            ("doing", ["ラベル agent:doing"]),
            ("blocked", [f"開いている {WORK}#3 に blocked-by"]),
            ("umbrella", ["sub-issue が 1 件開いている"]),
            ("external", ["作者 stranger の authorAssociation が NONE"]),
            ("ready", []),
        ]
        for i, (status, reasons) in enumerate(expected):
            active = {name for name, _ in expected[i:]}
            node = issue(
                state="CLOSED" if "closed" in active else "OPEN",
                labels=[label for key, label in (("skip", "agent:skip"), ("doing", "agent:doing")) if key in active],
                blocked_by=[blocker(3)] if "blocked" in active else [],
                sub_issues=(2, 1) if "umbrella" in active else (0, 0),
                author="stranger",
                association="NONE" if "external" in active else "OWNER",
            )
            with self.subTest(status=status):
                result = self.view(node)
                self.assertEqual((result["status"], result["reasons"]), (status, reasons))

    def test_doing_lists_label_trusted_prs_and_branches(self):
        node = issue(labels=["agent:doing"], branches=["feat/a"], closing_prs=[pr(5)], referencing_prs=[pr(6)])
        result = self.view(node)
        self.assertEqual(result["status"], "doing")
        self.assertEqual(
            result["reasons"],
            ["ラベル agent:doing", f"開いている PR {WORK}#5", f"開いている PR {WORK}#6", "紐付いたブランチ feat/a"],
        )
        self.assertEqual(
            result["open_prs"], [{"ref": f"{WORK}#5", "closes": True}, {"ref": f"{WORK}#6", "closes": False}]
        )
        self.assertEqual(result["linked_branches"], ["feat/a"])

    def test_each_doing_signal_alone_makes_doing(self):
        cases = {
            "ラベル": issue(labels=["agent:doing"]),
            "閉じる PR": issue(closing_prs=[pr(5)]),
            "参照する PR": issue(referencing_prs=[pr(6, association="MEMBER")]),
            "bot の PR": issue(referencing_prs=[pr(7, association="NONE", typename="Bot")]),
            "紐付いたブランチ": issue(branches=["feat/a"]),
        }
        for name, node in cases.items():
            with self.subTest(name):
                self.assertEqual(self.view(node)["status"], "doing")

    def test_untrusted_prs_go_to_other_prs(self):
        node = issue(closing_prs=[pr(9, association="CONTRIBUTOR")], referencing_prs=[pr(8, association="NONE")])
        result = self.view(node)
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["open_prs"], [])
        self.assertCountEqual(result["other_prs"], [f"{WORK}#8", f"{WORK}#9"])

    def test_closed_prs_and_closed_blockers_do_not_count(self):
        node = issue(
            closing_prs=[pr(5, state="CLOSED")],
            referencing_prs=[pr(6, state="MERGED")],
            blocked_by=[blocker(3, state="CLOSED")],
        )
        result = self.view(node)
        self.assertEqual((result["status"], result["open_prs"], result["blocked_by"]), ("ready", [], []))

    def test_pr_that_closes_and_references_is_listed_once(self):
        node = issue(closing_prs=[pr(5)], referencing_prs=[pr(5)])
        self.assertEqual(self.view(node)["open_prs"], [{"ref": f"{WORK}#5", "closes": True}])

    def test_completed_sub_issues_are_not_umbrella(self):
        result = self.view(issue(sub_issues=(3, 3)))
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["sub_issues"], {"total": 3, "completed": 3})


class TrustTest(IssuesTestCase):
    def test_owner_member_collaborator_are_trusted(self):
        for association in ("OWNER", "MEMBER", "COLLABORATOR"):
            with self.subTest(association):
                result = self.view(issue(association=association))
                self.assertEqual((result["trusted"], result["status"]), (True, "ready"))

    def test_other_authors_are_external(self):
        for association in ("CONTRIBUTOR", "FIRST_TIME_CONTRIBUTOR", "FIRST_TIMER", "MANNEQUIN", "NONE", None):
            with self.subTest(association):
                result = self.view(issue(author="stranger", association=association))
                self.assertEqual((result["trusted"], result["status"]), (False, "external"))
                self.assertEqual(result["author"]["association"], association or "NONE")

    def test_bot_is_trusted_with_none_association(self):
        result = self.view(issue(author="github-actions", typename="Bot", association="NONE"))
        self.assertEqual(result["author"], {"login": "github-actions", "bot": True, "association": "NONE"})
        self.assertEqual((result["trusted"], result["status"]), (True, "ready"))

    def test_view_marks_free_text_as_untrusted(self):
        node = issue(
            title="T",
            body="B",
            comments=[
                comment("C1", 1),
                comment("C2", 2, association="NONE", login="stranger"),
                comment("C3", 3, association="NONE", login="github-actions", typename="Bot"),
            ],
        )
        result = self.view(node)
        self.assertEqual((result["untrusted_title"], result["untrusted_body"]), ("T", "B"))
        self.assertNotIn("title", result)
        self.assertNotIn("body", result)
        self.assertEqual(
            result["untrusted_comments"],
            [
                {
                    "author": "owner",
                    "association": "OWNER",
                    "trusted": True,
                    "created_at": at(1),
                    "body": "C1",
                    "truncated": False,
                },
                {
                    "author": "stranger",
                    "association": "NONE",
                    "trusted": False,
                    "created_at": at(2),
                    "body": "C2",
                    "truncated": False,
                },
                {
                    "author": "github-actions",
                    "association": "NONE",
                    "trusted": True,
                    "created_at": at(3),
                    "body": "C3",
                    "truncated": False,
                },
            ],
        )

    def test_comment_without_association_is_untrusted(self):
        node = issue(comments=[{**comment("C", 1), "authorAssociation": None}])
        self.assertEqual(
            [(c["association"], c["trusted"]) for c in self.view(node)["untrusted_comments"]], [("NONE", False)]
        )

    def test_view_clips_body_and_comments(self):
        node = issue(
            body="あ" * (issues.BODY_LIMIT + 1),
            comments=[comment("い" * (issues.COMMENT_LIMIT + 1), 1), comment("う" * issues.COMMENT_LIMIT, 2)],
        )
        result = self.view(node)
        self.assertEqual((len(result["untrusted_body"]), result["body_truncated"]), (issues.BODY_LIMIT, True))
        self.assertEqual(
            [(len(c["body"]), c["truncated"]) for c in result["untrusted_comments"]],
            [(issues.COMMENT_LIMIT, True), (issues.COMMENT_LIMIT, False)],
        )


class ClaimTest(IssuesTestCase):
    def test_claim_line_gives_branch_and_session(self):
        result = self.claims([claim("feat/a", 1, "s1")])
        self.assertEqual((result["claim_branch"], result["claim_session"], result["claim_at"]), ("feat/a", "s1", at(1)))
        self.assertEqual((result["competing_claims"], result["last_release"]), ([], None))

    def test_claim_without_session(self):
        result = self.claims([claim("feat/a", 1)])
        self.assertEqual((result["claim_branch"], result["claim_session"]), ("feat/a", None))

    def test_comment_without_claim_line_is_not_a_claim(self):
        result = self.claims([comment("ブランチ `feat/a` で直す", 1)])
        self.assertEqual((result["claim_branch"], result["claim_session"], result["claim_at"]), (None, None, None))

    def test_first_claim_wins_and_later_ones_compete(self):
        # 返ってきた順ではなく、時刻の順で勝ち負けを決める。
        result = self.claims([claim("feat/c", 3, "s3"), claim("feat/a", 1, "s1"), claim("feat/b", 2, "s2")])
        self.assertEqual(result["claim_session"], "s1")
        self.assertEqual(
            result["competing_claims"],
            [
                {"branch": "feat/b", "session": "s2", "at": at(2)},
                {"branch": "feat/c", "session": "s3", "at": at(3)},
            ],
        )

    def test_untrusted_claim_does_not_count(self):
        result = self.claims([claim("evil", 1, "x", association="NONE", login="stranger"), claim("feat/a", 2, "s1")])
        self.assertEqual((result["claim_session"], result["competing_claims"]), ("s1", []))

    def test_bot_claim_counts(self):
        result = self.claims([claim("bot/a", 1, "b1", association="NONE", login="github-actions", typename="Bot")])
        self.assertEqual(result["claim_session"], "b1")


class ReleaseTest(IssuesTestCase):
    def test_release_with_id_matches_only_by_id(self):
        # 同じブランチ名でも、ID の無い着手と別の ID の着手は外さない。
        for claimed in (None, "s1"):
            with self.subTest(claim_session=claimed):
                result = self.claims([claim("feat/a", 1, claimed), release("feat/a", 2, "s2")])
                self.assertEqual((result["claim_branch"], result["claim_session"]), ("feat/a", claimed))
                self.assertIsNone(result["last_release"])

    def test_release_with_id_ignores_branch(self):
        result = self.claims([claim("feat/a", 1, "s1"), release("feat/renamed", 2, "s1")])
        self.assertIsNone(result["claim_branch"])
        self.assertEqual(result["last_release"]["cleared"], "all")

    def test_release_without_id_matches_by_branch(self):
        result = self.claims([claim("feat/a", 1, "s1"), release("feat/a", 2)])
        self.assertIsNone(result["claim_branch"])
        self.assertEqual(
            result["last_release"],
            {"kind": "手放し", "branch": "feat/a", "session": None, "at": at(2), "cleared": "all"},
        )

    def test_release_without_id_on_other_branch_clears_nothing(self):
        result = self.claims([claim("feat/a", 1), release("feat/b", 2)])
        self.assertEqual((result["claim_branch"], result["last_release"]), ("feat/a", None))

    def test_winner_release_clears_competing_claims(self):
        result = self.claims([claim("feat/a", 1, "s1"), claim("feat/b", 2, "s2"), release("feat/a", 3, "s1")])
        self.assertEqual((result["claim_session"], result["competing_claims"]), (None, []))
        self.assertEqual(
            result["last_release"],
            {"kind": "手放し", "branch": "feat/a", "session": "s1", "at": at(3), "cleared": "all"},
        )

    def test_loser_release_clears_only_that_claim(self):
        result = self.claims(
            [claim("feat/a", 1, "s1"), claim("feat/b", 2, "s2"), claim("feat/c", 3, "s3"), release("feat/b", 4, "s2")]
        )
        self.assertEqual(result["claim_session"], "s1")
        self.assertEqual([c["session"] for c in result["competing_claims"]], ["s3"])
        self.assertEqual(
            result["last_release"],
            {"kind": "手放し", "branch": "feat/b", "session": "s2", "at": at(4), "cleared": "one"},
        )

    def test_loser_release_without_id_matches_by_branch(self):
        result = self.claims([claim("feat/a", 1), claim("feat/b", 2), release("feat/b", 3)])
        self.assertEqual((result["claim_branch"], result["competing_claims"]), ("feat/a", []))
        self.assertEqual(result["last_release"]["cleared"], "one")

    def test_done_line_releases_like_release(self):
        result = self.claims([claim("feat/a", 1, "s1"), claim("feat/b", 2, "s2"), release("feat/a", 3, "s1", "済み")])
        self.assertEqual((result["claim_branch"], result["competing_claims"]), (None, []))
        self.assertEqual((result["last_release"]["kind"], result["last_release"]["cleared"]), ("済み", "all"))

    def test_removing_doing_label_clears_all_claims(self):
        result = self.claims([claim("feat/a", 1, "s1"), claim("feat/b", 2, "s2")], [unlabeled(3)])
        self.assertEqual((result["claim_branch"], result["competing_claims"]), (None, []))
        self.assertEqual(
            result["last_release"],
            {"kind": "unlabeled", "branch": None, "session": None, "at": at(3), "cleared": "all"},
        )

    def test_removing_other_label_clears_nothing(self):
        result = self.claims([claim("feat/a", 1, "s1")], [unlabeled(2, "priority:high")])
        self.assertEqual((result["claim_session"], result["last_release"]), ("s1", None))

    def test_last_release_is_the_last_one_that_cleared(self):
        # 手放しを書いてからラベルを外すと、ラベルを外した記録は何も外さない。当たらない手放しも同じ。
        result = self.claims(
            [claim("feat/a", 1, "s1"), release("feat/a", 2, "s1"), release("feat/x", 4, "s9")], [unlabeled(3)]
        )
        self.assertIsNone(result["claim_branch"])
        self.assertEqual(
            result["last_release"],
            {"kind": "手放し", "branch": "feat/a", "session": "s1", "at": at(2), "cleared": "all"},
        )

    def test_release_comment_sorts_before_unlabeled_at_same_time(self):
        result = self.claims([claim("feat/a", 1, "s1"), release("feat/a", 2, "s1")], [unlabeled(2)])
        self.assertEqual((result["last_release"]["kind"], result["last_release"]["session"]), ("手放し", "s1"))

    def test_release_sorts_before_claim_at_same_time(self):
        # 同じ時刻なら、前の着手を手放してから新しい着手を読む。
        result = self.claims([claim("feat/a", 1, "s1"), claim("feat/b", 2, "s2"), release("feat/a", 2, "s1")])
        self.assertEqual((result["claim_session"], result["competing_claims"]), ("s2", []))
        self.assertEqual(result["last_release"]["session"], "s1")

    def test_new_claim_after_release_wins(self):
        result = self.claims([claim("feat/a", 1, "s1"), release("feat/a", 2, "s1"), claim("feat/b", 3, "s2")])
        self.assertEqual((result["claim_session"], result["competing_claims"]), ("s2", []))
        self.assertEqual(result["last_release"]["at"], at(2))

    def test_untrusted_release_is_ignored(self):
        result = self.claims([claim("feat/a", 1, "s1"), release("feat/a", 2, "s1", association="NONE", login="x")])
        self.assertEqual((result["claim_session"], result["last_release"]), ("s1", None))

    def test_release_without_claim_clears_nothing(self):
        result = self.claims([release("feat/a", 1, "s1")], [unlabeled(2)])
        self.assertEqual((result["claim_branch"], result["last_release"]), (None, None))


class PriorityTest(IssuesTestCase):
    def test_labels_give_priority_and_difficulty(self):
        cases = [
            (["priority:high", "difficulty:expert"], "high", "expert"),
            (["priority:medium", "difficulty:hard"], "medium", "hard"),
            (["priority:low", "difficulty:medium"], "low", "medium"),
            (["difficulty:easy"], None, "easy"),
        ]
        for labels, priority, difficulty in cases:
            with self.subTest(labels=labels):
                result = self.view(issue(labels=labels))
                self.assertEqual((result["priority"], result["difficulty"]), (priority, difficulty))

    def test_highest_label_wins(self):
        cases = [
            (["priority:low", "priority:high"], "high", None),
            (["priority:low", "priority:medium"], "medium", None),
            (["difficulty:easy", "difficulty:hard", "difficulty:expert"], None, "expert"),
            (["difficulty:easy", "difficulty:hard"], None, "hard"),
            (["difficulty:easy", "difficulty:medium"], None, "medium"),
        ]
        for labels, priority, difficulty in cases:
            with self.subTest(labels=labels):
                result = self.view(issue(labels=labels))
                self.assertEqual((result["priority"], result["difficulty"]), (priority, difficulty))

    def test_values_come_only_from_known_labels(self):
        node = issue(labels=["priority:urgent", "difficulty:trivial", "bug"], body="優先度: 高\n難易度: 難")
        result = self.view(node)
        self.assertEqual((result["priority"], result["difficulty"]), (None, None))

    def test_backlog_orders_by_priority_then_oldest(self):
        # 優先度のラベルが無い Issue は中として、中の Issue と作成の順に並ぶ。
        specs = {
            3: (["priority:high"], 10),
            1: (["priority:low"], 1),
            6: ([], 1),
            2: ([], 5),
            7: (["priority:low"], 4),
            5: (["priority:high", "priority:low"], 2),
            4: (["priority:medium"], 3),
        }
        for number, (labels, created) in specs.items():
            self.gh.add_issue(issue(number, labels=labels, created=day(created)))
        result = self.output("backlog")
        self.assertEqual([i["number"] for i in result["issues"]], [5, 3, 6, 4, 2, 1, 7])


class RepoTest(IssuesTestCase):
    def test_reports_visibility_and_default_branch(self):
        self.gh.add_repo(WORK, visibility="PUBLIC", default_branch="main")
        self.assertEqual(
            self.output("repo"),
            {
                "work": {"name": WORK, "visibility": "PUBLIC", "default_branch": "main", "missing_labels": []},
                "tracker": None,
                "tracker_error": None,
            },
        )

    def test_missing_labels_lists_every_label_when_none_exist(self):
        self.gh.add_repo(WORK, labels=[])
        self.assertEqual(self.output("repo")["work"]["missing_labels"], ALL_LABELS)

    def test_missing_labels_lists_only_absent_labels(self):
        self.gh.add_repo(WORK, labels=["agent:doing", "priority:medium", "difficulty:easy", "bug"])
        self.assertEqual(
            self.output("repo")["work"]["missing_labels"],
            [
                "agent:skip",
                "priority:high",
                "priority:low",
                "difficulty:expert",
                "difficulty:hard",
                "difficulty:medium",
            ],
        )

    def test_tracker_missing_labels_include_repo_label(self):
        self.gh.tracker_config = TRACKER
        self.gh.add_repo(TRACKER, labels=ALL_LABELS)
        self.assertEqual(self.output("repo")["tracker"]["missing_labels"], [f"repo:{WORK}"])
        self.gh.add_repo(TRACKER, labels=[*ALL_LABELS, f"repo:{WORK}"])
        self.assertEqual(self.output("repo")["tracker"]["missing_labels"], [])


class TrackerTest(IssuesTestCase):
    def use_tracker(self, work_visibility="PRIVATE", tracker_visibility="PRIVATE"):
        self.gh.add_repo(WORK, visibility=work_visibility)
        self.gh.add_repo(TRACKER, visibility=tracker_visibility, labels=[*ALL_LABELS, f"repo:{WORK}"])
        self.gh.tracker_config = TRACKER

    def test_without_config_there_is_no_tracker(self):
        result = self.output("repo")
        self.assertEqual((result["tracker"], result["tracker_error"]), (None, None))

    def test_tracker_naming_work_repo_is_ignored(self):
        self.gh.tracker_config = "O/WORK"
        result = self.output("repo")
        self.assertEqual((result["tracker"], result["tracker_error"]), (None, None))

    def test_tracker_as_narrow_as_work_is_used(self):
        pairs = [
            ("PRIVATE", "PRIVATE"),
            ("INTERNAL", "PRIVATE"),
            ("INTERNAL", "INTERNAL"),
            ("PUBLIC", "PRIVATE"),
            ("PUBLIC", "PUBLIC"),
        ]
        for work, tracker in pairs:
            with self.subTest(work=work, tracker=tracker):
                self.use_tracker(work, tracker)
                result = self.output("repo")
                self.assertIsNone(result["tracker_error"])
                self.assertEqual(
                    (result["tracker"]["name"], result["tracker"]["source"]),
                    (TRACKER, "git config --local gh-issue.tracker"),
                )

    def test_tracker_wider_than_work_is_not_used(self):
        for work, tracker in [("PRIVATE", "INTERNAL"), ("PRIVATE", "PUBLIC"), ("INTERNAL", "PUBLIC")]:
            with self.subTest(work=work, tracker=tracker):
                self.use_tracker(work, tracker)
                result = self.output("repo")
                self.assertEqual((result["work"]["name"], result["tracker"]), (WORK, None))
                self.assertIn(TRACKER, result["tracker_error"])
                self.assertIn("広く見える", result["tracker_error"])

    def test_unusable_tracker_config_is_reported(self):
        for value in ("not-a-repo", "o/a/b", "o/missing", 128):
            with self.subTest(value=value):
                self.gh.tracker_config = value
                result = self.output("repo")
                self.assertEqual((result["work"]["name"], result["tracker"]), (WORK, None))
                self.assertTrue(result["tracker_error"])

    def test_repo_option_does_not_read_tracker(self):
        self.use_tracker()
        for argv in (["repo", "--repo", WORK], ["backlog", "--repo", WORK]):
            with self.subTest(argv=argv):
                self.gh.calls.clear()
                result = self.output(*argv)
                self.assertEqual((result["tracker"], result["tracker_error"]), (None, None))
                self.assertEqual([c for c in self.gh.calls if c[0] == "git" or c[:3] == ["gh", "repo", "view"]], [])

    def test_backlog_reads_tracker_issues_with_repo_label(self):
        self.use_tracker()
        self.gh.add_issue(issue(1, created=day(2)))
        self.gh.add_issue(issue(10, labels=[f"repo:{WORK}"], created=day(1)), TRACKER)
        self.gh.add_issue(issue(11, labels=["repo:o/other"], created=day(1)), TRACKER)
        result = self.output("backlog")
        self.assertEqual([(i["repo"], i["number"]) for i in result["issues"]], [(TRACKER, 10), (WORK, 1)])
        self.assertEqual(result["open_total"], {WORK: 1, f"{TRACKER} (repo:{WORK})": 1})
        self.assertEqual([q["labels"] for q in self.gh.backlog_queries(TRACKER)], [[f"repo:{WORK}"]])
        self.assertEqual([q["labels"] for q in self.gh.backlog_queries(WORK)], [None])

    def test_backlog_keeps_work_issues_when_tracker_read_fails(self):
        self.use_tracker()
        self.gh.add_issue(issue(1))
        self.gh.fail(TRACKER, "backlog", returncode=1, stderr="HTTP 502")
        result = self.output("backlog")
        self.assertEqual([(i["repo"], i["number"]) for i in result["issues"]], [(WORK, 1)])
        self.assertTrue(result["tracker_error"].startswith(f"{TRACKER} の Issue を読めない"))
        self.assertEqual(result["open_total"], {WORK: 1})

    def test_backlog_does_not_read_rejected_tracker(self):
        self.use_tracker("PRIVATE", "PUBLIC")
        self.gh.add_issue(issue(10, labels=[f"repo:{WORK}"]), TRACKER)
        result = self.output("backlog")
        self.assertEqual((result["issues"], result["tracker"]), ([], None))
        self.assertTrue(result["tracker_error"])
        self.assertEqual(self.gh.backlog_queries(TRACKER), [])


class CommandLineTest(IssuesTestCase):
    def test_malformed_repo_exits_2(self):
        for value in ("noslash", "a/b/c", "/name", "owner/", ""):
            for argv in (["--repo", value, "repo"], ["repo", "--repo", value], ["view", "1", "--repo", value]):
                with self.subTest(argv=argv):
                    code, out, _ = self.call(*argv)
                    self.assertEqual((code, out), (2, ""))
        self.assertEqual(self.gh.calls, [])

    def test_repo_option_before_subcommand_is_used(self):
        self.gh.add_repo("o/other")
        self.assertEqual(self.output("--repo", "o/other", "repo")["work"]["name"], "o/other")

    def test_limit_out_of_range_exits_2(self):
        for value in ("0", "101", "-1", "x"):
            with self.subTest(value=value):
                self.assertEqual(self.call("backlog", "--limit", value)[0], 2)

    def test_limit_in_range_is_passed_to_query(self):
        for value in ("1", "100"):
            with self.subTest(value=value):
                self.output("backlog", "--limit", value)
                self.assertEqual(self.gh.backlog_queries(WORK)[-1]["first"], int(value))

    def test_default_limit_is_50(self):
        self.output("backlog")
        self.assertEqual(self.gh.backlog_queries(WORK)[-1]["first"], 50)

    def test_truncated_when_more_issues_than_limit(self):
        for number in (1, 2, 3):
            self.gh.add_issue(issue(number))
        result = self.output("backlog", "--limit", "2")
        self.assertEqual((len(result["issues"]), result["truncated"], result["open_total"]), (2, True, {WORK: 3}))
        self.assertFalse(self.output("backlog", "--limit", "3")["truncated"])

    def test_comments_truncated(self):
        node = issue(comments=[comment(f"c{i}", i) for i in range(25)])
        result = self.view(node)
        self.assertEqual((result["comments"], result["comments_truncated"]), (25, True))
        self.assertFalse(self.view(node, "--comments", "100")["comments_truncated"])

    def test_comments_out_of_range_exits_2(self):
        for value in ("0", "101"):
            with self.subTest(value=value):
                self.assertEqual(self.call("view", "1", "--comments", value)[0], 2)

    def test_gh_failures_exit_1(self):
        cases = {
            "gh が失敗": {"returncode": 1, "stderr": "HTTP 401: Bad credentials"},
            "GraphQL のエラー": {"stdout": json.dumps({"errors": [{"message": "Something went wrong"}]})},
            "JSON でない": {"stdout": "<html>"},
            "想定と違う形": {"stdout": json.dumps({"data": {"repository": {"nameWithOwner": WORK}}})},
        }
        for name, failure in cases.items():
            with self.subTest(name):
                self.gh.fail(WORK, "repo", **failure)
                code, out, err = self.call("repo")
                self.assertEqual((code, out), (1, ""))
                self.assertTrue(err.startswith("issues.py: "), err)

    def test_unresolved_work_repo_exits_1(self):
        self.gh.work = None
        for argv in (["repo"], ["backlog"], ["view", "1"]):
            with self.subTest(argv=argv):
                code, out, err = self.call(*argv)
                self.assertEqual((code, out), (1, ""))
                self.assertIn("gh repo view", err)

    def test_missing_repo_or_issue_exits_1(self):
        for argv in (
            ["repo", "--repo", "o/missing"],
            ["backlog", "--repo", "o/missing"],
            ["view", "99", "--repo", WORK],
        ):
            with self.subTest(argv=argv):
                code, out, err = self.call(*argv)
                self.assertEqual((code, out), (1, ""))
                self.assertTrue(err.startswith("issues.py: "), err)


if __name__ == "__main__":
    unittest.main()
