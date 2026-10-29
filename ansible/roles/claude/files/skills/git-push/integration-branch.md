# 統合ブランチと detached HEAD

SKILL.md の Step 1 の 2. で、`git branch --show-current` が空（detached HEAD）か、`develop` / `master` / `main`（統合ブランチ）だったときに読む。どちらも中止条件で、1. の未コミットの変更の方針、2. の表の確認、3. の 0 件の終わり方より先に当てる。0 件で止めずに終えるのは、下の「止める前に数える」に当たったときだけである。

## 目次

- 止める理由
- 止める前に数える
- 出す方針
- リモートにまだ無い統合ブランチ
- force push を頼まれたとき
- 作業ブランチへ移す

## 止める理由

detached HEAD では push するブランチが無い（`for-each-ref` は `refs/heads/` を引くことになり、全ブランチの upstream を並べる）。
統合ブランチは、git-workflow のルール 2 が直接の push を禁じており、push を頼まれていても force push でも、リモートにまだそのブランチが無くても例外にしない。

## 止める前に数える

止める前に、push していないコミットを数える。統合ブランチでは `git log --oneline '@{upstream}..HEAD'`（upstream が無いか `[gone]` なら `git log --oneline HEAD --not --remotes`）、detached HEAD では `git log --oneline HEAD --not --remotes` で数える。統合ブランチで upstream と比べるのは、ほかの名前で push 済みのコミットも統合ブランチには残るからである。
0 件で 1. の出力も空なら、移しても push するものが無いので、止めずに 3. の 0 件として終える。force push を頼まれたときは 0 件でも止める（下の「force push を頼まれたとき」）。
統合ブランチで数えた件数は控え、移したら出力の「作業ツリー」節に書く。移した先を push した後に `--not --remotes` で数え直すと、そのコミットが除かれて 0 件になる（Git 2.54.0 で実測）。

## 出す方針

作業ブランチへ移す（下の「作業ブランチへ移す」）か中断で、統合ブランチへ push する選択肢は出さない。
未コミットの変更があっても 1. では聞かず、この確認を先に出す。統合ブランチや detached HEAD でコミットすると git-workflow のルール 2 に反する。未コミットの変更は移った先へそのまま移り、やり直した Step 1 で扱う。

## リモートにまだ無い統合ブランチ

`git remote` が 1 行で、`git ls-remote --exit-code --heads <remote> refs/heads/<branch>` が exit 2（リモートにそのブランチが無い）なら、まだリモートに無い統合ブランチの初回の push なので、ユーザーが手で行う旨を push 節の理由に添え（`— push しない（統合ブランチ main のため。リモートに main が無く、初回の push は手で行う）`）、推奨する方針を中断にする。対話時は確認の文にも同じことを書く。`git remote` が 2 行以上なら添えない。
upstream で決めないのは、`git remote add` と `git fetch` の後もリモートにブランチがあるのに upstream は空のままだからである。`refs/heads/` を付けるのは、`main` だけだと `feature/main` のように末尾が一致するブランチでも exit 0 になるためである（どちらも Git 2.54.0 で実測）。

## force push を頼まれたとき

push するコミットが 0 件でも止める。そのとき 0 件なら、作業ブランチへ移す方針は出さない。移した先も 0 件で終わり、使わないブランチが残る。
force push はユーザーが手で行う旨を理由に添え（`— push しない（統合ブランチ main のため。force push は手で行う）`）、出す方針はユーザーが手で force push するか中断にして、推奨を中断にする。

## 作業ブランチへ移す

今の HEAD から切る。未コミットの変更もそのまま移る。

```bash
git switch -c <作業ブランチ> HEAD --no-track
```

- git-branch のルール 3 の (a)(b) とルール 7 の確認は踏まない。ほかのベースから切ると手元のコミットを置いていき、(b) の `git pull --rebase` は手元のコミットを付け直す。未コミットの変更は持ち込み、やり直した Step 1 で扱う
- 名前は git-workflow のルール 1 で決め、候補は `git show-ref --verify --quiet refs/heads/<名前>` が失敗する（まだ無い）名前から出す。対話時は候補を Step 1 の確認の選択肢に入れ、別に聞かない。ユーザーが入力した名前が既にあれば `git switch -c` が exit 128 になるので、`-C` で上書きせず聞き直す
- git-branch のルール 3 の (d) は流さない。ベースを選んでいないので `<base-ref>` が無い。`git branch --show-current` が新しいブランチであることだけを確かめる。移したコミットは、やり直した Step 1 の 3. に並ぶ
- 統合ブランチに残った手元のコミットはこの skill では消さない（消すのは git-workflow のルール 6 の要承認操作）
- 移したら Step 1 からやり直す
