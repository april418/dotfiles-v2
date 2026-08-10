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
#   - セッション状態: ~/.claude/session-state/<cwd>.md
#   - プロジェクトの指示: .claude/CLAUDE.md
#
# セッション状態には、圧縮で落ちる判断（採用案・却下案・却下理由）と作業ツリーの
# 状態が入る。要約は「何を話したか」を残すが、案そのものは残して理由だけを落とす
# ため、却下した案を実装し始める事故が起きる。
#   https://qiita.com/hiranuma/items/60cd5dbf642e346f8be7
#
# **ユーザー全体の指示 (~/.claude/CLAUDE.md) は流さない。** ハーネスが compact 後の
# コンテキストへ claudeMd ブロックとして全文を戻すため二重になる。
#
# ## 出力量の上限
#
# additionalContext が 10,000 文字を超えるとハーネスがファイルへ退避し、
# コンテキストには先頭 2,000 文字のプレビューしか載らない。
# **エラーにはならず、載ったように見える。**
#
# 閾値は公開されていないが、本体のバンドルに定数として入っている。
# バージョンが上がったら次で引き直す (2.1.200 で確認)。
#
#   $ grep -ao 'PHa=1e4.\{0,40\}' "$(readlink -f "$(which claude)")"
#   → var PHa=1e4; ... async function CXe(e,t,n,r=PHa){if(e.length<=r)return e;
#
# 判定は `e.length` すなわち文字数であってバイト数ではない。`wc -c` で
# 見積もると日本語 1 文字が 3 バイトなので 3 倍過大になる。`wc -m` を使う。
#
# 上限に達した節は捨てずにパスだけ出す。黙って落とすと、全部載ったものとして
# 扱われる。
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

HOOK_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=./session-state-path.sh
. "$HOOK_DIR/session-state-path.sh"
STATE="$(session_state_path "$CWD")"

CWD="$CWD" TRANSCRIPT="$TRANSCRIPT" STATE="$STATE" HOOK_DIR="$HOOK_DIR" python3 <<'PY'
import importlib.util, json, os, pathlib

CWD = pathlib.Path(os.environ["CWD"])
TRANSCRIPT = os.environ.get("TRANSCRIPT") or ""

# 全体の上限。ハーネスの 10,000 に 1 割のマージンを取る。冒頭「出力量の上限」を参照。
MAX_TOTAL_CHARS = 9_000

# 「どのプロジェクトが作業中か」の判定は保存側と共有する。片方だけ基準が
# 変わると、保存したのに復旧しない状態になり、しかもエラーが出ない。
spec = importlib.util.spec_from_file_location(
    "active_projects", os.path.join(os.environ["HOOK_DIR"], "active-projects.py"))
active = importlib.util.module_from_spec(spec)
spec.loader.exec_module(active)


def read(path):
    try:
        return pathlib.Path(path).read_text(encoding="utf-8")
    except Exception:
        return None


project_mds = active.claude_md_files(CWD, TRANSCRIPT)

STATE = pathlib.Path(os.environ["STATE"])

parts = [
    "会話の要約が行われた。要約には「何を話したか」しか残らず、判断（採用案・"
    "却下案・却下理由）と順序制約は落ちる。以下を正とし、要約の側は仮説として扱うこと。"
    f"\n\n判断を下したら {STATE} の「判断ログ」節へ追記すること。"
]
total = len(parts[0])

# 状態を先頭に置く。上限に達したときに削られるのは後ろなので、最も小さく最も
# 復元価値が高いものを先に通す。
sections = [("このセッションの状態", STATE)]
sections += [("このプロジェクトの指示", p) for p in project_mds]

for label, path in sections:
    body = read(path)
    if body is None:
        continue
    heading = f"\n# {label} ({path})\n\n"
    if total + len(heading) + len(body) <= MAX_TOTAL_CHARS:
        section = heading + body
    else:
        section = heading + (
            f"（{len(body):,} 文字あり上限を超えるため本文を省いた。"
            "作業を始める前に Read すること）"
        )
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
