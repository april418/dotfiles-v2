#!/usr/bin/env bash
# ==================================================
# compact 後と resume 時にセッション状態をコンテキストへ戻す
# ==================================================
# 要約は「何を話したか」を残すが、案そのものは残して理由だけを落とすため、
# 却下した案を実装し始める事故が起きる。圧縮の外側に置いたセッション状態
# (~/.claude/session-state/<cwd>.md) を compact 直後に戻す。中身は判断
# （採用案・却下案・却下理由）と作業ツリーの状態。
#   https://qiita.com/hiranuma/items/60cd5dbf642e346f8be7
#
# resume でも戻す。履歴はそのまま読み込まれるが、止まっていた間に同じ cwd の
# ほかのセッションが足した判断は入ってこない。前置きは source で切り替える。
# 要約が行われたと書くと、resume では事実と合わない。
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
# 上限を超えたら古い側を行の単位で省き、新しい側を上限まで出す。状態ファイルは追記で
# 育ち、最近の判断と、直前の PreCompact が書いた作業ツリーの状態は末尾にある。省いた
# ことは本文の頭に書く。黙って落とすと、全部載ったものとして扱われる。
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
SOURCE="$(extract source)"

HOOK_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=./session-state-path.sh
. "$HOOK_DIR/session-state-path.sh"
STATE="$(session_state_path "$CWD")"

STATE="$STATE" SOURCE="$SOURCE" python3 <<'PY'
import json, os, pathlib

STATE = pathlib.Path(os.environ["STATE"])
SOURCE = os.environ.get("SOURCE", "")

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

append_rule = (
    f"\n\nグローバル指示の「判断ログ」節に挙げた場面で判断を下したら、その節の書き方で {STATE} の「判断ログ」節へ追記すること。"
)
if SOURCE == "resume":
    lead = (
        "セッションが再開された。会話の履歴はそのまま読み込まれているが、止まっていた間に"
        "同じ作業ディレクトリのほかのセッションが下した判断は入っていない。以下はこの作業"
        "ディレクトリの状態ファイルで、並行して動いたセッションや以前のセッションの判断も含む。"
        "履歴に会話の要約があれば、要約には判断（採用案・却下案・却下理由）と順序制約が残らない"
        "ので、要約の側は仮説として扱うこと。履歴と以下、または以下の判断どうしが食い違うときは、"
        "新しいほうを採ること。新しさは日付か覆したという記述で決め、どちらでも決められなければ、"
        "グローバル指示の「ユーザーに判断を委ねるとき」節に従って確かめること。" + append_rule
    )
else:
    lead = (
        "会話の要約が行われた。要約には「何を話したか」しか残らず、判断（採用案・"
        "却下案・却下理由）と順序制約は落ちる。以下はこの作業ディレクトリの状態ファイルで、"
        "並行して動いたセッションや以前のセッションの判断も含む。いまの作業に関わる"
        "判断は以下を正とし、要約の側は仮説として扱うこと。ただし以下の判断どうし、または"
        "以下と要約が食い違うときは、新しいほうを採ること。新しさは日付（要約はいまの"
        "セッションのもの）か覆したという記述で決め、どちらでも決められなければ、"
        "グローバル指示の「ユーザーに判断を委ねるとき」節に従って確かめること。" + append_rule
    )
heading = f"\n\n# この作業ディレクトリの状態 ({STATE})\n\n"


def u16(s):
    # ハーネスの判定は JS の length で、UTF-16 のコード単位を数える。絵文字のような
    # BMP の外の文字は len() では 1、length では 2 になる。
    return len(s.encode("utf-16-le")) // 2


if u16(lead + heading + body) > MAX_TOTAL_CHARS:
    NOTE_BUDGET = 200  # 下の省略の注記を収める分
    budget = MAX_TOTAL_CHARS - u16(lead + heading) - NOTE_BUDGET
    # 判断は日付で始まる 1 行の箇条書きで、見出しを持たないものが多い。見出しで
    # 切ると、末尾の作業ツリーの状態の節まで飛んで最近の判断を落とすので、行で切る。
    lines = body.splitlines(keepends=True)
    start, used = len(lines), 0
    while start > 0 and used + u16(lines[start - 1]) <= budget:
        start -= 1
        used += u16(lines[start])
    # 省いた側でコードブロックが開いたままなら、閉じのフェンスの次の行から始める。
    # そのまま始めると、閉じのフェンスが開きとして読まれ、以降が全部コードに見える。
    if sum(line.startswith("```") for line in lines[:start]) % 2:
        while start < len(lines) and not lines[start].startswith("```"):
            start += 1
        start += 1
    kept = "".join(lines[start:])
    body = (
        f"（全 {len(body):,} 文字のうち、新しい側の {len(kept):,} 文字だけを載せた。"
        "古い判断が要るときは、全文を grep するか offset を付けて Read すること）\n\n"
        + kept
    )

print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": lead + heading + body,
    }
}))
PY
