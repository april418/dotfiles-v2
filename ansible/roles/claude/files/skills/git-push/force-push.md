# force push を頼まれたとき

SKILL.md の「force push について」の意味で force push を頼まれたら、Step 1 に入る前に読む。ここの手順は、SKILL.md の Step 1〜3 の該当箇所に差し込んで使う。

## 目次

- 統合ブランチと detached HEAD
- 非対話モード
- 対話モード
  - Step 1 の 2.: push 先の先端を取る
  - Step 1 の 3.: 消えるコミットと足すコミット
  - 答えを使い回す範囲
  - Step 3: push コマンド

## 統合ブランチと detached HEAD

統合ブランチ（`develop` / `master` / `main`）と detached HEAD への force push は、どのモードでも Step 1 の 2. で止める。push するコミットが 0 件でも止める。止め方は integration-branch.md にある（`git branch --show-current` が空か統合ブランチなので、SKILL.md の案内でそちらも読んでいる）。以降の節は、作業ブランチへの force push にだけ当てる。

## 非対話モード

作業ブランチへの force push も、要求されていても行わない（git-workflow のルール 0）。Step 1 の 2. で中止条件として扱い、チェックは流さない。1. の未コミットの変更の方針、2. の表の確認、3. の 0 件の終わり方より先に当てる。未コミットの変更があっても 1. の方針は出さずにここで止め、未コミットの変更は検出内容として伝える。
push するコミットが 0 件でも止める。巻き戻す force push は新しいコミットが無くてもリモートを変える。チェックを流さないのは、push しないと決まっていて、その結果が使われないためである。

push 節は `— push しない（非対話では force push を行わないため）` にし、出す方針は次の 3 つにする。

1. 対話で force push を頼み直す（推奨。Auto Mode なら切ってから、subagent なら呼び出し元の対話セッションで頼む。Auto Mode のままでは同じところで止まる）
2. ユーザーが手で force push する（`git push --force-with-lease --force-if-includes <remote> <branch>`）
3. 中断

頼み直せば、消えるコミットを見てから承認でき、push 先の先端が承認したときのままでなければ上書きしない。手で打つコマンドは sha を渡せないので、`--force-if-includes` を付けて、fetch しただけで手元のブランチに一度も入っていない先端を拒否させる（`(remote ref updated since checkout)` で exit 1。amend や巻き戻しの後は通る。Git 2.54.0 で実測）。
コマンドの `<remote>` は、remote の名指しがあればその remote、無ければ upstream の remote、どちらも無く `git remote` が 1 行ならその remote にする。決まらなければ `<remote>` のまま書き、push 先の remote を確かめてから打つよう添える。2. の表より先に止めるので push 先は決まっておらず、推測した remote に他人のブランチがあると、fetch 済みなら `--force-with-lease` だけでは上書きし、`--force-if-includes` を足すと拒否する（どちらも Git 2.54.0 で実測）。

## 対話モード

作業ブランチへの force push は、push 先から消えるコミットを見せて `AskUserQuestion` で承認を取ってから行う（git-workflow のルール 6）。チェックは通常の push と同じく流す（push 先に残るのは HEAD である）。

### Step 1 の 2.: push 先の先端を取る

表の行で push 先の remote が決まったら、どの行でも、SKILL.md の「追跡 ref の残りの確認」の 2 つのコマンドより先に `git fetch <remote>` を流し、`ls-remote` は `rev-parse` によらず流す。fetch もその 2 つと同じく、同じ回の Step 1 の中では同じ remote に 1 回だけ流す。その後 `for-each-ref` を流し直して表を引き直す。表の行の数え方と確認は、下の「Step 1 の 3.」を当ててから使う。3. で push 先から消えるコミットを見せるには、push 先の今の先端とそのコミットが要る。`ls-remote` が先端の sha を出し、fetch がそのコミットを手元に持ってくる。`pushurl` で push 先を分けた remote では、push 先にしか無いコミットは fetch で手元に来ず、3. の手元に無いときの終わり方になる（Git 2.54.0 で実測）。
fetch が失敗したら、消えるコミットを見せられないので聞かずに終える（`— push しない（<remote> を fetch できなかったため。<git が出した最初の fatal: の行>）`）。

### Step 1 の 3.: 消えるコミットと足すコミット

0 件の判定より先に当てる。2. の `ls-remote` の結果で決める。
exit 0 なら、出力の先頭の sha（タブの前）で、push 先から消えるコミットと足すコミットを並べる。

```bash
git log --oneline HEAD..<sha>   # push 先から消えるコミット
git log --oneline <sha>..HEAD   # 足すコミット
```

`<remote>/<branch>` と書かないのは、同じ名前のローカルブランチがあると `refname is ambiguous` の警告だけでそちらを読むためである（Git 2.54.0 で実測）。
sha のコミットが手元に無いと `fatal: Invalid revision range` で exit 128 になる（`--single-branch` の clone など、fetch の refspec に入らないブランチ。Git 2.54.0 で実測）。消えるコミットを見せられないので、2 本目を流さず、聞かずに終える（`— push しない（<remote> の <branch> のコミットが手元に無く、消えるコミットを見せられないため）`）。
消えるコミットが 1 件以上なら、sha を控え、2 つの一覧を見せて `AskUserQuestion` で force push するか中断するかを聞く（git-workflow のルール 6）。表の行に確認があれば（upstream と違う remote の `-u`）同じ確認で聞く。push 対象のコミットは足すコミットで、表の行の数え方（SKILL.md の 3. の `git log` と、remote-tracking.md の「聞く前に数える」）は使わない。足すコミットが 0 件でも 0 件として終えない。巻き戻す force push（`git reset --hard HEAD~1` の後など）は足すコミットが無く `@{upstream}..HEAD` も空になるが、push 先からコミットを消す（Git 2.54.0 で実測）。
force push すると答えたら、表の行で決まった push コマンドに `--force-with-lease=refs/heads/<branch>:<控えた sha>` を足したものに決まる（`git push -u --force-with-lease=refs/heads/feature/x:<sha> origin feature/x`）。
exit 2（push 先にブランチが無い）か、消えるコミットが 0 件なら、上書きするものが無く force は要らない。表の行と SKILL.md の 3. の数え方のとおりに数え、force を付けずに push する。

### 答えを使い回す範囲

force push の承認は、やり直した Step 1 の 2. の `ls-remote` が出した sha が、承認したときに控えた sha と同じ間だけ使う。違えば見せた一覧と lease に渡す sha が変わるので、聞き直す。

### Step 3: push コマンド

```bash
git push --force-with-lease=refs/heads/<branch>:<控えた sha> <remote> <branch>
```

表の行が `-u` 付きなら `-u` も付ける。push 先の `<branch>` が控えた sha のままなら上書きし、承認の後にほかの人が push したかブランチを消したなら ` ! [rejected]        <branch> -> <branch> (stale info)` で exit 1 になる（Git 2.54.0 で実測）。聞き直さずに、push コマンドが失敗した行で終える。
`--force` は使わない。sha を渡さない `--force-with-lease` は remote-tracking ref と比べるので、承認の後に fetch が走ると、見せていないコミットまで上書きする（`git push --help`）。`--force-if-includes` は、sha を渡した lease と一緒では効かないので付けない（同）。
