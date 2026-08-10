#!/usr/bin/env bash
# ==================================================
# compact 後に CLAUDE.md をコンテキストへ戻す
# ==================================================
# 会話が長くなると context が要約され、CLAUDE.md に書いた規則が薄まる。
# 要約は「何を話したか」を残すもので、「どう振る舞うか」の指示は落ちる。
#
# **PostCompact ではこれを実現できない。** あのイベントはログや通知などの
# 副作用専用で、hookSpecificOutput.additionalContext を受け付けない。
# SessionStart は受け付け、matcher に compact を指定すると compact 直後にだけ
# 発火する。そのため実装は SessionStart 側に置く。
#   https://code.claude.com/docs/en/hooks.md
#
# 対象は 2 種類。
#   - ユーザー全体の指示: ~/.claude/CLAUDE.md
#   - プロジェクトの指示: .claude/CLAUDE.md
#
# ## プロジェクト指示の探し方
#
# **cwd から遡るだけでは足りない。** 複数リポジトリを束ねた親ディレクトリで
# 起動すると、目的の CLAUDE.md は cwd の「子」にある。実際にこの構成で
# 1 つも拾えなかった。
#
# 遡って見つからない場合は子を探すが、親に複数のリポジトリがあると全部
# ヒットする (実測で 4 件 54KB)。無関係なものまで流すと context を無駄に
# 食うため、**transcript にどれだけ現れたか**で作業中のものを選ぶ。
# 実測ではこの差が明確に出た (7797 / 1099 / 6 / 3 / 0)。
set -uo pipefail

INPUT="$(cat)"

# JSON の取り出しに jq を使わない。環境によっては入っておらず、その場合
# 抽出が空になって**フックが黙って素通りする**。防御が無効になったことに
# 気づけないため、依存を持たない実装にする (guard-branch-base.sh と同じ理由)。
extract() {
  printf '%s' "$INPUT" | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(0)
cur = d
for k in sys.argv[1].split('.'):
    if not isinstance(cur, dict):
        sys.exit(0)
    cur = cur.get(k)
    if cur is None:
        sys.exit(0)
print(cur, end='')
" "$1" 2>/dev/null
}

CWD="$(extract cwd)"
[ -n "$CWD" ] || CWD="$PWD"
TRANSCRIPT="$(extract transcript_path)"

CWD="$CWD" TRANSCRIPT="$TRANSCRIPT" HOME_DIR="$HOME" python3 <<'PY'
import json, os, pathlib

CWD = pathlib.Path(os.environ["CWD"])
TRANSCRIPT = os.environ.get("TRANSCRIPT") or ""
USER_MD = pathlib.Path(os.environ["HOME_DIR"]) / ".claude" / "CLAUDE.md"

# 子を探す深さ。リポジトリ直下 (<child>/.claude/CLAUDE.md) と、その 1 つ下の
# ネストまで見れば足りる。深くすると node_modules 等を掘って遅くなる。
MAX_DEPTH = 3
# transcript にこの回数以上現れたものだけ採る。実測の分布 (7797 / 1099 / 6 /
# 3 / 0) はこの閾値で綺麗に割れる。
MIN_MENTIONS = 10
# 同時に流すプロジェクト指示の上限。
MAX_PROJECTS = 3
# 全体の上限。これを超える分は落とす (context を食い潰さないため)。
MAX_TOTAL_CHARS = 120_000

SKIP_DIRS = {"node_modules", ".git", "dist", "build", ".next", "vendor", "target"}


def read(path):
    try:
        return pathlib.Path(path).read_text(encoding="utf-8")
    except Exception:
        return None


def walk_up():
    """cwd から親へ遡って最初に見つかった .claude/CLAUDE.md。"""
    for d in [CWD, *CWD.parents]:
        candidate = d / ".claude" / "CLAUDE.md"
        if candidate.is_file():
            return candidate
    return None


def scan_children():
    """cwd 配下の .claude/CLAUDE.md を集める。"""
    found = []
    base_depth = len(CWD.parts)
    for root, dirs, files in os.walk(CWD):
        rootp = pathlib.Path(root)
        if len(rootp.parts) - base_depth >= MAX_DEPTH:
            dirs[:] = []
            continue
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        if rootp.name == ".claude" and "CLAUDE.md" in files:
            found.append(rootp / "CLAUDE.md")
    return found


def count_mentions(paths):
    """transcript に各プロジェクトのパスが何回現れるかを数える。

    transcript は数十 MB になるのでブロック単位で読む。境界をまたぐ一致を
    落とさないよう、前ブロックの末尾を繰り越す。
    """
    if not TRANSCRIPT or not os.path.isfile(TRANSCRIPT):
        return {p: 0 for p in paths}

    # <project-root>/ の形で数える。単なる名前だと MCP のツール名などが混ざる。
    needles = {p: f"{p.parent.parent}/" for p in paths}
    counts = {p: 0 for p in paths}
    overlap = max((len(n) for n in needles.values()), default=0)
    tail = ""
    try:
        with open(TRANSCRIPT, encoding="utf-8", errors="ignore") as f:
            while True:
                block = f.read(1 << 20)
                if not block:
                    break
                chunk = tail + block
                for p, needle in needles.items():
                    counts[p] += chunk.count(needle)
                tail = chunk[-overlap:] if overlap else ""
    except Exception:
        return {p: 0 for p in paths}
    return counts


project_mds = []
up = walk_up()
if up is not None:
    project_mds.append(up)
else:
    children = scan_children()
    if len(children) == 1:
        project_mds = children
    elif children:
        counts = count_mentions(children)
        ranked = sorted(children, key=lambda p: -counts[p])
        project_mds = [p for p in ranked if counts[p] >= MIN_MENTIONS][:MAX_PROJECTS]

parts = [
    "会話の要約が行われた。要約には「何を話したか」しか残らないため、"
    "従うべき指示を以下に再掲する。以降はこの内容に従うこと。"
]
total = len(parts[0])

for label, path in [("ユーザーの全体指示", USER_MD)] + [
    ("このプロジェクトの指示", p) for p in project_mds
]:
    body = read(path)
    if body is None:
        continue
    section = f"\n# {label} ({path})\n\n{body}"
    if total + len(section) > MAX_TOTAL_CHARS:
        continue
    parts.append(section)
    total += len(section)

# 見出しだけで本文が 1 つも無いなら黙って終わる。空の additionalContext を
# 返すと「規則が無い」と読める文字列がコンテキストに入る。
if len(parts) == 1:
    raise SystemExit(0)

print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": "\n".join(parts),
    }
}))
PY
