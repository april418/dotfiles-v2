#!/usr/bin/env bash
# ==================================================
# compact 後にセッション状態をコンテキストへ戻す
# ==================================================
# 要約は「何を話したか」を残すが、案そのものは残して理由だけを落とすため、
# 却下した案を実装し始める事故が起きる。圧縮の外側に置いたセッション状態
# (~/.claude/session-state/<cwd>.md) を compact 直後に戻す。中身は判断
# （採用案・却下案・却下理由）と作業ツリーの状態。
#   https://qiita.com/hiranuma/items/60cd5dbf642e346f8be7
#
# **PostCompact ではこれを実現できない。** あのイベントはログや通知などの
# 副作用専用で、hookSpecificOutput.additionalContext を受け付けない。
# SessionStart は受け付け、matcher に compact を指定すると compact 直後にだけ
# 発火する。そのため実装は SessionStart 側に置く。
#   https://code.claude.com/docs/en/hooks.md
#
# **指示ファイル (CLAUDE.md / AGENTS.md) は流さない。** ユーザー全体の指示と
# cwd とその祖先の指示はハーネスが compact 後にディスクから読み直し、cwd の子に
# ある指示は子のファイルを Read したときに載せ直す。流すと二重になる
# (2.1.295 / 2.1.272 で実測。AGENTS.md は 2.1.277 以降)。
#   https://code.claude.com/docs/en/context-window#what-survives-compaction
#
# ファイル名は役割と合っていないが、改名すると配置先に旧ファイルが残るので変えない。
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
# 上限を超えたら本文を捨ててパスだけ出す。黙って落とすと、全部載ったものとして
# 扱われる。
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

HOOK_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=./session-state-path.sh
. "$HOOK_DIR/session-state-path.sh"
STATE="$(session_state_path "$CWD")"

STATE="$STATE" python3 <<'PY'
import json, os, pathlib

STATE = pathlib.Path(os.environ["STATE"])

# 全体の上限。ハーネスの 10,000 に 1 割のマージンを取る。冒頭「出力量の上限」を参照。
MAX_TOTAL_CHARS = 9_000

# 状態が無い・空なら黙って終わる。見出しだけを返すと「判断が無い」と読める
# 文字列がコンテキストに入る。
try:
    body = STATE.read_text(encoding="utf-8")
except Exception:
    raise SystemExit(0)
if not body.strip():
    raise SystemExit(0)

lead = (
    "会話の要約が行われた。要約には「何を話したか」しか残らず、判断（採用案・"
    "却下案・却下理由）と順序制約は落ちる。以下を正とし、要約の側は仮説として扱うこと。"
    f"\n\n判断を下したら {STATE} の「判断ログ」節へ追記すること。"
)
heading = f"\n\n# このセッションの状態 ({STATE})\n\n"
if len(lead) + len(heading) + len(body) > MAX_TOTAL_CHARS:
    body = (
        f"（{len(body):,} 文字あり上限を超えるため本文を省いた。"
        "作業を始める前に Read すること）"
    )

print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": lead + heading + body,
    }
}))
PY
