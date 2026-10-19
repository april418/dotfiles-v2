#!/usr/bin/env bash
# ==================================================
# 作業ブランチからのベース未指定な派生をブロックする
# ==================================================
# git switch -c / git checkout -b にベースを指定しないと、現在の HEAD から
# 分岐する。作業ブランチ上でこれを実行すると、そのブランチのコミットを
# 引き連れた新ブランチができる。
#
# 厄介なのは、そうなってもブランチ名も差分も正しく見えることである。
# PR を作るまで表面化せず、説明文に書いていないコミットがレビューされない
# ままマージされる事故につながる (2026-08-07 に発生)。
#
# git-branch skill のルール 3 (b) にベースの取得・更新を明記しているが、
# 文章だけでは防げない。機械的に止める。
#
# ブロックするのは「現在が作業ブランチ (feature/* / hotfix/*) で、かつ
# ベースが未指定」の場合のみ。統合ブランチ上での派生は通す。
# 未コミット変更をそのまま持ち込む経路 (git-branch skill ルール 3 (b) 例外 1) も
# ベースを明示するので通る。git switch -c <new> <base> は未コミット変更を保ったまま
# 切り替え、変更のあるファイルの中身が HEAD とベースで違うときは何も変えずに拒否する。
#
# 仕様: PreToolUse フックは exit 2 でツール実行をブロックし、stderr の内容が
# ブロック理由としてモデルへ渡る。
#   https://code.claude.com/docs/en/hooks.md
set -uo pipefail

INPUT="$(cat)"

# JSON の取り出しに jq を使わない。環境によっては入っておらず、その場合
# 抽出が空になって**フックが黙って素通りする**。防御が無効になったことに
# 気づけないため、依存を持たない実装にする (実際にこれで一度無力化した)。
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

COMMAND="$(extract tool_input.command)"
CWD="$(extract cwd)"

[ -n "$COMMAND" ] || exit 0

# git switch -c <name> / git checkout -b <name> を拾う。
# -c/-b の後ろのトークン数を数え、1 個ならベース未指定と判断する。
BRANCH_ARGS="$(printf '%s' "$COMMAND" \
  | grep -oE '\bgit[[:space:]]+(switch[[:space:]]+-c|checkout[[:space:]]+-b)[[:space:]]+[^;&|]*' \
  | head -1 \
  | sed -E 's/.*(switch[[:space:]]+-c|checkout[[:space:]]+-b)[[:space:]]+//')"

[ -n "$BRANCH_ARGS" ] || exit 0

# オプション (-- で始まるもの) を除いた引数の数
ARG_COUNT="$(printf '%s\n' $BRANCH_ARGS | grep -vc '^-' || true)"
[ "$ARG_COUNT" -le 1 ] || exit 0

# 現在のブランチを調べる。git リポジトリでなければ何もしない。
cd "${CWD:-.}" 2>/dev/null || exit 0
CURRENT="$(git rev-parse --abbrev-ref HEAD 2>/dev/null)" || exit 0

case "$CURRENT" in
  feature/*|hotfix/*) ;;
  *) exit 0 ;;   # 統合ブランチ上なら問題ない
esac

cat >&2 <<EOS
ブランチの派生を中止しました。

現在のブランチ: $CURRENT (作業ブランチ)
実行しようとしたコマンド: $COMMAND

ベースを指定していないため、現在の HEAD から分岐します。この作業ブランチの
コミットを新しいブランチが引き連れることになり、PR に無関係な変更が混ざります。
ブランチ名も差分も正しく見えるため、マージするまで気づけません。

対処 (<base-ref> は、ベースがローカルにあり、ほかの worktree でチェックアウトされて
いなければ <base>、それ以外は origin/<base> です。ローカルにあるかは
git show-ref --verify --quiet refs/heads/<base> の成否で、ほかの worktree にあるかは
git for-each-ref --format='%(worktreepath)' refs/heads/<base> の出力が空でないかで分かります):

  1. git-branch skill のルール 3 の (a) でベースを選び、(b) に従って最新化する
       <base-ref> が <base>:        git switch <base> && git pull --rebase origin <base>
       <base-ref> が origin/<base>: git fetch origin

  2. ベースを明示して派生する (--no-track は -c <new-branch> より後ろに置きます)
       git switch -c <new-branch> <base-ref> --no-track

  3. 派生直後に確認する
       git branch --show-current            # <new-branch> であること
       git log --oneline <base-ref>..HEAD   # 空であること

リモートにしか無いベースは git switch <base> でローカルに作らず、origin/<base> のまま使います。
ほかの worktree にあるベースへの git switch <base> は exit 128 で失敗します。
--ignore-other-worktrees で押し通さず、origin/<base> を使います。

未コミット変更がある場合は、1. の代わりに git-branch skill のルール 3 (b) 例外 1
に従います (先にルール 7 で扱いを決めます。pull --rebase はステージ済みか未ステージの
変更があると動きません)。持ち込む場合も 2. で変更は保持されますが、変更のあるファイルの
中身が現在の HEAD とベースで違うと、git は派生を拒否します (ブランチは作られません)。
EOS
exit 2
