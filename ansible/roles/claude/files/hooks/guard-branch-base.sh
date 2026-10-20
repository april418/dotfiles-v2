#!/usr/bin/env bash
# ==================================================
# 作業ブランチからのベース未指定な派生をブロックする
# ==================================================
# git switch -c / -C、git checkout -b / -B、git worktree add -b / -B にベースを
# 指定しないと、現在の HEAD から分岐する。-b を付けない git worktree add <path> も、
# <path> の basename のブランチが無ければ、その名前で HEAD から作る。作業ブランチ上で
# これらを実行すると、そのブランチのコミットを引き連れた新ブランチができる。
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

# 解析器の不具合が無関係なコマンドに及ばないよう、どの語も無いものは解析しない。
case "$COMMAND" in
  *switch*|*checkout*|*worktree*) ;;
  *) exit 0 ;;
esac

# 解析に失敗したら exit 1 で通す (PreToolUse の exit 1 はブロックしない)。python3 は
# .py が見つからないと exit 2 で終わるので、終了コードをそのまま返さない。
HOOK_DIR="$(cd "$(dirname "$0")" && pwd)"
BRANCHES="$(printf '%s' "$COMMAND" | python3 "$HOOK_DIR/guard-branch-base-parse.py" "${CWD:-.}")" || exit 1

# 統合ブランチ上、detach した HEAD、git リポジトリの外なら問題ない
CURRENT=""
while IFS= read -r branch; do
  case "$branch" in
    feature/*|hotfix/*) CURRENT="$branch"; break ;;
  esac
done <<< "$BRANCHES"
[ -n "$CURRENT" ] || exit 0

WORKTREE_NOTE=""
case "$COMMAND" in
  *"worktree add"*) WORKTREE_NOTE="
-b を付けない git worktree add <path> も、<path> の末尾と同じ名前のブランチが無ければ、
その名前のブランチを HEAD から作ります。既にあるブランチを開くなら
git worktree add <path> <branch> と、ブランチを指定します。同じコマンドの前のほうで
git を実行しているか、git の前に環境変数の代入や env を書いているときは、ブランチが
あるかを確かめずに止めています (実行した後の状態はフックの時点では分かりません)。
" ;;
esac

cat >&2 <<EOS
ブランチの派生を中止しました。

現在のブランチ: $CURRENT (作業ブランチ)
実行しようとしたコマンド: $COMMAND

ベースを指定していないため、現在の HEAD から分岐します。この作業ブランチの
コミットを新しいブランチが引き連れることになり、PR に無関係な変更が混ざります。
ブランチ名も差分も正しく見えるため、マージするまで気づけません。
${WORKTREE_NOTE}
対処 (<base-ref> は、ベースがローカルにあり、ほかの worktree でチェックアウトされて
いなければ <base>、それ以外は origin/<base> です。ローカルにあるかは
git show-ref --verify --quiet refs/heads/<base> の成否で、ほかの worktree にあるかは
git for-each-ref --format='%(worktreepath)' refs/heads/<base> の出力が空でないかで分かります):

  1. git-branch skill のルール 3 の (a) でベースを選び、(b) に従って最新化する
       <base-ref> が <base>:        git switch <base> && git pull --rebase origin <base>
       <base-ref> が origin/<base>: git fetch origin

  2. ベースを明示して派生する (-C / -B で切り直すときも <base-ref> を付けます)
       git switch -c <new-branch> <base-ref> --no-track
       git worktree add --no-track -b <new-branch> <path> <base-ref>   # worktree を作る場合

  3. 派生直後に確認する (worktree を作った場合は git -C <path> で打ちます)
       git branch --show-current            # <new-branch> であること
       git log --oneline <base-ref>..HEAD   # 空であること

リモートにしか無いベースは git switch <base> でローカルに作らず、origin/<base> のまま使います。
ほかの worktree にあるベースへの git switch <base> は exit 128 で失敗します。
--ignore-other-worktrees で押し通さず、origin/<base> を使います。

未コミット変更がある場合は、1. の代わりに git-branch skill のルール 3 (b) 例外 1
に従います (先にルール 7 で扱いを決めます。pull --rebase はステージ済みか未ステージの
変更があると動きません)。持ち込む場合も 2. で変更は保持されますが、変更のあるファイルの
中身が現在の HEAD とベースで違うと、git は派生を拒否します (ブランチは作られません)。

cd の移動先が実行時まで決まらない ("\$X" など) か、まだ無いディレクトリ (git init や
git clone の直後など) のときは、cd する前の場所で判定しています。移動先で派生するなら、
cd と派生を別のコマンドに分けて打ちます (git init の直後なら git init -b <new-branch> でも足ります)。
EOS
exit 2
