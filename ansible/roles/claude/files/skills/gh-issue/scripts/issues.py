"""GitHub の Issue を読み、着手してよいかの判断に使う信号を JSON で標準出力に出す。

GitHub には書き込まない。終了コードは 0 = 読めた、1 = gh の呼び出しか作業中のリポジトリの解決に失敗した、
2 = 引数の誤り。失敗の理由は標準エラーに出す。書き込み先（tracker）だけが読めないときは、理由を
tracker_error に入れて作業中のリポジトリの分を出し、0 で終わる。
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys

DOING_LABEL = "agent:doing"
SKIP_LABEL = "agent:skip"
AGENT_LABELS = [DOING_LABEL, SKIP_LABEL]
# 別のリポジトリを書き込み先にしたとき、作業中のリポジトリ向けの Issue をこのラベルで見分ける。
TRACKER_LABEL_PREFIX = "repo:"
TRACKER_CONFIG_KEY = "gh-issue.tracker"
CLAIM_PATTERN = re.compile(r"^着手: ブランチ `([^`\n]+)`(?: セッション `([^`\n]+)`)?", re.MULTILINE)
RELEASE_PATTERN = re.compile(r"^(?:手放し|済み): ブランチ `([^`\n]+)`", re.MULTILINE)
TRUSTED_ASSOCIATIONS = {"OWNER", "MEMBER", "COLLABORATOR"}
# 書き込み先が作業中のリポジトリより広く見えると、作業中のリポジトリの名前と作業の中身が漏れる。
VISIBILITY_RANK = {"PRIVATE": 0, "INTERNAL": 1, "PUBLIC": 2}
BODY_LIMIT = 6000
COMMENT_LIMIT = 1500
GH_TIMEOUT_SECONDS = 60

PR_FIELDS = "number state author { __typename } authorAssociation repository { nameWithOwner }"
COMMENT_FIELDS = "author { __typename login } authorAssociation createdAt body"

ISSUE_FIELDS = """
number
title
state
createdAt
updatedAt
author { __typename login }
authorAssociation
labels(first: 30) { nodes { name } }
linkedBranches(first: 10) { nodes { ref { name } } }
closedByPullRequestsReferences(first: 10, includeClosedPrs: false) { nodes { PR_FIELDS } }
timelineItems(itemTypes: [CROSS_REFERENCED_EVENT], last: 30) {
  nodes { ... on CrossReferencedEvent { source { __typename ... on PullRequest { PR_FIELDS } } } }
}
unlabeled: timelineItems(itemTypes: [UNLABELED_EVENT], last: 20) {
  nodes { ... on UnlabeledEvent { createdAt label { name } } }
}
blockedBy(first: 20) { nodes { number state repository { nameWithOwner } } }
parent { number }
subIssuesSummary { total completed }
""".replace("PR_FIELDS", PR_FIELDS)

BACKLOG_QUERY = """
query($owner: String!, $name: String!, $first: Int!, $labels: [String!]) {
  repository(owner: $owner, name: $name) {
    issues(states: OPEN, first: $first, labels: $labels, orderBy: {field: UPDATED_AT, direction: DESC}) {
      totalCount
      nodes {
        ISSUE_FIELDS
        comments(last: 20) { totalCount nodes { COMMENT_FIELDS } }
      }
    }
  }
}
""".replace("ISSUE_FIELDS", ISSUE_FIELDS).replace("COMMENT_FIELDS", COMMENT_FIELDS)

VIEW_QUERY = """
query($owner: String!, $name: String!, $number: Int!, $comments: Int!) {
  repository(owner: $owner, name: $name) {
    issue(number: $number) {
      stateReason
      body
      ISSUE_FIELDS
      comments(last: $comments) { totalCount nodes { COMMENT_FIELDS } }
    }
  }
}
""".replace("ISSUE_FIELDS", ISSUE_FIELDS).replace("COMMENT_FIELDS", COMMENT_FIELDS)


class GhError(Exception):
    pass


def run(args: list[str], stdin: str | None = None) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            args, input=stdin, capture_output=True, text=True, timeout=GH_TIMEOUT_SECONDS, check=False
        )
    except FileNotFoundError as e:
        raise GhError(f"{args[0]} が見つからない") from e
    except subprocess.TimeoutExpired as e:
        raise GhError(f"{' '.join(args[:3])} が {GH_TIMEOUT_SECONDS} 秒で終わらなかった") from e


def graphql(query: str, variables: dict) -> dict:
    # 変数は -f で渡すと配列と null を表せないので、要求の本体ごと標準入力から渡す。
    proc = run(["gh", "api", "graphql", "--input", "-"], json.dumps({"query": query, "variables": variables}))
    if proc.returncode != 0:
        raise GhError(f"gh api graphql が exit {proc.returncode}: {proc.stderr.strip() or proc.stdout.strip()}")
    payload = json.loads(proc.stdout)
    if payload.get("errors"):
        raise GhError("GraphQL のエラー: " + "; ".join(e.get("message", "") for e in payload["errors"]))
    return payload["data"]


def split_repo(repo: str) -> tuple[str, str]:
    owner, sep, name = repo.partition("/")
    if not sep or not owner or not name or "/" in name:
        raise GhError(f"リポジトリは OWNER/REPO の形で指定する: {repo}")
    return owner, name


def repo_argument(value: str) -> str:
    try:
        split_repo(value)
    except GhError as e:
        raise argparse.ArgumentTypeError(str(e)) from e
    return value


def nodes(connection: dict | None) -> list[dict]:
    # 読めない相手（private の Issue など）は nodes に null で入ることがあるので落とす。
    return [n for n in ((connection or {}).get("nodes") or []) if n]


def is_trusted(author: dict | None, association: str | None) -> bool:
    # github-actions の authorAssociation は NONE なので、bot は __typename で見分ける。
    return (author or {}).get("__typename") == "Bot" or (association or "NONE") in TRUSTED_ASSOCIATIONS


def describe_repo(repo: str, labels: list[str]) -> dict:
    owner, name = split_repo(repo)
    aliases = " ".join(f"l{i}: label(name: $l{i}) {{ name }}" for i in range(len(labels)))
    params = "".join(f", $l{i}: String!" for i in range(len(labels)))
    query = (
        f"query($owner: String!, $name: String!{params}) {{ repository(owner: $owner, name: $name) {{ "
        f"nameWithOwner visibility defaultBranchRef {{ name }} {aliases} }} }}"
    )
    variables = {"owner": owner, "name": name, **{f"l{i}": label for i, label in enumerate(labels)}}
    data = graphql(query, variables)["repository"]
    if data is None:
        raise GhError(f"{repo} が見つからないか、読めない")
    return {
        "name": data["nameWithOwner"],
        "visibility": data["visibility"],
        "default_branch": (data.get("defaultBranchRef") or {}).get("name"),
        "missing_labels": [label for i, label in enumerate(labels) if not data.get(f"l{i}")],
    }


def work_repo_name() -> str:
    proc = run(["gh", "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"])
    if proc.returncode != 0:
        raise GhError(f"作業中のリポジトリを gh repo view で解決できない: {proc.stderr.strip()}")
    return proc.stdout.strip()


def tracker_repo_name() -> str | None:
    # 書き込み先は clone ごとに決めるので、global の設定は読まない。
    proc = run(["git", "config", "--local", "--get", TRACKER_CONFIG_KEY])
    # git config --get は、キーが無いと exit 1 で何も出さない。
    if proc.returncode == 1:
        return None
    if proc.returncode != 0:
        raise GhError(f"git config --local --get {TRACKER_CONFIG_KEY} が exit {proc.returncode}: {proc.stderr.strip()}")
    return proc.stdout.strip() or None


def resolve(repo_option: str | None) -> tuple[dict, dict | None, str | None]:
    """作業中のリポジトリ、書き込み先、書き込み先を使えない理由を返す。--repo を渡したら書き込み先は読まない。"""
    if repo_option:
        return describe_repo(repo_option, AGENT_LABELS), None, None
    work = describe_repo(work_repo_name(), AGENT_LABELS)
    try:
        tracker_name = tracker_repo_name()
        if not tracker_name or tracker_name.lower() == work["name"].lower():
            return work, None, None
        try:
            split_repo(tracker_name)
        except GhError as e:
            raise GhError(f"git config の {TRACKER_CONFIG_KEY} が OWNER/REPO の形でない: {tracker_name}") from e
        tracker = describe_repo(tracker_name, [*AGENT_LABELS, TRACKER_LABEL_PREFIX + work["name"]])
        if VISIBILITY_RANK.get(tracker["visibility"], 2) > VISIBILITY_RANK.get(work["visibility"], 0):
            raise GhError(
                f"書き込み先 {tracker['name']}（{tracker['visibility']}）が作業中のリポジトリ"
                f"（{work['visibility']}）より広く見えるので使わない"
            )
        tracker["source"] = f"git config --local {TRACKER_CONFIG_KEY}"
    except GhError as e:
        return work, None, str(e)
    return work, tracker, None


def ref(node: dict) -> str:
    return f"{(node.get('repository') or {}).get('nameWithOwner', '?')}#{node.get('number')}"


def current_claim(comments: list[dict], unlabeled: list[dict]) -> tuple[dict | None, list[dict]]:
    """最後の手放しより後の最初の着手と、その後に重なった着手を返す。

    手放しは、信頼する書き手の「手放し:」「済み:」のコメントと、agent:doing を外した記録の両方で数える。
    ラベルを外すには triage 以上の権限が要るので、外した人は信頼する書き手である。
    """
    # ISO 8601 の UTC の時刻は文字列の順に並べれば時刻の順になる。同じ時刻なら手放しを先に置く。
    events = [
        (e.get("createdAt") or "", 0, None) for e in unlabeled if (e.get("label") or {}).get("name") == DOING_LABEL
    ]
    for comment in comments:
        if not is_trusted(comment.get("author"), comment.get("authorAssociation")):
            continue
        body = comment.get("body") or ""
        if RELEASE_PATTERN.search(body):
            events.append((comment.get("createdAt") or "", 0, None))
        match = CLAIM_PATTERN.search(body)
        if match:
            claim = {"branch": match.group(1), "session": match.group(2), "at": comment.get("createdAt")}
            events.append((comment.get("createdAt") or "", 1, claim))
    winner = None
    competing = []
    for _, kind, claim in sorted(events, key=lambda e: (e[0], e[1])):
        if kind == 0:
            winner, competing = None, []
        elif winner is None:
            winner = claim
        else:
            competing.append(claim)
    return winner, competing


def signals(node: dict, repo: str) -> dict:
    """GraphQL の Issue のノードから、着手の判断に使う信号を組み立てる。"""
    labels = [n.get("name") for n in nodes(node.get("labels"))]
    author = node.get("author") or {}
    association = node.get("authorAssociation") or "NONE"
    trusted = is_trusted(author, association)
    state = node.get("state") or "OPEN"

    branches = [n["ref"]["name"] for n in nodes(node.get("linkedBranches")) if n.get("ref")]
    open_prs: dict[str, dict] = {}
    for pr in nodes(node.get("closedByPullRequestsReferences")):
        if pr.get("state") == "OPEN":
            open_prs[ref(pr)] = {"closes": True, "trusted": is_trusted(pr.get("author"), pr.get("authorAssociation"))}
    for event in nodes(node.get("timelineItems")):
        source = event.get("source") or {}
        if source.get("__typename") == "PullRequest" and source.get("state") == "OPEN":
            pr_trusted = is_trusted(source.get("author"), source.get("authorAssociation"))
            open_prs.setdefault(ref(source), {"closes": False, "trusted": pr_trusted})
    trusted_prs = [k for k, v in open_prs.items() if v["trusted"]]
    blocked_by = [ref(b) for b in nodes(node.get("blockedBy")) if b.get("state") == "OPEN"]

    comment_nodes = nodes(node.get("comments"))
    claim, competing = current_claim(comment_nodes, nodes(node.get("unlabeled")))
    sub = node.get("subIssuesSummary") or {}
    sub_total, sub_done = sub.get("total") or 0, sub.get("completed") or 0

    reasons = []
    if state != "OPEN":
        status = "closed"
        reasons.append(f"state が {state}")
    elif SKIP_LABEL in labels:
        status = "skip"
        reasons.append(f"ラベル {SKIP_LABEL}")
    elif DOING_LABEL in labels or trusted_prs or branches:
        status = "doing"
        if DOING_LABEL in labels:
            reasons.append(f"ラベル {DOING_LABEL}")
        reasons += [f"開いている PR {k}" for k in trusted_prs]
        reasons += [f"紐付いたブランチ {b}" for b in branches]
    elif blocked_by:
        status = "blocked"
        reasons += [f"開いている {b} に blocked-by" for b in blocked_by]
    elif sub_total > sub_done:
        status = "umbrella"
        reasons.append(f"sub-issue が {sub_total - sub_done} 件開いている")
    elif not trusted:
        status = "external"
        reasons.append(f"作者 {author.get('login')} の authorAssociation が {association}")
    else:
        status = "ready"

    return {
        "repo": repo,
        "number": node.get("number"),
        # タイトルも誰でも書けるので、キーの名前で指示ではないことを示す。
        "untrusted_title": node.get("title"),
        "status": status,
        "reasons": reasons,
        "author": {"login": author.get("login"), "bot": author.get("__typename") == "Bot", "association": association},
        "trusted": trusted,
        "labels": labels,
        "claim_branch": (claim or {}).get("branch"),
        "claim_session": (claim or {}).get("session"),
        "claim_at": (claim or {}).get("at"),
        "competing_claims": competing,
        "linked_branches": branches,
        "open_prs": [{"ref": k, "closes": v["closes"]} for k, v in open_prs.items() if v["trusted"]],
        "other_prs": [k for k, v in open_prs.items() if not v["trusted"]],
        "blocked_by": blocked_by,
        "parent": (node.get("parent") or {}).get("number"),
        "sub_issues": {"total": sub_total, "completed": sub_done},
        "comments": (node.get("comments") or {}).get("totalCount", 0),
        "comments_truncated": (node.get("comments") or {}).get("totalCount", 0) > len(comment_nodes),
        "created_at": node.get("createdAt"),
        "updated_at": node.get("updatedAt"),
    }


def clip(text: str | None, limit: int) -> tuple[str, bool]:
    text = text or ""
    return (text[:limit], True) if len(text) > limit else (text, False)


def read_backlog(repo: str, limit: int, labels: list[str] | None) -> tuple[list[dict], int]:
    owner, name = split_repo(repo)
    data = graphql(BACKLOG_QUERY, {"owner": owner, "name": name, "first": limit, "labels": labels})
    issues = (data.get("repository") or {}).get("issues")
    if issues is None:
        raise GhError(f"{repo} の Issue を読めない")
    return [signals(n, repo) for n in nodes(issues)], issues.get("totalCount", 0)


def cmd_repo(args: argparse.Namespace) -> dict:
    work, tracker, tracker_error = resolve(args.repo)
    return {"work": work, "tracker": tracker, "tracker_error": tracker_error}


def cmd_backlog(args: argparse.Namespace) -> dict:
    work, tracker, tracker_error = resolve(args.repo)
    issues, total = read_backlog(work["name"], args.limit, None)
    open_total = {work["name"]: total}
    if tracker:
        label = TRACKER_LABEL_PREFIX + work["name"]
        try:
            tracked, tracked_total = read_backlog(tracker["name"], args.limit, [label])
        except GhError as e:
            tracker_error = f"{tracker['name']} の Issue を読めない: {e}"
        else:
            issues += tracked
            open_total[f"{tracker['name']} ({label})"] = tracked_total
    return {
        "work": work,
        "tracker": tracker,
        "tracker_error": tracker_error,
        "issues": issues,
        "open_total": open_total,
        "truncated": any(n > args.limit for n in open_total.values()),
    }


def cmd_view(args: argparse.Namespace) -> dict:
    repo = args.repo or work_repo_name()
    owner, name = split_repo(repo)
    data = graphql(VIEW_QUERY, {"owner": owner, "name": name, "number": args.number, "comments": args.comments})
    node = (data.get("repository") or {}).get("issue")
    if node is None:
        raise GhError(f"{repo}#{args.number} が見つからないか、読めない")
    result = signals(node, repo)
    result["state"] = node.get("state")
    result["state_reason"] = node.get("stateReason")
    # 本文とコメントは誰でも書けるので、キーの名前で指示ではないことを示す。
    body, truncated = clip(node.get("body"), BODY_LIMIT)
    result["untrusted_body"] = body
    result["body_truncated"] = truncated
    result["untrusted_comments"] = []
    for comment in nodes(node.get("comments")):
        text, cut = clip(comment.get("body"), COMMENT_LIMIT)
        association = comment.get("authorAssociation") or "NONE"
        result["untrusted_comments"].append(
            {
                "author": (comment.get("author") or {}).get("login"),
                "association": association,
                "trusted": is_trusted(comment.get("author"), association),
                "created_at": comment.get("createdAt"),
                "body": text,
                "truncated": cut,
            }
        )
    return result


def parse_args(argv: list[str]) -> argparse.Namespace:
    # gh と同じくサブコマンドの後ろにも --repo を書けるよう、前と後ろの両方で受ける。
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--repo",
        type=repo_argument,
        default=argparse.SUPPRESS,
        help="読むリポジトリ（OWNER/REPO）。省くと作業中のリポジトリと、その書き込み先",
    )
    parser = argparse.ArgumentParser(
        description="GitHub の Issue を読み、着手の判断に使う信号を JSON で出す。", parents=[common]
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser(
        "repo", parents=[common], help="作業中のリポジトリと書き込み先の visibility・既定ブランチ・無いラベル"
    )

    backlog = sub.add_parser("backlog", parents=[common], help="開いている Issue と、それぞれの信号")
    backlog.add_argument("--limit", type=int, default=50, choices=range(1, 101), metavar="1-100")

    view = sub.add_parser("view", parents=[common], help="1 件の本文・コメントと信号")
    view.add_argument("number", type=int)
    view.add_argument("--comments", type=int, default=20, choices=range(1, 101), metavar="1-100")
    args = parser.parse_args(argv)
    if not hasattr(args, "repo"):
        args.repo = None
    return args


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    handlers = {"repo": cmd_repo, "backlog": cmd_backlog, "view": cmd_view}
    try:
        result = handlers[args.command](args)
    except GhError as e:
        print(f"issues.py: {e}", file=sys.stderr)
        return 1
    except (ValueError, KeyError, TypeError, AttributeError) as e:
        # gh が JSON でないものや想定と違う形を返したとき。traceback より 1 行の理由の方が読み手は動ける。
        print(f"issues.py: gh の出力を読めない（{type(e).__name__}: {e}）", file=sys.stderr)
        return 1
    json.dump(result, sys.stdout, ensure_ascii=False, indent=1)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
