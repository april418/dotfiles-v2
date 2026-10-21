---
name: git-pr
description: PR の作成とマージに関するルール。gh pr create の前に含まれるコミットを説明文と突き合わせる手順、マージしてよいかの承認規律、merge commit 形式でのマージ、gh pr merge --delete-branch が worktree ごとにローカルで行うことと打つ前の確認（積んだ PR の base の付け替えを含む）、マージ直後のベース追従（linked worktree を含む）とマージ済みブランチの掃除。gh pr create / gh pr merge を実行する前と、PR がマージされた直後に参照する。共通ルールは git-workflow skill にある。
---

# 概要

PR の作成とマージは、ユーザーが明示的に要求した場合のみ行う
（`git-workflow` のルール 0 の終端表とルール 9）。要求された場合はこの skill に従う。

このファイルにあるルールは 11 だけである。ほかの番号は `git-workflow` の振り分け表で
持ち主を引く。

## ルール 11: PR の作成とマージ

### PR 作成前の内容確認（省略不可）

**`gh pr create` の前に、PR に含まれるコミットを列挙して説明文と突き合わせる。**

```bash
git log --oneline <base-ref>..HEAD
```

`<base-ref>` は git-workflow の `<base-ref>` 定義表で決めた参照。PR の base に指定する予定の
ブランチと同じものを使う（別のブランチと比べると検証の意味がなくなる）。
PR の base は、ブランチを切るときと同じ git-branch のルール 3 (a) の手順で選ぶ。

確認すること。

- **説明文に書いていないコミットが混ざっていないか**
- 意図した変更だけか（ベースの取り違えで無関係なコミットを引き連れていないか）

混ざっていた場合、**そのまま `gh pr create` を実行してはいけない。**
ここで一度止めて、**git-recovery のルール 10** の復旧手順に従う。

PR 本文には **含まれるコミットを列挙する欄を必ず設ける**。
突き合わせの相手が本文に無いと、この確認は形だけになる。

これが要るのは、ブランチ派生時の取り違えが**PR を出すまで表面化しない**ため。
差分もブランチ名も正しく見えるので、説明文を書いている最中も気づけない。

実際の事故: 直前の作業ブランチから新ブランチを切ってしまい、
無関係なコミットを含んだ PR を作成した。説明文には新しい変更のことしか
書かなかったため、**別の変更がレビューされないままマージされた**（2026-08-07）。
そのマージによって元の PR も自動的に「マージ済み」となり、
レビューの機会が完全に失われた。

### PR マージの承認規律（戦略よりも先に必ず確認）

PR のマージは取り消しが難しく、CI/CD 経由でデプロイまで連鎖しうる操作である。
そのため「マージしてよいか」の判定は以下に従う。

- **承認は PR 単位・都度**: 「マージして」はその発話が指す PR に限る。
  過去の承認や別 PR への承認を流用しない。
- **曖昧な回答は承認ではない**: `AskUserQuestion` の選択肢に対して
  選択肢外の形（素の URL・断片・別話題）で返答が来た場合、それは
  「対象はこれだ」という**情報提供**であり実行承認ではない。
  マージ等の実行前に「この PR をボクがマージしてよいか」を改めて確認する。
- **他人が author の PR は特に慎重に**: AI 自身が作成した PR 以外を
  マージすることは、作者やチームのレビューフローを飛ばす行為になる。
  その PR を名指しした明示要求がない限りマージしない。
- **検証の質は実行権限の代わりにならない**: diff 精読・CI green・
  依存の実在確認をどれだけ丁寧に行っても、無許可マージの正当化にはならない。
  「内容が正しいか」と「実行してよいか」は別の判断である。

背景: 実際に「どう進める？」への回答が PR の URL 提示だけだったのを
推奨案の承認と誤読し、チームメンバー author の PR を無断マージして
デプロイまで発火させ、ユーザーの信頼を損ねた事例がある（2026-07-10）。

※実行系アクション全般（デプロイ・公開・外部送信など git 以外を含む）の
承認原則はグローバル指示「曖昧な回答は承認ではない」節が正本である。
本節はその原則を git / GitHub 操作（PR マージ）へ適用した詳細規律の正本である。

### PR マージ時の戦略（明示要求があった場合のみ適用）

ユーザーがマージを要求した場合は **必ず merge commit 形式** を使う。
**併せて `--delete-branch` でリモートブランチを消す。**

```bash
gh pr merge <number> --merge --delete-branch
```

`--delete-branch` はマージ済みのリモートブランチを削除し、ローカルブランチも削除しようとする
（ローカルでどこまでやるかは下の「`gh pr merge` を打つ前」の表）。
マージ済みブランチを残すと、次に切るときに古いものを選ぶ余地が生まれる。
削除してもマージコミットから復元できるので不可逆ではない。
この削除はマージの名指しに含まれる。別に承認を取らない。

`--squash` / `--rebase` は使用しない。理由:

- マージ履歴が残るため、後で「どの PR でこの変更が入ったか」を `git log --first-parent` で辿れる
- 個別コミットの粒度（git-commit skill で revert 可能性最優先に設計したもの）を保てる
- squash は粒度を潰し、rebase は merge commit のメタ情報（PR 番号への参照等）を失わせる

ユーザーが明示的に `--squash` / `--rebase` を指示した場合のみ従う。
その場合は、リスクを警告した上で実行する。

git-workflow のルール 8（ローカルでの `git merge` 禁止）と矛盾しないこと:

- **ローカルブランチの統合**: `git rebase`（git-workflow のルール 8）
- **リモート PR のマージ**: `gh pr merge --merge`（このルール）

両者は対象が異なる。

### `gh pr merge` を打つ前（省略不可）

`--delete-branch` を付けると、gh はマージの後、リモートのブランチを消す前に、ローカルでも
git を動かす。何をするかは、PR の head（作業ブランチ）をどの worktree がチェックアウトして
いるかと、gh を打つ場所で決まる（gh v2.102.0 の `pkg/cmd/pr/merge/merge.go` の
`deleteLocalBranch`）。`git worktree list` で各 worktree のブランチが分かり、1 行目が
main worktree である。ローカルに `<head>` が無ければ、gh はローカルで何もしない。

| head をチェックアウトしている worktree | gh を打つ場所 | gh がローカルで行うこと |
| --- | --- | --- |
| どこにも無い | どこでも | `git branch -D <head>` |
| main worktree | その worktree | `git checkout <base>`（ローカルに無ければ `git checkout -b <base> --track origin/<base>`）→ `git pull --ff-only origin <base>` → `git branch -D <head>`。`<base>` がほかの worktree にあれば、警告を出して何もしない |
| main worktree | linked worktree | 警告を出して何もしない |
| linked worktree | その worktree | 警告を出して何もしない |
| linked worktree | ほかの worktree | `git worktree remove -- <head の worktree>` → `git branch -D <head>` |

打つ前に次の 4 つを確かめる。

1. **head がほかの linked worktree にあるなら、その worktree で打つ。** ほかの worktree から
   打つと、gh はその worktree を `git worktree remove` で消す。変更や未追跡ファイルがあれば
   拒否されてローカルの削除を飛ばすが、無ければ `.gitignore` で無視されたファイルごと消える。
   その worktree は、ほかのセッションの作業場所であることが多い。その worktree で打てば、
   gh はローカルに触れない。移るのはそのコマンドの間だけにする。

   ```bash
   (cd <head の worktree> && gh pr merge <number> --merge --delete-branch)
   ```

   その worktree に残るブランチは、その worktree が head を離れた後、次にマージしたときの
   一括削除（「マージ済みのローカルブランチは残さない」）で消える。最終応答に、残って
   いることを書く。
2. **push していないコミットが無いこと。** ローカルに `<head>` があれば、`git fetch origin`
   の後に `git log --oneline origin/<head>..<head>` が空であることを確かめる。マージされるのは
   リモートの head までで、gh の `git branch -D` はその先のコミットも消し、どのブランチからも
   辿れなくなる。PR を番号で指定すると、gh はローカルとのずれを警告しない。空でなければ
   マージせず、ユーザーに伝える。
3. **自分の worktree で head をチェックアウトしているなら、未コミット変更が無いこと。**
   `git status --porcelain --untracked-files=normal` に出力があれば、git-branch のルール 7 を踏む（選択肢は「表の例外」）。
   コミットしても push しなければマージに入らず、2. の条件を満たさなくなる。持ち込むと、main worktree では
   gh が `git checkout <base>` で変更を `<base>` へ移すか、checkout が拒否されて、リモートの
   ブランチを消さないままエラーで止まる。linked worktree では gh は触れないが、直後の追従で
   同じルール 7 を踏むので、ここで済ませる。stash は
   `git stash push -u -m "<head>: <退避した変更の内容>"` で取る。gh がマージせずに止まったら、
   head の上で `git stash list` からメッセージで探し、`git stash pop stash@{N}` で戻す。
   マージまで進んだら、最終応答に、stash した変更がマージした PR に入っていないことも書く。
4. **この PR の head を base にしている open な PR（積んだ PR）が無いこと。** あれば、先に
   その PR の base をこの PR の base へ付け替える。`--delete-branch` で head を消すと、
   GitHub は積んだ PR を付け替えずに閉じる（2026-10-20 に `gh pr merge --delete-branch` で実測。
   付け替えると書いた 2020 年の changelog とは違った）。

   ```bash
   gh pr list --base <head> --state open --json number,title,author
   gh pr edit <積んだ PR の番号> --base <この PR の base>
   ```

   付け替えはこのマージの名指しに含める。`--delete-branch` の削除と同じく、名指しされた
   マージで積んだ PR を閉じないための操作である。ただし積んだ PR の author が自分（AI が
   作ったもの）でなければ、付け替えずに止めてユーザーに確認する。マージの後に、積んだ PR が
   `gh pr view <番号> --json state,baseRefName` で OPEN かつ付け替え先を向いていることを確かめる。

   閉じられてしまったら、消えたブランチをマージ前の SHA でリモートに作り直し
   （`git push origin <SHA>:refs/heads/<head>`）、`gh pr reopen` → `gh pr edit --base` の後に
   作り直したブランチを消す。PR の番号を残すにはこの順しかない。

stdout が端末でないと、gh はマージの成功もブランチの削除も出力せず、警告とエラーだけを出す
（`infof` は `IsStdoutTTY()` のときだけ書く）。exit が 0 以外でも、マージは済んでいることがある。
再実行せずに `gh pr view <number> --json state` で確かめる。`{"state":"MERGED"}` で、
`git ls-remote --exit-code --heads origin <head>` が exit 0（head がリモートに残っている）なら、
`git push origin --delete <head>` で消す。マージの名指しに含まれる削除なので、下の
「リモートに残ったマージ済みブランチ」の、名指しがある場合に当たる。

### マージした直後にベースを最新へ戻す（省略不可）

**マージが完了したら、その場でベースブランチへ戻して追従させる。**
作業ブランチに留まったままにしない。

誰がマージしたかによらない。自分が `gh pr merge` したときも、ユーザーが
「マージした」と伝えてきたときも、次の作業に入る前にこの手順を踏む。

ただし、この手順を踏むのは、自分の worktree がマージした head をチェックアウトしていたとき、
統合ブランチか detach した HEAD にいるとき、またはセッションの開始時に作られたブランチ
（デスクトップアプリの `claude/<名前>` など）の上にいて `git log --oneline <base-ref>..HEAD` が
空のときである。開始時のブランチから追従したなら、そのブランチも直後の一括削除で消える。
ほかの作業ブランチの上にいるなら、
`git fetch --prune origin` だけにしてそのブランチに留まる。そのブランチの作業はまだ終わっていない。
下の「マージ済みのローカルブランチは残さない」の一括削除も流さない（理由はその節）。

切り替えの前に git-branch のルール 7（未コミット変更の扱い）を踏む。この場面では
「そのまま持ち込む」を選べない（git-branch のルール 7 の「表の例外」）。stash を選んだら
`git stash push -u -m "<元のブランチ>: <退避した変更の内容>"` で退避してから切り替える。
マージの前に stash していれば、ここでは何も出ない。

切り替え方は `<base-ref>`（git-workflow の定義）で変わる。切り替えた後は、git-branch の
ルール 3 (d) の「直前の操作」の表で確かめる。

```bash
# <base-ref> が <base> の場合
git switch <base>
git pull --rebase origin <base>

# <base-ref> が origin/<base> の場合（ベースがほかの worktree にあるか、リモートにしか無い）
git fetch --prune origin
git switch --detach origin/<base>
```

linked worktree で作業していると、`<base>` は main worktree でチェックアウトされている
ことが多く、後者になる。ほかの worktree の `<base>` を、その worktree で pull して更新
しない。その worktree の作業ツリーを動かすことになる。

gh が作業ブランチのローカル削除を飛ばしたとき（上の表の「警告を出して何もしない」行）は、
警告が勧める手順（`git worktree remove`、ほかの worktree の切り替え、`git branch -D`）に
従わない。worktree を消すか、ほかの worktree の作業ツリーを動かすことになり、`-D` は
未マージのコミットも黙って消す（git-workflow のルール 6）。自分の worktree が head をチェックアウト
していたなら、切り替えた後の一括削除（下の「マージ済みのローカルブランチは残さない」）で消える。
ユーザーが squash / rebase でマージした head は `--merged` に出ず、ほかの worktree がチェックアウト
している head は `+` の行として除かれるので、どちらも一括削除で消えない。扱いは同じ節の
一括削除の結果の項にある。

stash した変更は `<base>` の上でも、detach した HEAD の上でも pop しない。どちらも次に
切るブランチの起点で、そこにある未コミット変更は、次に切るブランチへ持ち込む前提で
扱われる（git-branch のルール 7 の表の 1 行目）ので、別件が混ざりうる。次の作業で
使うなら、そのブランチを切った後に git-branch のルール 3 (b) 例外 1 の pop の表で決める。
使わないまま作業を終えるなら、最終応答に退避したときのメッセージと、戻し方（作業ブランチを
切ってから `git stash list` でメッセージから番号を探し、`git stash pop stash@{N}` する）を書く。

**マージ済みのローカルブランチは残さない。** ベースへ追従した直後に、毎回下のコマンドで
まとめて消す。マージした head のほかに、次のものもベースに取り込まれていれば消える。

- セッションの開始時に作られ、使われずに残ったブランチ（デスクトップアプリの `claude/<名前>` など）。作業は git-branch のルール 3 で切ったブランチで進めるので、開始時のブランチにはコミットが載らない
- 前にマージしたとき、ほかの worktree がチェックアウトしていて消せなかった head

追従の直後に限るのは、`-d` の判定の相手がブランチで違うためである。upstream が残っていれば
その upstream、upstream が無いか追跡先が消えた（`gone`）ブランチは HEAD に取り込まれているかで
判定する。マージした head は `fetch --prune` の後たいてい `gone` になるので、HEAD がその
ブランチを含んでいないと（マージより前に切った作業ブランチの上など）`not fully merged` で
拒否される（Git 2.54.0 で実測）。追従の直後なら、
`--merged <base-ref>` と `-d` が比べる HEAD が同じコミットを指す。

```bash
# リモートで消えたブランチの remote-tracking ref を落とす
git fetch --prune origin

# 追跡先が消えたローカルブランチを拾う
git branch -vv | grep ': gone]'

# ベースにマージ済みのローカルブランチをまとめて消す
git branch --merged <base-ref> | grep -vE "^[*+]|^\s*(main|master|develop)$" | xargs -r git branch -d
```

**`grep -v "^\*"` だけでは足りない。** ローカルに `<base>` があれば、
`git branch --merged <base-ref>` の出力には**たいてい `<base>` 自身が含まれる**
（`<base-ref>` そのものか、`<base-ref>` にマージ済みだから）。`*` は現在いる
ブランチにしか付かない。追従したベース自身は `*` か `+` で外れるが、ほかの統合ブランチ
（develop に追従したときの、どこでもチェックアウトされていない master など）は名前でしか
守られない。統合ブランチ名を明示的に除外すること。

ほかの worktree でチェックアウトされているブランチには `+` が付く。`-d` はそれを消せない
ので、`+` の行も除外する。除外しないと `+` をブランチ名として渡してしまい、
`error: branch '+' not found` が出て exit 1 になる。

**実際の失敗**: この規則を書いた直後に自分で実行し、`master` を削除した。
`feature/*` 上にいたため `*` はそちらに付いており、`master` が除外されな
かった（2026-08-10）。`git branch master origin/master` で復旧できたが、
**規則として書いたコマンドを検証せずに流した**のが誤りだった。

`-d` は未マージのものを拒否するので安全で、git-workflow のルール 6 の `-D`（未マージの
強制削除）とは別物である。ローカルの掃除に承認は要らない。

一括削除の結果は次のように扱う。

- `Deleted branch <名前> (was <SHA>)` の行は、最終応答にそのまま書く。自前のコミットが無いブランチも消えるので、要るものがあれば `git branch <名前> <SHA>` で戻せるようにする
- `-d` が拒否したもの（`not fully merged`、`used by worktree`）は、git の hint に従って `-D` で消さない。`-D` は git-workflow のルール 6 の要承認操作なので、一括削除の流れでは使わない。拒否があるとパイプラインの exit は 0 以外になるが、ほかのブランチは消えている。stderr に `fatal:` が出ていたら、`<base-ref>` の取り違えなどで何も消えていない
- マージした head と、`: gone]` に出たブランチのうち、一括削除で消えなかったものは消さずに最終応答に書く。ほかの worktree がチェックアウトしている（`+`）、squash / rebase でマージされた、追従したのとは別のベースへマージされた、マージされずに閉じた PR のもの、push していないコミットがある、などが当たる。消したいものがあれば、ユーザーに確かめてから `-D` を使う

**リモートに残ったマージ済みブランチは、名指しか承認を得てから消す。** ユーザーが
マージした場合や、GitHub 側で自動削除されない場合に残る。通常 push と違い、
頼まれた作業の成果物ではないものをリモートで消す操作なので、マージ後の掃除として
自分の判断では消さない（auto mode もこれを止める）。

- ユーザーがそのブランチの削除を名指ししているなら、確認せずに実行する
- 名指しが無く対話時なら、`AskUserQuestion` で消してよいか確認する
- 名指しが無く非対話時なら、実行せず、最終応答で次のコマンドを示して終える
- auto mode に止められたら、回避せずにコマンドを示して終える

```bash
git push origin --delete <branch>
```

`git push --delete` はコミットを送らないので、git-push skill（push 前の品質チェック）は通さない。

マージした head が `git ls-remote --exit-code --heads origin <head>` で exit 0（リモートに
残っている）なら、リポジトリの `delete_branch_on_merge`（マージした PR の head を GitHub が消す
設定）を `gh api 'repos/{owner}/{repo}' --jq .delete_branch_on_merge` で確かめる（`{owner}` と
`{repo}` は gh が今のリポジトリで埋める）。

| 値 | すること |
| --- | --- |
| `true` | 設定は変えない。残っている head は上の箇条のとおりに扱う |
| `false` | `gh api -X PATCH 'repos/{owner}/{repo}' -F delete_branch_on_merge=true` でオンにすることも提案する。リポジトリの設定を変える操作なので、ユーザーの承認を得てから流す |
| `null` | このトークンでは設定を読めない（read 権限だけのリポジトリで実測）。提案せず、設定を変えられる人に頼むよう最終応答に書く |

**古い状態からブランチを切ると、無駄なマージ作業が発生しうる。** git-branch のルール 3(b)
は「派生直前に更新する」と定めているが、それだけでは足りない。マージから次の
派生までの間に手元が遅れたままになり、その間に作った作業ブランチが古いベースを
指す。

**「ファイルが無い」「変更が反映されていない」と判断する前に、ブランチのずれを
疑う。** マージ済みの変更は `origin/<base>` にあっても手元には無い。

```bash
git branch --show-current
git status -sb | head -1        # ## main...origin/main [behind N] が出ていないか
```

**実際の失敗**: PR をマージした後も、その PR より前に切った作業ブランチに
留まり続けた。手元の `main` は 9 コミット遅れており、マージ済みのはずの
`.env.example` が作業ツリーに存在しなかった。ユーザーから「雛形ないけど？」と
指摘されるまで気づかなかった（2026-08-10）。

## チェックリスト

- [ ] **PR を作る前に** `git log --oneline <base-ref>..HEAD` を**説明文と突き合わせた**か？
      （※こちらの合格条件は「空」ではなく「説明文と一致」。同じコマンドだが
      タイミングも期待値も違う）
      （書いていないコミットが混ざったまま出すと、レビューされずにマージされる）
- [ ] PR をマージする場合、**その PR を名指しした明示要求**があるか？
      （曖昧な回答・URL 提示だけでは承認ではない。他人 author の PR は特に）
- [ ] PR マージ時は `--merge --delete-branch` を使っているか？
      （merge commit 形式で、リモートのブランチを消す。ローカルは gh が飛ばすことがある）
- [ ] **マージの前に** 4 つを確かめたか？
      （head がほかの linked worktree にあるならそこで打つ。
      `git log --oneline origin/<head>..<head>` が空。
      自分の worktree が head をチェックアウトしているなら未コミット変更が無い。
      head を base にしている積んだ PR があれば、先に base を付け替える）
- [ ] gh の exit が 0 以外のとき、再実行せずに `gh pr view <number> --json state` を見たか？
- [ ] **マージした後、`<base-ref>` に合わせてベースへ戻したか？**
      （マージした head の上か、統合ブランチか detach した HEAD、または `<base-ref>..HEAD` が
      空の開始時のブランチ（`claude/<名前>` など）にいたときだけ。
      ほかの作業ブランチの上なら `fetch` だけにして留まる。
      `<base>` なら `switch` と `pull --rebase`、`origin/<base>` なら `fetch` と `switch --detach`。
      作業ブランチに留まると手元が遅れ、次に切るブランチが古いベースを指す。
      ユーザーがマージした場合も同じ。未コミット変更は持ち込まない。
      stash したなら `<base>` でも detach した HEAD でも pop しない）
- [ ] **追従した直後に、マージ済みのローカルブランチをまとめて消したか？**
      （使われなかった `claude/*` なども消える。ほかの作業ブランチの上では流さない。
      拒否されたものを `-D` で消さず、消したものと残ったものを最終応答に書く）
- [ ] リモートに残ったマージ済みブランチを、名指しも承認も無しに消していないか？
      （残っていたら `delete_branch_on_merge` を確かめ、`false` ならオンにすることも提案する）
- [ ] 「ファイルが無い」と言う前に `git status -sb` で `behind` を確認したか？
