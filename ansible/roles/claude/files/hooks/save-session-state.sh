#!/usr/bin/env bash
# ==================================================
# 圧縮の直前に、機械で拾える作業状態を保存する
# ==================================================
# compact は「何を話したか」の要約を作る非可逆操作で、判断（採用案・却下案・
# 却下理由）や順序制約が落ちる。要約に案そのものは残るのに理由だけが消えるため、
# 却下したはずの案を実装し始める、失敗した手順を復旧手順として再実行する、
# といった誤動作が起きる。
#   https://qiita.com/hiranuma/items/60cd5dbf642e346f8be7
#
# ## このフックが書くもの / 書かないもの
#
# **シェルスクリプトはモデルの判断を知らない。** ここで保存できるのは
# git の状態のような機械で拾えるものだけである。判断ログはモデル自身が
# 作業中に同じファイルへ追記する（グローバル指示「判断は圧縮の外側に残す」を参照）。
#
# そのため既存の内容は消さない。機械が拾える節だけを差し替え、モデルが
# 書いた節はそのまま残す。
#
# 圧縮はブロックしない。PreCompact は exit 2 でブロックできるが、自動 compact
# を止めると context が溢れたまま進めなくなる。
set -uo pipefail

INPUT="$(cat)"
HOOK_DIR="$(cd "$(dirname "$0")" && pwd)"

# jq を使わない理由は guard-branch-base.sh と同じ。入っていない環境では
# 抽出が空になり、フックが黙って素通りして気づけない。
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
TRIGGER="$(extract trigger)"
TRANSCRIPT="$(extract transcript_path)"

# shellcheck source=./session-state-path.sh
. "$HOOK_DIR/session-state-path.sh"
STATE="$(session_state_path "$CWD")"
mkdir -p "$(dirname "$STATE")" 2>/dev/null || exit 0

# 作業中のリポジトリだけを対象にする。親ディレクトリで起動すると候補が全部
# ヒットするため（実測で 6 件）、transcript から絞る。
REPOS="$(CWD="$CWD" TRANSCRIPT="$TRANSCRIPT" HOOK_DIR="$HOOK_DIR" python3 -c "
import importlib.util, os, pathlib
spec = importlib.util.spec_from_file_location(
    'active_projects', os.path.join(os.environ['HOOK_DIR'], 'active-projects.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
for r in m.git_repos(pathlib.Path(os.environ['CWD']), os.environ.get('TRANSCRIPT', '')):
    print(r)
")" || REPOS=""

collect() {
  printf '## 作業ツリーの状態（自動収集 / trigger=%s）\n\n' "${TRIGGER:-unknown}"
  printf 'cwd: `%s`\n\n' "$CWD"

  [ -n "$REPOS" ] || {
    printf '（作業中のリポジトリを特定できなかった）\n'
    return
  }

  local repo
  while IFS= read -r repo; do
    [ -n "$repo" ] || continue
    local branch status log
    branch="$(git -C "$repo" rev-parse --abbrev-ref HEAD 2>/dev/null)" || continue
    printf '### %s\n\n' "$(basename "$repo")"
    printf -- '- ブランチ: `%s`\n' "$branch"

    status="$(git -C "$repo" status --short 2>/dev/null | head -20)"
    if [ -n "$status" ]; then
      printf -- '- 未コミットの変更:\n\n```\n%s\n```\n\n' "$status"
    else
      printf -- '- 未コミットの変更: なし\n\n'
    fi

    log="$(git -C "$repo" log --oneline -5 2>/dev/null)"
    [ -n "$log" ] && printf -- '- 直近のコミット:\n\n```\n%s\n```\n\n' "$log"
  done <<<"$REPOS"
}

AUTO="$(collect)"

# 既存ファイルからモデルが書いた行をすべて保ち、自動収集の節だけを差し替える。
AUTO="$AUTO" STATE="$STATE" python3 <<'PY'
import os, pathlib

state = pathlib.Path(os.environ["STATE"])
auto = os.environ["AUTO"]
marker = "## 作業ツリーの状態（自動収集"
# モデルは自動収集の節の後ろに箇条書きや見出しを足し、その形は決まっていない。
# 見出しで節の終わりを探すと取りこぼすので、終わりを印で示す。印の中の文は、
# ファイルを読んだモデルが印より前に書き足さないためにある。
end_marker = "<!-- 作業ツリーの状態はここまで。PreCompact フックが毎回書き換えるので、追記はこの行より後ろへ -->"

header = (
    "# セッション状態\n\n"
    "compact で失われる判断と状態を、圧縮の外側に置くためのファイル。\n"
    "「作業ツリーの状態」節は PreCompact フックが毎回書き換える。\n"
    "それ以外の節はモデルが書く。消さないこと。\n\n"
    "## 判断ログ\n\n"
    "採用した案・却下した案・却下理由・順序制約をここへ追記する。\n"
)

existing = ""
if state.is_file():
    try:
        existing = state.read_text(encoding="utf-8")
    except Exception:
        existing = ""


# collect() が節の最後に出しうる行。
legacy_last_lines = ("（作業中のリポジトリを特定できなかった）", "- 未コミットの変更: なし")


def skip_legacy_auto(lines, i):
    """終わりの印が無い自動収集の節を、collect() が出す行の形だけ読み飛ばす。

    返すのは、節の後ろにあるモデルの行の位置。lines を書き換えることがある。
    """
    in_fence = False
    while i < len(lines):
        s = lines[i].rstrip("\r\n")
        # 印の無いファイルは末尾に改行が無く、追記が節の最後の行にくっついていることがある。
        # くっついた機械の部分だけを外して残す。
        if in_fence:
            if s == "```":
                in_fence = False
            elif s.startswith("```"):
                lines[i] = lines[i][3:]
                return i
        elif s == "```":
            in_fence = True
        elif s.startswith("### "):
            following = [l.strip() for l in lines[i + 1 : i + 3] if l.strip()]
            if not (following and following[0].startswith("- ブランチ: `")):
                return i
        elif s in ("", "- 未コミットの変更:", "- 直近のコミット:", *legacy_last_lines) or s.startswith(
            ("cwd: `", "- ブランチ: `")
        ):
            pass
        else:
            for p in legacy_last_lines:
                if s.startswith(p):
                    lines[i] = lines[i][len(p) :]
            return i
        i += 1
    return i


def is_auto_start(lines, i):
    """collect() の出力の始まりか。

    コードブロックの中で引用された見出しを節と取り違えないよう、次の行まで見る。
    フェンスを追って判定すると、閉じ忘れのフェンスがあるたびに節が増えていく。
    """
    if not lines[i].startswith(marker):
        return False
    following = [l.strip() for l in lines[i + 1 : i + 3] if l.strip()]
    return bool(following) and following[0].startswith("cwd: `")


lines = existing.splitlines(keepends=True)
kept_lines = []
i = 0
while i < len(lines):
    if not is_auto_start(lines, i):
        kept_lines.append(lines[i])
        i += 1
        continue
    j = i + 1
    while j < len(lines) and not is_auto_start(lines, j):
        if lines[j].rstrip("\r\n") == end_marker:
            break
        j += 1
    if j < len(lines) and lines[j].rstrip("\r\n") == end_marker:
        i = j + 1
    else:
        i = skip_legacy_auto(lines, i + 1)
kept = "".join(kept_lines).rstrip() or header

# 末尾に改行を付ける。無いと、シェルの >> で足した最初の行が終わりの印にくっつく。
state.write_text(f"{kept}\n\n{auto}\n\n{end_marker}\n", encoding="utf-8")
PY

# 保存したことをユーザーに見せる。黙って動くと、動いていないのか
# 保存するものが無かったのか区別できない。
printf '{"systemMessage":"セッション状態を保存した: %s"}\n' "$STATE"
