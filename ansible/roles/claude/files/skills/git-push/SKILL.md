---
name: git-push
description: リモートへの push 前に品質チェック（build, lint, test, audit 等）を実行し、安全にプッシュする。プロジェクトのツールチェインを自動検出してチェックを行う。
---

# 概要

- このスキルはリモートブランチへの push を行う。
- push 前にプロジェクト固有の品質チェックを自動検出・実行する。
- すべてのチェックに通過した場合のみ push を実行する。

## 実行モードと AskUserQuestion

本スキルは、流すチェックの一覧にも通常の push にも承認を取らない（`[gone]` のブランチを作り直すかは下の表の 1 行目で聞く）。対話で頼まれた force push だけは、表の 2 行目で承認を取る。Step 1 を通った時点で未コミット変更は無く push 先も 1 つに決まっており、作業ブランチへの通常の push（force を伴わない）は後から打ち消せる（git-workflow のルール 0）。
チェックを外すのは push を頼む指示か、下の 4 場面で聞いた確認への答えで行う（「流さないチェックの書き方」）。

`AskUserQuestion` で聞くのは次の 4 つの場面だけである。**非対話モード**（subagent 実行、CI、Auto Mode 等、ユーザーへの問い合わせができないコンテキスト）では、右の列のとおりにする。

| 場面                                                                                                                                                                                                                                             | 対話モード                                                                                               | 非対話モード                                                                                         |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| Step 1 で確認が要るか中止条件を検出した（未コミット変更、push 先の remote が決まらない、名指しの remote が upstream の remote と違う、upstream が `[gone]`（追跡 ref の残りを含む。Step 1 の 2.）、detached HEAD、統合ブランチ、remote が 0 行） | 検出内容を伝え、次に取りうる方針を聞く                                                                   | 下の段落                                                                                             |
| 作業ブランチへの force push を頼まれ、Step 1 の 3. で push 先から消えるコミットがある                                                                                                                                                            | 消えるコミットと足すコミットを見せ、force push するか中断するかを聞く（git-workflow のルール 6）         | 起きない（Step 1 の 2. で止める）                                                                    |
| Step 2 で Node.js の PM が見つからない（PATH の PM の node を指定と照らして合わず、nvm にも合う版が無いときを含む。照らさずに流す場面は当たらない）                                                                                              | PM の場所を聞く（node が合わないときは、合う node か PM の場所）                                         | Node.js のチェックを失敗にする（「PATH 解決のフォールバック」と「PATH で見つけた PM の node の版」） |
| Step 3 でチェックが追跡ファイルを書き換えた                                                                                                                                                                                                      | コミットしてから push し直すか、中断するかを聞く（チェックが作った未追跡のファイルがあれば、その扱いも） | 同じ選択肢を最終応答で提示する                                                                       |

非対話モードで Step 1 の中止条件を検出した場合（未コミット変更あり / detached HEAD / 統合ブランチ / upstream が `[gone]`（追跡 ref の残りを含む） / push 先の remote が決まらない / 名指しの remote が upstream の remote と違う / force push を頼まれた 等）は、push は実行せず、検出内容と次に取りうる方針（コミット / `.gitignore` か `.git/info/exclude` に足す / stash / 作業ブランチへ移す / push 先の remote の指定 / 対話で force push を頼み直す / ユーザーが手で force push する / 中断等）を最終応答で 2〜4 択で提示する。
upstream が `[gone]`、名指しの remote が upstream の remote と違う、detached HEAD、統合ブランチでも、push するコミットが 0 件ならどのモードでも聞かず、0 件として終える（detached HEAD と統合ブランチは、未コミットの変更も無いとき。Step 1 の 2.）。
ただし統合ブランチと detached HEAD で force push を頼まれたときと、非対話で作業ブランチへの force push を頼まれたときは、0 件でも止める（「force push について」）。
対話で作業ブランチへの force push を頼まれ、push 先から消えるコミットがあるときも、0 件で終えずに承認を聞く（Step 1 の 3.）。

確認への答えは、Step 1 からやり直した後も使い、同じことを聞き直さない（外したチェック、push 先の remote、`-u` で付け替えるか、`[gone]` のブランチを push するか、PM か node の場所）。やり直した手順はそのまま流し、聞く場面に来たら、聞く代わりに前の答えを使う。
force push の承認は、やり直した Step 1 の 2. の `ls-remote` が出した sha が、承認したときに控えた sha と同じ間だけ使う。違えば見せた一覧と lease に渡す sha が変わるので、聞き直す。

**チェックが 1 つでも失敗したら、どのモードでも push しない。** 失敗内容を報告して終える（「失敗時の優先規則」）。

## ワークフロー

### Step 1: 現在の状態を確認

```bash
git status --porcelain --untracked-files=normal
```

```bash
git branch --show-current
```

```bash
git for-each-ref --format='%(upstream:short) %(upstream:track)' "refs/heads/$(git branch --show-current)"
```

```bash
git remote
```

以下を確認する:

1. **未コミットの変更がないこと** — 上の `git status --porcelain --untracked-files=normal` の出力が空であること。未追跡のファイル（`??`）も未コミットの変更に数える。
   チェックは作業ツリーを読むので、push しないファイルのせいでチェックが通ったり落ちたりする（新しく足したファイルの `git add` し忘れは、手元で通って CI で落ちる）。
   `--short` ではなく `--porcelain` を使うのは、設定の `status.branch=true` で `--short` が clean でも `## <branch>` の行を出すため。`--untracked-files=normal` は `status.showUntrackedFiles=no` でも `??` を出すために付ける（どちらも Git 2.54.0 で実測）。`.gitignore` などで無視されたファイルは出ないので数えない。
   未コミットの変更がある場合は `AskUserQuestion` でユーザーに報告し、先にコミットするか stash するか確認する。片付くまで push は行わない。
   ただし今のブランチが統合ブランチか detached HEAD（2.）なら、1. では聞かず、2. の確認（作業ブランチへ移す / 中断）を先に出す。統合ブランチや detached HEAD でコミットすると git-workflow のルール 2 に反する。未コミットの変更は移った先へそのまま移り、やり直した Step 1 で扱う。
   非対話で作業ブランチへの force push を頼まれたとき（2.）も、1. の方針は出さずに 2. で止め、未コミットの変更は検出内容として伝える。
   未追跡のファイルには無視する選択肢も出す。生成物は `.gitignore` に足してコミットする（git-commit skill。このコミットも push 対象に入る）。`.gitignore` を書き換えただけでは ` M .gitignore` が残る。自分だけが作るファイル（メモなど）は `.git/info/exclude` に足す（コミットは要らない）。
   ロックファイル（Step 3 の「チェックが作った未追跡のファイル」の段落で決めたもの）には `.gitignore` の選択肢を出さず、コミットするか `.git/info/exclude` に足すかを出す。
   stash は `git stash push -u -m "<branch>: git-push の前に退避 (<退避したパス>)"` にする。`-u` が無いと未追跡のファイルを退避せず、未追跡のファイルだけのときは `No local changes to save` と出して exit 0 で終わる（Git 2.54.0 で実測）。メッセージにパスを入れるのは、同じ文言の stash が 2 つ並ぶと `git stash list` で見分けられないため。
   片付けたら Step 1 からやり直す。stash は push の後も戻さず、退避したときのメッセージと戻し方を出力の「作業ツリー」節に書く。戻さないのは、チェックが作り直したファイルとパスが重なると、pop が一部だけ戻して exit 1 になり stash も残るためである。
2. **push 先のリモート・ブランチ** — まず `git branch --show-current` が空でないことを確かめる。
   空なら detached HEAD で push するブランチが無いので、中止条件として扱う（`for-each-ref` は
   `refs/heads/` を引くことになり、全ブランチの upstream を並べる）。
   `develop` / `master` / `main` なら統合ブランチで、これも中止条件として扱う。git-workflow のルール 2 は
   統合ブランチへの直接の push を禁じており、push を頼まれていても force push でも、リモートにまだその
   ブランチが無くても例外にしない。`git remote` が 1 行で、`git ls-remote --exit-code --heads <remote> refs/heads/<branch>`
   が exit 2（リモートにそのブランチが無い）なら、まだリモートに無い統合ブランチの初回の push なので、ユーザーが
   手で行う旨を push 節の理由に添え（`— push しない（統合ブランチ main のため。リモートに main が無く、初回の push は手で行う）`）、
   推奨する方針を中断にする。対話時は確認の文にも同じことを書く。upstream で決めないのは、`git remote add` と
   `git fetch` の後もリモートにブランチがあるのに upstream は空のままだからである。`refs/heads/` を付けるのは、
   `main` だけだと `feature/main` のように末尾が一致するブランチでも exit 0 になるためである（どちらも Git 2.54.0
   で実測）。`git remote` が 2 行以上なら添えない。
   detached HEAD と統合ブランチで出す方針は、作業ブランチへ移す（下の「作業ブランチへ移す」）か中断で、
   統合ブランチへ push する選択肢は出さない。
   止める前に、push していないコミットを数える。統合ブランチでは `git log --oneline '@{upstream}..HEAD'`
   （upstream が無いか `[gone]` なら `git log --oneline HEAD --not --remotes`）、detached HEAD では
   `git log --oneline HEAD --not --remotes` で数える。統合ブランチで upstream と比べるのは、ほかの名前で
   push 済みのコミットも統合ブランチには残るからである。0 件で 1. の出力も空なら、移しても push する
   ものが無いので、止めずに 3. の 0 件として終える。force push を頼まれたときは 0 件でも止める（「force push について」）。
   そのとき 0 件なら、作業ブランチへ移す方針は出さない。移した先も 0 件で終わり、使わないブランチが残る。
   force push はユーザーが手で行う旨を理由に添え（`— push しない（統合ブランチ main のため。force push は手で行う）`）、
   出す方針はユーザーが手で force push するか中断にして、推奨を中断にする。
   統合ブランチで数えた件数は控え、移したら出力の「作業ツリー」節に書く。移した先を push した後に
   `--not --remotes` で数え直すと、そのコミットが除かれて 0 件になる（Git 2.54.0 で実測）。
   どちらでもなく、非対話で force push を頼まれたときも、ここで中止条件として扱う（「force push について」）。
   1. の未コミットの変更の方針、下の表の確認、3. の 0 件の終わり方より先に当てる。
      どれでもなければ `for-each-ref` の出力、`git remote` の行数、remote の名指しで決める。
      `for-each-ref` の出力は前後の空白を除いてから表に当てる。upstream が無いと空白 1 文字の
      行になり、これが表の「空」である。upstream との差が無いときも `origin/<branch> ` と
      末尾に空白が付く（どちらも Git 2.54.0 で実測）。

   **remote の名指し**は、push を頼んだ指示が push 先の remote を名前で指定していること（「fork に push して」、`/git-push fork` の引数など）。
   指示として数えるのは、対話時と Auto Mode ではユーザーの発言、subagent ではタスクの指示文、CI ではジョブが渡したプロンプトである。skill の引数は、1 語のときだけ名前として比べる（2 語以上なら一致しないものとして扱う）。push 先の remote を聞く確認（名指しが `git remote` のどれとも一致しない、2 行以上で名指しが無い）でユーザーが答えた remote も名指しに数え、表を引き直す。エージェントが自分で選んで skill の引数に入れた名前は数えない。
   名前は `git remote` の出力の各行と完全一致で比べる。どれとも一致しなければ、`git remote` が 0 行なら表の最終行で中止し、1 行以上なら表には当てはめず `AskUserQuestion` でユーザーに push 先を確認する。表の「名指し」はすべて一致したものである。

   | upstream（`for-each-ref` の出力）                                                                                                                         | `git remote` | remote の名指し                 | push 先                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
   | --------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------ | ------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
   | 同名のリモートブランチ（`<remote>/<branch>`。`[ahead N]` / `[behind N]` / `[ahead N, behind N]` が続いてよい。`[gone]` で終わるものは下の `[gone]` の行） | —            | 無い、または upstream の remote | `git push <remote> <branch>`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
   | 同名のリモートブランチ（末尾が `[gone]` のものを含む）                                                                                                    | —            | upstream と違う remote          | 聞く前に、3. のコミットを `git log --oneline HEAD --not --remotes=<名指しの remote>` で数える。`@{upstream}..HEAD` は upstream の remote との差で、upstream の remote に push 済みなら 0 件になって push せずに終わる（Git 2.54.0 で実測）。`[gone]` では下の行のとおり使えない。0 件なら聞かずに 3. の 0 件として終える。1 件以上なら `AskUserQuestion` で確認する。`-u` で upstream を名指しの remote へ付け替えるかが決まらない（付け替えずに push すると upstream は変わらない）。答えで `git push -u <名指しの remote> <branch>` か `git push <名指しの remote> <branch>` に決まる                                                                                                                                                                                                      |
   | 末尾が `[gone]`（upstream のリモートブランチが消えた）                                                                                                    | —            | 無い、または upstream の remote | 聞く前に、3. のコミットを `git log --oneline HEAD --not --remotes=<upstream の remote>` で数える（`@{upstream}` は解決できず exit 128 になる）。0 件なら聞かずに 3. の 0 件として終え、理由に `[gone]` を添える（`— push しない（push するコミットが無いため。upstream の origin/feature/x は [gone]）`）。merge commit でマージされたブランチはここで終わる。1 件以上なら `AskUserQuestion` で確認する。PR がマージ済みでブランチが消された可能性があり（squash でマージされたブランチは 1 件以上残る）、push するとマージ済みのブランチを作り直す（git-pr のルール 11「マージした直後にベースを最新へ戻す」を見る）。push すると答えたら `git push <upstream の remote> <branch>` に決まる。upstream の設定は残っており、push で追跡が戻るので `-u` は要らない（どれも Git 2.54.0 で実測） |
   | 空（upstream が無い）、または名前の違うブランチ                                                                                                           | 1 行         | 無い、またはその remote         | **初回 push として扱い、`git push -u <remote> <branch>` で確定とみなす**                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
   | 空、または名前の違うブランチ                                                                                                                              | 2 行以上     | ある                            | **初回 push として扱い、`git push -u <名指しの remote> <branch>` で確定とみなす**                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
   | 空、または名前の違うブランチ                                                                                                                              | 2 行以上     | 無い                            | `AskUserQuestion` でユーザーに push 先を確認する                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
   | —                                                                                                                                                         | 0 行         | —                               | push 先が無い。中止条件として扱う                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |

   `origin/<base>` から切ったブランチは upstream が `origin/<base>` になる（名前の違う
   ブランチ）。そのままでは引数なしの `git push` が名前の不一致で拒否され、`-u` を付けずに
   push すると upstream がベースを指したまま残るので、初回 push として `-u` で付け替える。

   表の行が 1 行目か upstream と違う remote の行に決まったら、その行の数え方と確認より先に、次の 2 つで push 先の追跡 ref が
   リモートで消されたブランチの残りでないかを確かめる。ほかの行では、残りがあっても数え方も確認も変わらないので流さない。
   同じ回の Step 1 の中では、同じ remote には 1 回だけ流す（Step 1 からやり直したときは流し直す）。

   ```bash
   git rev-parse --verify --quiet refs/remotes/<remote>/<branch>
   git ls-remote --exit-code --heads "$(git remote get-url --push <remote>)" refs/heads/<branch>
   ```

   `ls-remote` は `rev-parse` が exit 0（追跡 ref がある）のときだけ流す（force push は下の段落）。`ls-remote` に remote の名前を渡すと
   fetch の URL を見るので、`pushurl` で push 先を分けた remote では、この skill が push して作った追跡 ref まで残りに見える。
   `get-url --push` は `pushurl` と `pushInsteadOf` を当てた URL を出す。
   `rev-parse` が exit 0 で `ls-remote` が exit 2（push 先にブランチが無い）なら、その追跡 ref はリモートで消されたブランチの残りである。
   fetch しても `fetch.prune` が無効（git の既定）ならその ref は消えず、通常の push はここまで fetch もしないので、`for-each-ref` は `[gone]` を
   出さない（`[ahead 1]` などが付くか、差が無ければ何も付かない）。upstream がその ref なら、upstream を `[gone]` として表を引き直す。1 行目の
   まま push すると、リモートで消されたブランチを確認なしで作り直す（`* [new branch]` で exit 0）。`[gone]` の行の 0 件の理由は、`[gone]` を
   `リモートで消された（追跡 ref は残っている）` に替えて書く。`git branch -vv` などは gone を出さない。
   `[gone]` として引いた行と upstream と違う remote の行では、`--not --remotes=<remote>` で数えるところを
   `git log --oneline HEAD --not --exclude=<remote>/<branch> --remotes=<remote>` にする。残りを除かないと、その ref にあるコミットが数えられず、
   push 先に無いのに 0 件で終わる。`--exclude` の値に `refs/remotes/` を付けると何も除かない。初回 push の行では（force push で残りが
   分かったときも）除かない。除くと、`-u` を付けずに push してマージされたブランチが 1 件以上になり、確認なしで作り直す。
   残りを `[gone]` として引いたとき、fetch していなければほかの追跡 ref もマージより前のままなので、merge commit でマージしたブランチの
   コミットも数え、`[gone]` の行の 0 件では終わらずに作り直すかを聞く（どれも Git 2.54.0 で実測）。確認には、マージ済みのコミットも並びうる
   ことを添える。数えすぎても確認か中止に倒れるだけなので、これを避けるための fetch はしない。
   `ls-remote` が exit 2 以外の 0 でない終了なら、push 先にブランチがあるかが分からないので、聞かずに終える
   （`— push しない（<remote> の <branch> を ls-remote で確かめられなかったため。<git が出した最初の fatal: の行>）`）。3. の fetch の失敗と同じく
   中止条件に数えない。

   対話で作業ブランチへの force push を頼まれたときは、表の行で push 先の remote が決まったら、どの行でも、上の 2 つより先に
   `git fetch <remote>` を流し、`ls-remote` は `rev-parse` によらず流す。fetch も上の 2 つと同じく、同じ回の Step 1 の中では
   同じ remote に 1 回だけ流す。その後 `for-each-ref` を流し直して表を引き直す。表の行の数え方と確認は、3. の
   「force push を頼まれたとき」を当ててから使う。3. で push 先から消えるコミットを見せるには、push 先の今の先端とそのコミットが要る。`ls-remote` が先端の sha を出し、fetch が
   そのコミットを手元に持ってくる。`pushurl` で push 先を分けた remote では、push 先にしか無いコミットは fetch で手元に来ず、3. の
   手元に無いときの終わり方になる（Git 2.54.0 で実測）。fetch が失敗したら、消えるコミットを見せられないので聞かずに終える
   （`— push しない（<remote> を fetch できなかったため。<git が出した最初の fatal: の行>）`）。

   **作業ブランチへ移す**ときは、今の HEAD から切る。未コミットの変更もそのまま移る。

   ```bash
   git switch -c <作業ブランチ> HEAD --no-track
   ```

   - git-branch のルール 3 の (a)(b) とルール 7 の確認は踏まない。ほかのベースから切ると手元のコミットを置いていき、(b) の `git pull --rebase` は手元のコミットを付け直す。未コミットの変更は持ち込み、やり直した Step 1 で扱う
   - 名前は git-workflow のルール 1 で決め、候補は `git show-ref --verify --quiet refs/heads/<名前>` が失敗する（まだ無い）名前から出す。対話時は候補を Step 1 の確認の選択肢に入れ、別に聞かない。ユーザーが入力した名前が既にあれば `git switch -c` が exit 128 になるので、`-C` で上書きせず聞き直す
   - git-branch のルール 3 の (d) は流さない。ベースを選んでいないので `<base-ref>` が無い。`git branch --show-current` が新しいブランチであることだけを確かめる。移したコミットは、やり直した Step 1 の 3. に並ぶ
   - 統合ブランチに残った手元のコミットはこの skill では消さない（消すのは git-workflow のルール 6 の要承認操作）
   - 移したら Step 1 からやり直す

3. **push 対象のコミット** — 差分コミット一覧をユーザーに表示する。push するコミットが 0 件の場合は「push するコミットがない」旨を伝えて終了する。
   対話で作業ブランチへの force push を頼まれたときは、0 件の判定より先に、この項の最後の「force push を頼まれたとき」を当てる。
   0 件は中止条件に数えない。取りうる方針が無いので、どのモードでも聞かず、選択肢も出さない。2. の表で push 先に同名のブランチがあると決まっていない行（upstream と違う remote、初回 push）で 0 件なら、
   `git ls-remote --exit-code --heads "$(git remote get-url --push <remote>)" refs/heads/<branch>` を流す（2. の表の後の段落で流していれば、その結果を使う）。exit 2 のときだけ、リモートに
   ブランチが無いことを理由に添える（`— push しない（push するコミットが無いため。origin に feature/x が無く、ブランチだけ作るなら手で push する）`）。
   0 件でも push しないのは、base から切ったばかりのブランチは base より先のコミットが無く、GitHub の PR 作成 API が
   `No commits between <base> and <branch>` で拒否するためである。0 件は push 先の remote に無いコミットの数で、base との差ではない
   （push 済みのブランチから切ったブランチは、0 件でも base より先のコミットを持つ）。

   ```bash
   git log --oneline '@{upstream}..HEAD'             # 表の 1 行目（upstream の remote へ push する）
   git log --oneline HEAD --not --remotes=<remote>   # ほかの行（初回 push、[gone]、upstream と違う remote）。<remote> は push 先
   ```

   `@{upstream}..HEAD` を引用符で囲むのは、囲まないと `Bash(git log:*)` の allow があっても規則で通らず、auto mode では
   classifier に回るためである。回ったのは `@{...}` と `..` が 1 つの語に並ぶ形（`HEAD..@{u}` も）で、`@{upstream}` や
   `stash@{0}` だけなら囲まなくても通った（Claude Code 2.1.304 で実測）。

   初回 push で `git log -5` のように件数で区切ると、自分のコミットが 0 件でもベースの
   コミットが並び、0 件を判定できない。`--not --remotes=<remote>` はその remote のどのブランチにも
   無いコミットだけを出す。2. で追跡 ref の残りがあると分かったときは、初回 push の行を除き、2 本目に `--exclude=<remote>/<branch>` を足す（2. の表の後の段落）。
   数える前に `git for-each-ref --count=1 refs/remotes/<remote>/` が空なら、`git fetch <remote>` する（2. で fetch した remote には流さない）。
   一度も fetch していない remote には remote-tracking ref が無く、何も除かれずに push 済みのコミットまで
   並ぶ（`git remote add` しただけの remote で、Git 2.54.0 で実測）。2. で残りがあると分かった remote では、`--exclude=refs/remotes/<remote>/<branch>` を
   足して見る。fetch せずに push しただけの remote は残りだけで空にならず、数える側で残りを除くと push 済みのコミットまで並ぶ。
   `for-each-ref` の `--exclude` は `log` と逆で、`refs/remotes/` から書かないと何も除かない（どれも Git 2.54.0 で実測）。fetch が失敗したら、push 済みのコミットを
   除けず数えられないので、聞かずに終える（`— push しない（<remote> を fetch できなかったため。<git が出した最初の fatal: の行>）`）。
   0 件と同じく中止条件に数えない。

   **force push を頼まれたとき**（対話の作業ブランチ）は、2. の `ls-remote` の結果で決める。
   exit 0 なら、出力の先頭の sha（タブの前）で、push 先から消えるコミットと足すコミットを並べる。

   ```bash
   git log --oneline HEAD..<sha>   # push 先から消えるコミット
   git log --oneline <sha>..HEAD   # 足すコミット
   ```

   `<remote>/<branch>` と書かないのは、同じ名前のローカルブランチがあると `refname is ambiguous` の警告だけでそちらを読むためである（Git 2.54.0 で実測）。
   sha のコミットが手元に無いと `fatal: Invalid revision range` で exit 128 になる（`--single-branch` の clone など、fetch の refspec に
   入らないブランチ。Git 2.54.0 で実測）。消えるコミットを見せられないので、2 本目を流さず、聞かずに終える
   （`— push しない（<remote> の <branch> のコミットが手元に無く、消えるコミットを見せられないため）`）。
   消えるコミットが 1 件以上なら、sha を控え、2 つの一覧を見せて `AskUserQuestion` で force push するか中断するかを聞く
   （git-workflow のルール 6）。表の行に確認があれば（upstream と違う remote の `-u`）同じ確認で聞く。push 対象のコミットは
   足すコミットで、表の行の数え方（上のコードブロックと、表の「聞く前に数える」）は使わない。足すコミットが 0 件でも 0 件として
   終えない。巻き戻す force push（`git reset --hard HEAD~1` の後など）は足すコミットが無く `@{upstream}..HEAD` も空になるが、
   push 先からコミットを消す（Git 2.54.0 で実測）。
   force push すると答えたら、表の行で決まった push コマンドに `--force-with-lease=refs/heads/<branch>:<控えた sha>` を足したものに
   決まる（`git push -u --force-with-lease=refs/heads/feature/x:<sha> origin feature/x`）。
   exit 2（push 先にブランチが無い）か、消えるコミットが 0 件なら、上書きするものが無く force は要らない。表の行と上の数え方の
   とおりに数え、force を付けずに push する。

### Step 2: プロジェクトの品質チェックを自動検出・実行

プロジェクトルートのファイル構成からツールチェインを自動検出し、
利用可能なチェックを順に実行する。

#### 検出ロジック

以下の種別をすべて調べ、当てはまった種別はすべて対象にする（最初に当てはまった種別で止めない）。チェックを流す順は節の並び（Node.js → Python → Rust → Go → Ansible → Docker → Makefile → Taskfile）で、種別の中は表の行の順（Makefile / Taskfile は `lint` → `check` → `test` → `build` の順）である。

表の条件の「`<ツール>` がインストール済み」は次のとおりに判定する。入っていなければ「流さないチェックの書き方」のスキップ行にする。

| ツール                                                | 判定                                                                                   | 流すコマンド                                                                                      |
| ----------------------------------------------------- | -------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| Python の表（`ruff` / `mypy` / `pytest`）             | プロジェクトルートの `.venv/bin/<ツール>` が実行可能か。無ければ `command -v <ツール>` | `.venv/bin/<ツール>` で見つけたら、表のコマンドの先頭をそのパスにする（`.venv/bin/ruff check .`） |
| `clippy` / `cargo-audit`                              | `cargo clippy --version` / `cargo audit --version` が exit 0 か                        | 表のとおり                                                                                        |
| ほか（`golangci-lint` / `ansible-lint` / `hadolint`） | `command -v <ツール>`                                                                  | 表のとおり                                                                                        |

`.venv/bin` を先に見るのは、uv などがプロジェクトルートに作る `.venv` のツールは、venv を有効にしないと `PATH` に無いため。`PATH` の pytest は自分の環境で動くので、`.venv` に入れたプロジェクトの依存を import できない。
`uv run` は使わない。`.venv` や `uv.lock` が無ければ作り、`pyproject.toml` と食い違う `uv.lock` を書き換える（uv 0.13.1 で実測）。
`clippy` という実行ファイルは無く、`cargo clippy` の実体の `cargo-clippy` は rustup がコンポーネントの有無によらず置く proxy なので、`command -v` では判定できない。

**Node.js プロジェクト（`package.json` が存在）:**

パッケージマネージャー（PM）は上から順に見て、最初に決まったものを使う。

1. `package.json` の `packageManager`（`pnpm@10.33.0` のような値の `@` より前）
2. `package.json` の `devEngines.packageManager` の `name`。配列なら、3 のロックファイルで決まる PM がどれかの `name` に一致すればそれを、一致しないかロックファイルが無ければ先頭の `name` を使う
3. ロックファイル: `bun.lock` / `bun.lockb` → `pnpm-lock.yaml` → `yarn.lock` → `package-lock.json`
4. どれも無ければ `npm`

宣言（1・2）をロックファイルより先に見るのは、宣言と違う PM で流すと止まるからである（npm は `devEngines.packageManager` が他の PM を指すと `EBADDEVENGINES`、pnpm は `packageManager` が、11 以降は `devEngines.packageManager` も他の PM を指すと `This project is configured to use …` で exit 1）。
宣言とロックファイルが食い違っていても宣言の PM で流す。その PM のロックファイルが無いことで audit などが失敗したら、ほかの失敗と同じく push を止める。

下の表の audit 行の `<pm> audit` は、yarn では `yarn --version` のメジャー版で分ける。

- 1: `yarn audit`
- 2・3: `yarn npm audit --all --recursive`
- 4 以上: `yarn npm audit --all --recursive --no-deprecations`

`yarn npm audit` の既定は今いるワークスペースの直接依存だけなので、`--all` と `--recursive` で全ワークスペースの推移的な依存まで見る。4 以上は非推奨のパッケージも moderate として数えて exit 1 になるので、npm / pnpm と同じく脆弱性だけで止まるよう `--no-deprecations` を付ける（このフラグは 4 から）。
yarn 1 の終了コードは見つかった重大度の値の和（info 1 / low 2 / moderate 4 / high 8 / critical 16）で、info だけでも 0 にならず失敗である。
`yarn --version` は audit を流すと決まったときに、audit の直前に流す。0 以外で終わったら audit のコマンドが決まらないので、audit を流さずに `✗ Node.js audit（失敗。yarn --version が exit <N> で終わった）` と書く。
bun は 1.2.15 で `bun audit` が入ったので、それより前の bun では失敗になる。
pnpm 10 以下の `pnpm audit --prod` が `ERR_PNPM_AUDIT_BAD_RESPONSE` の 410 で失敗したら、package-manager skill のルール 5 の手順で pnpm 11 を使って流し直し、その結果で判定する。出力の `Node.js audit` の行には括弧で `pnpm 10 が 410 を返したため pnpm 11 で流し直した` と書き、ルール 5 が報告に添えるよう求めることも同じ括弧に入れる。

**PATH 解決のフォールバック**: 非ログインシェル（subagent の Bash 等）では、nvm 配下やスタンドアロンのインストーラで入れた PM が `PATH` に入っていないことがある。`command -v <pm>` で見つかった場合は、下の「PATH で見つけた PM の node の版」で node の版を照らす。見つからない場合は、下の表の場所を上の行から、行の中は左から順に見て、最初に見つかった実行ファイルを使う。

| PM     | 探す場所                                                                                                                                          |
| ------ | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| すべて | `$NVM_DIR/versions/node/*/bin/<pm>` のうち、プロジェクトが求める Node.js の版に合う最も新しいもの（下の「nvm の版の選び方」）                     |
| pnpm   | `$PNPM_HOME/bin/pnpm`、`$PNPM_HOME/pnpm`（`pnpm setup` が pnpm 11 以降は前者、10 以前は後者に置く。プロジェクトが宣言した版では選ばず、両方見る） |
| bun    | `$BUN_INSTALL/bin/bun`                                                                                                                            |

変数が空なら、各インストーラの既定の場所を使う。

| 変数          | 空のときの場所                                                                                            |
| ------------- | --------------------------------------------------------------------------------------------------------- |
| `NVM_DIR`     | `$XDG_CONFIG_HOME/nvm`（`XDG_CONFIG_HOME` も空なら `~/.nvm`）                                             |
| `PNPM_HOME`   | `$XDG_DATA_HOME/pnpm`（`XDG_DATA_HOME` も空なら macOS は `~/Library/pnpm`、ほかは `~/.local/share/pnpm`） |
| `BUN_INSTALL` | `~/.bun`                                                                                                  |

**nvm の版の選び方**: `bin/<pm>` が実行できる（`test -x`）版だけを候補にする。プロジェクトルートにある次の指定のすべてに合う候補のうち、最も新しい版を使う。中身が空か空白だけの指定は無いものとする。

- `package.json` の `engines.node`
- `.node-version` の中身
- `.nvmrc` の中身

package-manager skill のルール 2 と同じ確認先だが、優先順で 1 つに絞らない。`engines.node` が `>=18` のような下限だけだと、それだけで選んだ版は `.nvmrc` などで固定した版より新しくなりうる。
指定が 1 つも無ければ、候補を `sort -V` で比べて最も新しい版を使う（文字列で比べると `v9` が `v24` より新しくなる）。
指定があれば、合うかを npm が同梱する semver の CLI で決める。`<nvm>` は上の表で決めた `NVM_DIR` の場所で、展開した絶対パスで書く。
`<最新>` は、候補に限らず `<nvm>/versions/node/` の下で `bin/node` が実行でき、`lib/node_modules/npm/node_modules/semver/bin/semver.js` がある（`test -f`）版のうち、`sort -V` で最も新しいもの。候補の版の npm を使わないのは、npm 6 が同梱する semver 5 系の CLI は `bin/semver` で `.js` が無いため（`npm view npm@6.14.18 dependencies.semver` が `^5.7.1`、`npm view semver@5.7.1 bin` が `./bin/semver`）。`<最新>` が無ければ版を比べられないので、合う版が無い扱いにする。
指定は、読んだ値の前後の空白を除いて単一引用符で 1 つずつ `-r` に渡し、続けて候補の版を並べる。ファイルをシェルで読ませない。`"$(cat .nvmrc)"` は cwd が違うと空になり、`-r ''` はすべての版に合う。

```bash
'<nvm>/versions/node/<最新>/bin/node' '<nvm>/versions/node/<最新>/lib/node_modules/npm/node_modules/semver/bin/semver.js' -r '>=18' -r '24' v20.19.0 v24.15.0
```

すべての `-r` に合う版だけを、`v` を外して古い順に出す（この例では `24.15.0`）。最後の行に `v` を付けた版の `bin`（`<nvm>/versions/node/v24.15.0/bin`）が下の `<dir>` になる。合う版が無ければ何も出さずに exit 1 で終わる（semver 7.7.4 / npm 11.12.1 で実測）。0 以外で終わったら合う版が無い扱いにする。
semver の範囲として読めない指定は、どの版にも合わない。nvm は `.nvmrc` の `#` から後ろをコメントとして除き、`lts/*`・`node` などの alias を版に置き換えて読むが、ここではどちらもせずにそのまま `-r` に渡す。指定が無いものとしても扱わない。
合う版が無ければ、nvm の行では見つからなかった扱いにして次の行へ進む。

表の場所で見つけたら、その実行ファイルのあるディレクトリを `<dir>` とし、以降 PM と node を呼ぶコマンド（`yarn --version`、下の表の後の `pnpm config get verifyDepsBeforeRun`、下の表のチェック、pnpm 11 での流し直しとその前の Node.js の版の確認）は `PATH="<dir>:$PATH" <pm> run build` のように `<dir>` を `PATH` の先頭に足して流す。nvm の行は指定に合う版を選ぶが、後ろの行（`PNPM_HOME` / `BUN_INSTALL`）で見つけたときは node の版を指定と照らさない。
corepack が置く pnpm / yarn と npm は `#!/usr/bin/env node` で始まり、フルパスで呼んでも `node` が `PATH` に無いと `env: node: No such file or directory` で exit 127 になる。`<dir>/node <dir>/npm run build` と node をフルパスで呼んでも、scripts の中の `node` が `sh: node: command not found` で落ちる（どちらも npm 11.12.1 / pnpm 12.6.0 で実測）。nvm の `<dir>` にはその版の `node` がある。
シンボリックリンクは辿らない。nvm の `bin/pnpm` などは `../lib/node_modules/` の下へのリンクで、辿った先のディレクトリに `node` は無い。
`node` があるかは確かめない。`<dir>` にも `PATH` にも `node` が無ければ（スタンドアロンの pnpm など）、node を呼ぶチェックは失敗し、ほかの失敗と同じく push を止める。
`<dir>` は展開した絶対パスで書き（引用符の中の `~` は展開されない）、コマンドごとに付ける。Bash の呼び出しの間で環境変数は引き継がれないことがある。
出力では、流した Node.js のチェック（`yarn --version` の失敗で ✗ にした audit も数える）のうち最初の行の括弧の最後に `pnpm が PATH に無いため ~/.nvm/versions/node/v24.15.0/bin を PATH の先頭に足して流した` のように書く（ホームディレクトリは `~` と書く）。括弧にほかの説明（`失敗。`、410 で流し直したことなど）があれば、その後に `。` で区切って続ける。nvm ならパスから node の版が読め、CI と結果が違ったときの手がかりになる。
nvm に候補があったのに合う版が無く、後ろの行かユーザーの答えの `<dir>` で流したときは、`流した` の後に `。nvm は engines.node の >=26 に合う版が無い。pnpm があるのは v24.15.0` のように続ける。`nvm は` の後は、下の `探した場所:` で nvm の場所に添える括弧の中身と同じである。

表の場所でも見つからなければ `AskUserQuestion` でユーザーに PM の場所を確認する。nvm に候補があったのに合う版が無かったときは、下の `探した場所:` で nvm の場所に添える括弧と同じ内容を質問に添える。
答えが実行ファイルならその親を、ディレクトリならそれを `<dir>` にし、表の場所で見つけたときと同じに扱う。答えの `<dir>` の版は指定と照らさない。合わない版で流すかはユーザーが決める。`<dir>/<pm>` が実行できなければ（`test -x`）見つからなかった扱いにして、`<dir>/<pm>` が実行できなかったことを添え、中断を選択肢に入れてもう一度聞く。`bin/` の下などを自分で探しには行かない。
非対話モード時は Node.js のチェックを流さずに失敗とし、push を中止する。出力は、流すはずだった Node.js のチェックのうち最初のものを `✗ Node.js build（失敗。bun が見つからない。探した場所: PATH, ~/.nvm/versions/node/*/bin/bun, ~/.bun/bin/bun）` のように書き、残りの Node.js のチェックは前段失敗の行（`— <チェック名>（前段失敗のため未実行）`）にする。ほかの種別のチェックは、ほかの失敗と同じく「失敗時の優先規則」に従う。
`探した場所:` には、`command -v` を `PATH` と書き、続けて表で見た場所を見た順に `, ` で区切って並べる。変数は展開した値で書き、ホームディレクトリは `~` と書き、glob は展開しない。
nvm に候補があったのに合う版が無かったときは、nvm の場所の後ろに `~/.nvm/versions/node/*/bin/pnpm（engines.node の >=26 に合う版が無い。pnpm があるのは v24.15.0）` のように括弧を付ける。指定は「nvm の版の選び方」の並びの順に `engines.node の >=18 と .nvmrc の 20` のように `と` でつなぎ（値の中の改行は空白 1 つにする）、候補の版は古い順に `, ` で区切って並べる。`<最新>` が無くて比べられなかったときは、括弧の前半を `semver を流せる版が無い` にする（`（semver を流せる版が無い。pnpm があるのは v14.21.3）`）。
`corepack <pm>@latest` で取ってくることはしない。Node.js 25 以降は corepack が同梱されず、`@latest` はプロジェクトが宣言した版を無視するため。
流す Node.js のチェックが 1 つも無ければ（スキップ行だけなら）PM は探さず、見つからなくても失敗にしない。

**PATH で見つけた PM の node の版**: `command -v <pm>` で PM が見つかったら、`node --version` の版を「nvm の版の選び方」の 3 つの指定と照らす。PM によらず 3 つとも照らす。照らさないと、同じプロジェクトでもログインシェルでは PATH の版で、subagent では nvm の行で選んだ版で流れる。PM に任せても揃わない。npm 11.12.1 の `npm run build` は、`engines.node` に合わない版でも `engine-strict=true` のまま exit 0 で流れる。pnpm 12.6.0 の `pnpm run build` は、`engines.node` に合わなければ `engine-strict` が無くても `ERR_PNPM_UNSUPPORTED_ENGINE` で exit 1 になるが、`.nvmrc` と `.node-version` は見ない。
この節の切り替えは package-manager skill のルール 2 の `nvm use` の代わりで、`nvm install` で取ってくることはしない。push 前のチェックのために node を取ってきて `~/.nvm` を書き換えない。

次のどれかに当たれば照らさずに流す。上から見て最初に当たったものを採る。

- 指定が 1 つも無い
- `command -v node` が空か、`node --version` が 0 以外で終わった（上の「`node` があるかは確かめない」と同じく、node を呼ぶチェックの失敗に任せる）
- 「nvm の版の選び方」の `<最新>` が無い。切り替える先も無いので、nvm の無い環境で毎回止めない。注記は `~/.nvm/versions/node に semver を流せる版が無いため、PATH の node v24.15.0 を指定と照らさなかった` のように、探した `<nvm>/versions/node` と PATH の node の版を添える
- 下で外した結果、読める指定が残らない。注記は外した指定の注記だけ

semver の範囲として読めない指定（`lts/*`・`node`・`#` のコメントを含む値など）は外して照らす。合わない扱いにすると、`.nvmrc` が `lts/*` のプロジェクト（nvm 0.40.8 の README が載せる例）は PATH の node にも nvm のどの版にも合わず、毎回失敗する。nvm の行の扱い（どの版にも合わない）は変えない。
読めるかは、指定ごとに次のコマンドを 1 回流し、`null` を出すかで決める。`<指定>` は「nvm の版の選び方」と同じく前後の空白を除いた値である。semver.js の `-r` では決められない。読めない指定も合わない指定も、何も出さずに exit 1 で終わる。

```bash
'<nvm>/versions/node/<最新>/bin/node' -p 'require(process.argv[1]).validRange(process.argv[2])' '<nvm>/versions/node/<最新>/lib/node_modules/npm/node_modules/semver' '<指定>'
```

semver 7.7.4 では `lts/*`・`node`・`24 # pinned` が `null` を出し、読める指定は `>=24.0.0 <25.0.0-0` のような範囲を出す（どちらも exit 0）。0 以外で終わったら、残りの指定には流さず、照らさずに流す。注記は `semver の validRange が exit <N> で終わったため、PATH の node v24.15.0 を指定と照らさなかった` だけにする（それまでに外した指定の注記も書かない）。
外した指定の注記は `.nvmrc の lts/* は semver の範囲として読めないため照らさなかった` のように書く。指定の書き方は `探した場所:` の括弧と同じで、値の中の改行は空白 1 つにし、2 つ以上なら `と` でつないで 1 文にする（`.node-version の node と .nvmrc の lts/* は semver の範囲として読めないため照らさなかった`）。

残った指定を「nvm の版の選び方」と同じく `-r` に渡し、続けて PATH の版を 1 つだけ並べる。exit 0 ならそのまま流す。
0 以外なら、`<nvm>/versions/node/` の下で `bin/node` が実行できる版を同じ `-r` の後ろに並べ、最後の行に `v` を付けた版を選ぶ。nvm の行と違って `bin/<pm>` で絞らない。`<pm>` の無い版でも、PATH の `<pm>` がその版の node で動くからである（`node` だけを置いた版の `bin` を PATH の先頭に足すと、PATH にある pnpm 12.6.0 の corepack のシムはその `node` で起動した）。`corepack enable` はシムを corepack の隣に置くので、nvm では版ごとに `bin/pnpm` があったり無かったりする。選んだ版に `<pm>` があれば、PATH の `<pm>` ではなくそちらが動く（npm は nvm のどの版にもある）。
選んだ版の `bin` を `<dir>` にし、表の場所で見つけたときと同じく PATH の先頭に足して流す。注記は `PATH の node v24.15.0 が .nvmrc の 22 に合わないため ~/.nvm/versions/node/v22.12.0/bin を PATH の先頭に足して流した` のように書く。
注記の `PATH の node … が` の後ろには、PATH の版に合わなかった指定だけを書く。指定ごとに `-r '<指定>'` と PATH の版を 1 つ並べて流し、0 以外で終わったものである。照らした指定をすべて書くと、PATH の版が合っている指定にも合わないように読める。指定のつなぎ方は `探した場所:` の括弧と同じである。

合う版が無ければ、表の場所は見ない。表の後ろの行（`PNPM_HOME` / `BUN_INSTALL`）で PM を見つけても、node は PATH の合わない版のままだからである。
非対話モード時は「表の場所でも見つからなければ」の段落と同じく、Node.js のチェックを流さずに失敗とし、残りの Node.js のチェックを前段失敗の行にする。失敗の行は、`<pm> が見つからない。探した場所: …` の代わりに `PATH の node v24.15.0 が .nvmrc の 22 に合わない。~/.nvm/versions/node/*/bin/node には engines.node の >=20 と .nvmrc の 22 に合う版が無い。node があるのは v20.19.0, v24.15.0` のように書く。`には` の後ろには、照らしたすべての指定を書く。node がある版は古い順に `, ` で区切って並べる。
対話時は、その段落の質問ではなく、失敗の行と同じ内容を添えて、指定に合う node か `<pm>` のある場所を聞く。答えが実行ファイルならその親を、ディレクトリならそれを `<dir>` にし、`<dir>/node` か `<dir>/<pm>` のどちらかが実行できれば（`test -x`）PATH の先頭に足して流す。その段落の `<dir>/<pm>` だけを確かめる手順は使わない。どちらも実行できなければ、それを添え、中断を選択肢に入れてもう一度聞く。答えの版を指定と照らさないことと、`bin/` の下を探しに行かないことは、その段落と同じである。注記は `PATH の node v24.15.0 が engines.node の >=27 に合わず、nvm にも合う版が無いため、答えの /opt/homebrew/opt/node@27/bin を PATH の先頭に足して流した` のように書く。

この節の注記は、流した Node.js のチェックのうち最初の行の括弧に、「表の場所で見つけたら」の段落と同じく、ほかの説明の後に `。` で区切って続ける。パスのホームディレクトリは `~` と書く。外した指定の注記は、この節のほかの注記より前に書く。失敗の行は、`失敗。`、外した指定の注記、上の失敗の文の順になる（`✗ Node.js build（失敗。.nvmrc の lts/* は semver の範囲として読めないため照らさなかった。PATH の node v24.15.0 が engines.node の >=26 に合わない。…）`）。
この節の経路では、「表の場所で見つけたら」の段落の `<pm> が PATH に無いため …` と `nvm は …` の注記は書かない。PM は PATH にあり、nvm の行は見ていない。

| チェック   | 条件                                  | コマンド                                           |
| ---------- | ------------------------------------- | -------------------------------------------------- |
| build      | `scripts.build` が定義されている      | `<pm> run build`                                   |
| lint       | `scripts.lint` が定義されている       | `<pm> run lint`                                    |
| typecheck  | `scripts.typecheck` が定義されている  | `<pm> run typecheck`                               |
| type-check | `scripts.type-check` が定義されている | `<pm> run type-check`                              |
| test       | `scripts.test` が定義されている       | `<pm> run test`                                    |
| audit      | 常に実行                              | `<pm> audit` (`pnpm` の場合は `pnpm audit --prod`) |

`scripts.typecheck` と `scripts.type-check` が両方定義されていれば両方流す。中身が違いうるので、片方だけでは取りこぼす。

**PM が pnpm で、表の `pnpm run` のチェック（audit 以外）を 1 つでも流すなら、その前に `pnpm config get verifyDepsBeforeRun` を 1 回流す。出力が `undefined` なら、`pnpm run` のチェックに `PNPM_CONFIG_VERIFY_DEPS_BEFORE_RUN=false` を前置して流す**（package-manager skill のルール 1 の例外）。`<dir>` を足すときは `PATH="<dir>:$PATH" PNPM_CONFIG_VERIFY_DEPS_BEFORE_RUN=false pnpm run build` と並べる。
pnpm 11 以降はこの設定の既定が `install` で、`pnpm run` が `node_modules` を確かめ、ずれていれば install を流す。依存もロックファイルも無ければ `pnpm-lock.yaml` と `node_modules` を作り、package.json がロックファイルより新しければ `pnpm-lock.yaml` を書き換え、store に無い依存は registry へ取りに行く（11.9.0 は store にあっても supply-chain の検証でメタデータを取りに行く）。registry に届かなければ、12.6.0 は 1 分以上、11.9.0 は約 3 分 30 秒再試行してから exit 1 で終わり、スクリプトは流れない（どれもプロジェクトルートの `pnpm run build` を 11.9.0 / 12.6.0 で実測。10.33.0 は既定が `false` で何もしない）。`pnpm audit` は install を流さない。
切ると、package.json だけ変えてロックファイルを直し忘れたコミットも、手元のチェックは通りうる（既定の install ならロックファイルを書き換え、Step 3 で止まる）。この食い違いは npm と pnpm 10 でも同じで、CI の frozen install が見つける（pnpm は `ERR_PNPM_OUTDATED_LOCKFILE`。11.9.0 / 12.6.0 で `CI=true` の `pnpm run build` が同じエラーで exit 1）。
Makefile / Taskfile のターゲットには前置しない。プロジェクトが定めた入口なので、中の `pnpm run` が作ったり書き換えたりしたファイルは、ほかのチェックが作ったファイルと同じく扱う。
`config get` は、その版の `run` が従う指定の値を、設定ファイルと環境変数のどちらから来たものでも出し、どこにも無ければ `undefined` を出す（10.33.0 / 11.9.0 / 12.6.0 で実測。pnpm-workspace.yaml のキーは camelCase で書いたもの。10.33.0 は kebab-case のキーも出すが `run` は従わず、既定が `false` なので結果は同じ）。`undefined` 以外なら前置せずにその値に従い、環境変数は別に調べない。11.9.0 は環境変数の `error` / `warn` を読まずに install するが、`config get` もそれを出さないので前置され、install は止まる。`config get` が 0 以外で終わったら前置して流す。
`error` と、11.9.0 / 12.6.0 で端末が無いときの `prompt` は、`node_modules` がずれていると `ERR_PNPM_VERIFY_DEPS_BEFORE_RUN` で exit 1 になる。これもほかの失敗と同じく失敗である。10.33.0 の `prompt` は答えを読めず、スクリプトを流さないまま exit 0 で終わる。出力に `Would you like to run "pnpm install"` が出たら、exit 0 でも `✗ Node.js build（失敗。verifyDepsBeforeRun の prompt に答えられず、スクリプトが流れなかった）` のように失敗とする。
CLI の `--config.verify-deps-before-run=false` は使わない。`run build` の後ろに置くとスクリプトの引数になって効かず、ルール 1 が禁止する形そのものでもある。`npm_config_verify_deps_before_run` は 11.9.0 / 12.6.0 が読まない。
前置して流したチェックが失敗し、依存を宣言していて（下の audit の段落に並べた package.json と pnpm-workspace.yaml の欄のどれかが空でない）、プロジェクトルートに `node_modules` が無ければ、失敗の行の括弧の `失敗。` の直後（ほかの注記より前）に `node_modules が無い。pnpm install を流してから push し直す` を続ける（`✗ Node.js build（失敗。node_modules が無い。pnpm install を流してから push し直す）`）。依存のコマンドは `sh: tsc: command not found`（exit 127）で落ち、12.6.0 は 10.33.0 と違って `node_modules` が無いことを知らせない。

**`scripts.test` の値が `npm init` / `pnpm init` の既定の `echo "Error: no test specified" && exit 1` と完全に一致するときは、定義されていないものとして扱う。** package.json 上は `"test": "echo \"Error: no test specified\" && exit 1"` と書かれている。test 行の条件を満たさないので流さず、検出されなかったチェックと同じく push の可否の判定にも入れない。結果の出力には `— Node.js test（scripts.test が npm init の既定のままのためスキップ）` と書き、前段の失敗で打ち切ったときもこの書き方を変えない。
空白やコマンドを足したもの（末尾に `&& jest` を足したもの等）は定義されているものとして流し、0 でない終了コードは失敗である。判定は PM によらない（`npm init` で作ってから別の PM に移したプロジェクトにも残る）。

**ロックファイル（`bun.lock` / `bun.lockb` / `pnpm-lock.yaml` / `yarn.lock` / `package-lock.json` / `npm-shrinkwrap.json`）がどれも無く、`package.json` の `dependencies` / `devDependencies` / `optionalDependencies` / `peerDependencies` / `workspaces` と `pnpm-workspace.yaml` の `packages` もどれも無いか空のときは、audit を流さない。** ロックファイルが無いと、`npm audit` は `ENOLOCK`、`pnpm audit` は `ERR_PNPM_AUDIT_NO_LOCKFILE` で exit 1 になる。依存が無ければ、ロックファイルを作って流しても脆弱性 0 件（exit 0）で終わる。検出されなかったチェックと同じく push の可否の判定には入れず、結果の出力には `— Node.js audit（ロックファイルも依存も無いためスキップ）` と書く。前段の失敗で打ち切ったときもこの書き方を変えない。
ロックファイルが無くても上のどれかが空でなければ流し、ロックファイルが無いことによる失敗も失敗である。ロックファイルを作るコマンド（`npm audit` のエラーが案内する `npm i --package-lock-only`、`pnpm install --lockfile-only` 等）はスキルから流さない（未コミットのファイルが増える）。pnpm 11 以降の `pnpm run` が既定で流す install は、上の `verifyDepsBeforeRun` の段落のとおりに切る。

**Python プロジェクト（`pyproject.toml` / `setup.py` / `setup.cfg` が存在）:**

| チェック   | 条件                        | コマンド       |
| ---------- | --------------------------- | -------------- |
| lint       | `ruff` がインストール済み   | `ruff check .` |
| type-check | `mypy` がインストール済み   | `mypy .`       |
| test       | `pytest` がインストール済み | `pytest`       |

pytest は収集・選択されたテストが 0 件だと exit 5 で終わる。`uv init` 直後、テスト関数の無い `test_*.py` だけのとき、`addopts` の `-m` / `-k` で全件が外れたときがこれに当たる。テストがあっても `testpaths` / `python_files` の設定や全モジュールの `importorskip` で 0 件になれば同じく exit 5 で、区別しない。
**exit 5 は失敗に数えない。** push の可否を決める判定（冒頭の「チェックが 1 つでも失敗したら」、Step 3 の「すべてのチェックに通過したら」）では通過として扱い、出力だけ `— Python test（実行するテストが 0 件のためスキップ。pytest の exit 5: <最終行>）` と書く。`<最終行>` は pytest の最後の行から `=` と所要時間を除いたもの（`no tests ran` / `1 deselected` など）。
exit 5 以外の 0 でない終了コードは失敗である。この扱いは Python の表から流した `pytest` に限る。Makefile / Taskfile のターゲットや `scripts.test` から呼ばれた pytest は、テストが 0 件でもそのツールの終了コードで判定する。それらはプロジェクトが定めた入口なので、その終了コードをそのまま採る。表の `pytest` は skill が選んだコマンドなので、exit 5 の読み方も skill が決めてよい。make の出力と報告の書き方は Makefile / Taskfile の節にある。

**Rust プロジェクト（`Cargo.toml` が存在）:**

| チェック | 条件                             | コマンド                      |
| -------- | -------------------------------- | ----------------------------- |
| build    | 常に実行                         | `cargo build`                 |
| lint     | `clippy` がインストール済み      | `cargo clippy -- -D warnings` |
| test     | 常に実行                         | `cargo test`                  |
| audit    | `cargo-audit` がインストール済み | `cargo audit`                 |

**Go プロジェクト（`go.mod` が存在）:**

| チェック | 条件                               | コマンド            |
| -------- | ---------------------------------- | ------------------- |
| build    | 常に実行                           | `go build ./...`    |
| vet      | 常に実行                           | `go vet ./...`      |
| lint     | `golangci-lint` がインストール済み | `golangci-lint run` |
| test     | 常に実行                           | `go test ./...`     |

**Ansible プロジェクト（`ansible.cfg` または `playbook.yml` が存在）:**

| チェック     | 条件                              | コマンド                                       |
| ------------ | --------------------------------- | ---------------------------------------------- |
| lint         | `ansible-lint` がインストール済み | `ansible-lint`                                 |
| syntax-check | `playbook.yml` が存在             | `ansible-playbook --syntax-check playbook.yml` |

syntax-check はプロジェクトルートの `playbook.yml` にだけ流す。ほかの YAML を playbook とみなすのは推測で、vars やタスクのリストに流すと落ちる。ほかの playbook は ansible-lint に任せる（外せない syntax-check ルールで、見つけた playbook すべてに `ansible-playbook --syntax-check` を流す）。

**Docker プロジェクト（`Dockerfile` または `compose.yml` / `docker-compose.yml` が存在）:**

| チェック       | 条件                                                 | コマンド                        |
| -------------- | ---------------------------------------------------- | ------------------------------- |
| lint           | `Dockerfile` が存在し、`hadolint` がインストール済み | `hadolint Dockerfile`           |
| build          | `Dockerfile` が存在                                  | `docker build --check .`        |
| compose-config | `compose.yml` / `docker-compose.yml` が存在          | `docker compose config --quiet` |

**Makefile / Taskfile（`Makefile` / `Taskfile.yml` が存在）:**

`lint`, `check`, `test`, `build` ターゲットが定義されていれば実行する。

ターゲットから呼ばれた pytest のテストが 0 件だと、make は exit 2 で終わる。最終行は `make: *** [test] Error 5` で、その直前の行は、要約を出す設定なら pytest の要約になる（既定では `=` で囲まれた `no tests ran in 0.00s`、`-q` では囲みが無い。`-qq` では要約が出ず空行。GNU Make 3.81 と pytest 9.1.1 で実測）。これも失敗として push を止める（理由は Python の表の下の段落）。
最終行が `Error 5` で終わり、直前の行が pytest の要約で `passed` / `failed` / `error` / `skipped` のどれも含まない（`no tests ran` / `1 deselected` / `1 warning` など）ときは、失敗の報告に原因と直し方を添える。make の `Error 5` はレシピのどのコマンドが 5 を返しても出るので、要約の行が無ければ添えない。この判定は make の出力の形に合わせたもので、task には当てはめない。

```
- ✗ make test（失敗。pytest の実行するテストが 0 件で exit 5。テストを足すか、0 件を通すなら Makefile 側で `pytest || [ $$? -eq 5 ]` のように exit 5 を成功に変える）
```

#### チェック実行の原則

- **チェック名**: 結果の出力では、表の「チェック」列の前に種別名を付けて `<種別名> <チェック>` と書く（`Node.js build` / `Docker build`）。種別名は各節の見出しの「プロジェクト」より前の語（`Node.js` / `Python` / `Rust` / `Go` / `Ansible` / `Docker`）と `Makefile` / `Taskfile` である。Makefile / Taskfile は種別名を付けず `make <ターゲット>` / `task <タスク>` と書く（`make` / `task` が種別を示し、ターゲット名がそのままチェック名になる）。以下の `<チェック名>` も、各節のスキップ行も、この名前である。
  build / lint / test などは複数の表にあり、`package.json` と `Dockerfile` が両方あると `✗ build（失敗）` ではどちらの build か読めない。種別が 1 つのときも付けるのは、検出した数で書式を変えず、1 行だけ引用・中継されてもどの種別か読めるようにするためである。
- **流さないチェックの書き方**: 次のチェックは流さず、結果の出力に `— <チェック名>（<理由>）` と書く。push の可否の判定には入れず、前段の失敗で打ち切ったときも書き方を変えない。

  | 流さない理由                                                                                                                                                                                                                                                         | `<理由>`                                                                                    |
  | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------- |
  | ユーザーが push を頼んだ指示（対話時と Auto Mode ではユーザーの発言、subagent ではタスクの指示文、CI ではジョブが渡したプロンプト。エージェントが自分で決めて外したものは数えない）か、この skill が `AskUserQuestion` で聞いた確認（冒頭の 4 場面）への答えで外した | `ユーザーの指示でスキップ`                                                                  |
  | 表の条件のうち「`<ツール>` がインストール済み」だけを満たさない                                                                                                                                                                                                      | `<ツール> が入っていないためスキップ`（`— Python lint（ruff が入っていないためスキップ）`） |

  ツールが入っているかは環境で変わり、別の環境や CI では流れて落ちうるので書く。`scripts.build` が無い、`Dockerfile` が無いなど、プロジェクトがそのチェックを定めていないために条件を満たさないものは、各節が書き方を決めたもの（npm init の既定の test、ロックファイルも依存も無い audit）を除いて書かない。
  ユーザーが外したチェックに、ツールが入っていない理由や各節のスキップ理由も当てはまるときは、そちらを書く。ユーザーは外したことを知っているが、ツールが無いことは知らない。
  種別名の無い指示（「lint は飛ばして」）は、すべての種別のその名前のチェック（`make lint` / `task lint` を含む）を外す。条件を満たさず書かないチェックは、外しても書かない。

- 各チェックの実行結果（成功/失敗）をリアルタイムで表示する。
- **失敗時の優先規則（同時発生時の判断）**:
  1. **1 つでもチェックが失敗したら、その時点で残りのチェックを打ち切る**（`audit は常に実行` のような原則よりも「失敗で中止」が優先）。残りを流しても push しないことは変わらない。打ち切ったチェックは出力で `— <チェック名>（前段失敗のため未実行）` と明記する
  2. 失敗内容をユーザーに報告し push を中止する。`git status --porcelain --untracked-files=no` が空でなければ、チェックが書き換えたファイルも添える（Step 3 の取り直しは通過したときしか流れない）。Step 3 の「チェックが作った未追跡のファイル」も、その節の条件で流す。どのモードでも同じで、skill の手順はそこで終わる。次の手を `AskUserQuestion` で聞くことも、直して流し直すことも、この skill の手順には含めない
- プロジェクトの種別が検出できない場合、または流すチェックが 1 つもない場合（スキップ行だけになる場合を含む）は、チェックを流さずに Step 3 に進む。
  - **種別はプロジェクトルートにある上の構成ファイルだけで決め、拡張子からは推測しない。** `app.py` だけで `pyproject.toml` 等が無いリポジトリは検出 0 件になり、それで正しい。構成ファイルが無いのはプロジェクトがチェックを定めていないということで、推測で流すと合意の無い基準で push が止まる
  - **流すチェックが 0 件のときの出力**: 「品質チェック」セクションは残し、0 件になった理由を明示する。種別ごとに、`— <チェック名>（理由）` のスキップ行（上の「流さないチェックの書き方」や各節の規則で出すもの）があればそれを並べ、1 行も無い種別には下の表の行を書く

    | 場合                                                 | 出力                                                                     |
    | ---------------------------------------------------- | ------------------------------------------------------------------------ |
    | 種別を 1 つも検出できなかった                        | `（プロジェクト種別を検出できなかったため全チェックをスキップ）`         |
    | 種別は検出したが、どのチェックも条件を満たさなかった | `（<種別名> を検出したが <チェックが無い理由>ため全チェックをスキップ）` |

    例: `（Makefile を検出したが lint / check / test / build ターゲットが無いため全チェックをスキップ）`。ruff / mypy / pytest がどれも入っていない Python は、この行ではなく `— Python lint（ruff が入っていないためスキップ）` などのスキップ行を 3 行並べる。
    コマンドが入っているかは、条件の列に書かれていない限りスキップの理由にしない。流すと決まったチェックのコマンドが無ければ失敗として扱う（Node.js の PM は先に上の PATH 解決のフォールバックに従う。見つからないときの確認を含む）

### Step 3: push の実行

すべてのチェックに通過したら（またはチェック不要の場合）、まず作業ツリーを取り直す。

```bash
git status --porcelain --untracked-files=no
```

出力が空でなければ、チェックが追跡ファイルを書き換えている（`eslint --fix` や整形ツールなど）。通ったのは書き換えた後の作業ツリーで、push するコミットではないので、どのモードでも push しない。書き換わったファイルを報告し、コミットしてから push し直すか中断するかを提示する（対話時は `AskUserQuestion`、非対話時は最終応答）。push を頼まれていてもこの問いは省略しない。push の依頼は、書き換わったファイルのコミットまでは含まない。
提示する前に下の「チェックが作った未追跡のファイル」を流し、`??` の行があれば、その扱い（`.gitignore` に足して一緒にコミットする / `.git/info/exclude` に足す。ロックファイルには `.gitignore` の代わりに「そのまま一緒にコミットする」を出す）も同じ確認で聞く。聞かずにやり直すと、Step 1 の 1. がそのファイルで止まる。stash は出さない。やり直しで流すチェックが同じファイルを作り直し、後で戻すときに衝突する。
コミットしてから push し直すと答えたら、書き換わったファイルを git-commit skill でコミットし、Step 1 からやり直す（チェックも流し直す）。push 対象のコミットが増えるうえ、コミット時のフックが中身を変えうるので、通ったときの作業ツリーをそのまま push できるとはみなさない。
未追跡のファイルは見ない。チェックを流す前からあった未追跡のファイルは Step 1 で止めているので、この時点にある未追跡のファイルはチェックが作ったもの（ビルドの生成物など）で、チェックした内容と push するコミットの違いにはならない。

出力が空なら、Step 1 で決めた push コマンドで push する。

```bash
git push <remote> <branch>
```

#### 初回 push（Step 1 の表で初回 push と決めた場合）

```bash
git push -u <remote> <branch>
```

#### force push（Step 1 の 3. で force push の承認を取った場合）

```bash
git push --force-with-lease=refs/heads/<branch>:<控えた sha> <remote> <branch>
```

表の行が `-u` 付きなら `-u` も付ける。push 先の `<branch>` が控えた sha のままなら上書きし、承認の後にほかの人が push したかブランチを消したなら ` ! [rejected]        <branch> -> <branch> (stale info)` で exit 1 になる（Git 2.54.0 で実測）。聞き直さずに、push コマンドが失敗した行で終える。

#### チェックが作った未追跡のファイル

チェックのコマンド（表の「コマンド」列や make / task のターゲット。インストール済みの判定は数えない）を 1 つでも実行したら、push したかどうか（失敗・書き換えで止めた場合を含む）にかかわらず、最終報告の前に流す。Step 3 で書き換えを提示する前に流したなら、その結果を使う。
1 つも実行していなければ（流すチェックが 0 件、PM が見つからず ✗ にしただけ、`yarn --version` が失敗して audit を ✗ にしただけ）流さない。未追跡のファイルが無いことは Step 1 で確かめてあり、何も実行していなければ空になる。

```bash
git status --porcelain --untracked-files=normal
```

`??` の行は、チェックが作り、無視されていない生成物である。作業ツリーに残り、次の push の Step 1 で止まるので、報告に添えて `.gitignore` に足してコミットするよう勧める。
ただしロックファイル（パスの末尾のファイル名が、Node.js の節の audit の段落に並べたもののどれか）は `.gitignore` に足すよう勧めない。`.gitignore` に足すと、ロックファイルをコミットしない方針をプロジェクトに入れることになり、CI と手元で依存の版が揃わなくなる。そのままコミットするか `.git/info/exclude` に足すかを添え、どちらにするかはユーザーに任せる。Step 2 で決めた PM のものとは限らない（make のターゲットが別の PM で install したものなど）。

### force push について

- force push を頼まれたとして扱うのは、push を頼んだ指示が force push を求めたとき（「force push して」、`--force` や `--force-with-lease` の指定など）だけである。指示として数えるものは remote の名指しと同じで、通常の push が拒否されたことや、エージェントが自分で決めたことは数えない。
- スキルから自発的に force push を提案しない。
- 統合ブランチ（`develop` / `master` / `main`）への force push も Step 1 の 2. で止める。push するコミットが 0 件でも、統合ブランチであることを理由に止める。detached HEAD も同じである。
- 対話モードでは、作業ブランチへの force push は Step 1 の 2. で push 先を fetch して `ls-remote` で先端の sha を取り、3. で push 先から消えるコミットを見せて `AskUserQuestion` で承認を取ってから行う（git-workflow のルール 6）。チェックは通常の push と同じく流す（push 先に残るのは HEAD である）。
  `--force` は使わず、承認したときに控えた sha を `--force-with-lease=refs/heads/<branch>:<sha>` で渡す。sha を渡さない `--force-with-lease` は remote-tracking ref と比べるので、承認の後に fetch が走ると、見せていないコミットまで上書きする（`git push --help`）。`--force-if-includes` は、sha を渡した lease と一緒では効かないので付けない（同）。
- 非対話モードでは、作業ブランチへの force push も、要求されていても行わない（git-workflow のルール 0）。Step 1 の 2. で中止条件として扱い、チェックは流さない。1. の未コミットの変更の方針、2. の表の確認、3. の 0 件の終わり方より先に当てる。push 節は `— push しない（非対話では force push を行わないため）` にし、出す方針は対話で force push を頼み直す（推奨。Auto Mode なら切ってから、subagent なら呼び出し元の対話セッションで頼む。Auto Mode のままでは同じところで止まる）、ユーザーが手で force push する（`git push --force-with-lease --force-if-includes <remote> <branch>`）、中断の 3 つにする。頼み直せば、消えるコミットを見てから承認でき、push 先の先端が承認したときのままでなければ上書きしない。手で打つコマンドは sha を渡せないので、`--force-if-includes` を付けて、fetch しただけで手元のブランチに一度も入っていない先端を拒否させる（`(remote ref updated since checkout)` で exit 1。amend や巻き戻しの後は通る。Git 2.54.0 で実測）。
  コマンドの `<remote>` は、remote の名指しがあればその remote、無ければ upstream の remote、どちらも無く `git remote` が 1 行ならその remote にする。決まらなければ `<remote>` のまま書き、push 先の remote を確かめてから打つよう添える。2. の表より先に止めるので push 先は決まっておらず、推測した remote に他人のブランチがあると、fetch 済みなら `--force-with-lease` だけでは上書きし、`--force-if-includes` を足すと拒否する（どちらも Git 2.54.0 で実測）。
  巻き戻す force push は新しいコミットが無くてもリモートを変えるので、0 件でもこの理由で止める。チェックを流さないのは、push しないと決まっていて、その結果が使われないためである。

## push した後、人に確認を頼む前に

**PR を作った直後は CI が pending である。pending は「まだ分からない」で
あって green ではない。**

「動作確認をお願いしたい」と依頼する前に、CI が **green** になるまで待つ。
赤い状態で頼むと、相手は動かないものを見せられることになる。

```bash
gh pr checks <number>          # 状態を見る
gh run watch <run-id> --exit-status   # 終わるまで待つ
```

自分が待てば分かることを、相手に肩代わりさせない。ユーザーの時間は、機械で
代替できない判断にだけ使う。

**実際の失敗**: PR を 2 本作り、どちらも CI を見ずに「ブラウザで確認して
ほしい」と依頼した。2 本とも整形エラーで落ちており、動く状態ですらなかった
（2026-08-08）。

### CI が green でも、見られる場所があるとは限らない

**CI が通ったことと、変更が動いている場所があることは別である。**
「ブラウザで見てほしい」と頼む前に、**相手が開く URL を自分が言えるか**を
確かめる。言えないなら、それは依頼ではなく丸投げである。

デプロイのトリガーを読む。多くのリポジトリは統合ブランチへの push でしか
デプロイしない。

```bash
grep -n -A6 "^on:" .github/workflows/deploy*.yml
```

`on: push: branches: [main]` だけなら、**PR の時点ではどこにも反映されて
いない**。この場合に取れる手段は 3 つある。

| 手段                         | 使いどころ                                               |
| ---------------------------- | -------------------------------------------------------- |
| ローカルで preview を立てる  | マージ前に見たい。**依存サービスが揃うかを先に確かめる** |
| 先にマージして本番で見る     | 戻せる規模のとき。revert の手順を添えて提案する          |
| PR ごとの preview 環境を作る | 同じ問題が繰り返し起きているとき。別作業として切り出す   |

**ローカル preview は「立てれば見える」とは限らない。** ローカルの DB が空、
外部サービスのバインディングが本番を向いていない、シークレットが無い、
といった理由で空の画面になる。**提案する前に、データが入っているかまで
確かめること。**

**実際の失敗**: CI が green になったのを確認して「ブラウザで見てほしい」と
依頼したが、そのリポジトリはデプロイが `main` への push のみで、PR 用の
preview 環境も無かった。**見る場所が存在しなかった。** 前回の失敗を受けて
「CI を待つ」は守ったが、「見られる状態か」は確かめていなかった
（2026-08-09）。

さらにローカル preview を代替として提案しかけたが、実際にはローカル DB に
テーブルすら無く、そのままでは空の画面になる状態だった。**手段を提案する
前に、その手段が成立するかを確かめていなかった。**

## 出力フォーマット

各ステップの結果を以下の形式で表示する:

```
## Push 前チェック

**ブランチ:** feature/xxx → origin/feature/xxx
**コミット数:** 3 件

### push 対象コミット
- abcdef1 feat(auth): ログイン機能を追加
- abcdef2 fix(auth): バリデーションの修正
- abcdef3 test(auth): ログインのテストを追加

### 品質チェック
- ✓ Node.js build
- — Node.js lint（ユーザーの指示でスキップ）
- ✗ Node.js test（失敗）
- — Node.js audit（前段失敗のため未実行）
- — Docker lint（hadolint が入っていないためスキップ）
- — Docker build（前段失敗のため未実行）

### push
- — push しない（チェックが失敗したため）
```

Step 1 の 3. で force push の承認を聞いたときは（中断と答えたときも）、「コミット数」と「push 対象コミット」を足すコミットで書き（0 件なら「push 対象コミット」は `- （無し）`）、その後に「push 先から消えるコミット」の節を同じ形で書く。

「push」の節は次のどれか 1 行で書く。

| 場合                                                                                                | 行                                                                                                                      |
| --------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| push した                                                                                           | `` ✓ `<流した push コマンド>` ``                                                                                        |
| force push を頼まれたが、push 先から消えるコミットが無く force を付けずに push した（Step 1 の 3.） | ``✓ `<流した push コマンド>`（push 先から消えるコミットが無いため force を付けなかった）``                              |
| push コマンドが 0 以外で終わった                                                                    | ``✗ `<流した push コマンド>`（失敗。<git が出した `!` / `error:` / `fatal:` の行>）``                                   |
| チェックが失敗した（追跡ファイルの書き換えを伴う場合を含む）                                        | `— push しない（チェックが失敗したため）`                                                                               |
| 全チェックが通った後、Step 3 で追跡ファイルの書き換えを検出した                                     | `— push しない（チェックが追跡ファイルを書き換えたため）`                                                               |
| Step 1 で止めた（push 対象 0 件、確認に中断と答えた場合を含む）                                     | `— push しない（<止めた理由>）`（force push の承認に中断と答えたら `— push しない（force push の確認で中断したため）`） |
| Step 2 の PM の確認（PATH の node が合わないときの、node か PM の場所の確認を含む）に中断と答えた   | `— push しない（PM の確認で中断したため）`                                                                              |

リモートに手元に無いコミットがあるときの理由の行は、追跡ブランチが古ければ ` ! [rejected]        <branch> -> <branch> (fetch first)`、fetch 済みで分岐していれば末尾が `(non-fast-forward)` になる（どちらも exit 1。Git 2.54.0 で実測）。拒否されても force push は提案しない（「force push について」）。
Step 1 で止めたときと PM の確認で中断したときは、チェックを流す前なので「品質チェック」の節は書かない。Step 1 で止めたときは、決まらなかった欄（push 先、コミット数、push 対象コミット）も書かない。

「push」の節の後に、当てはまるものがあれば「作業ツリー」「次の手」の節をこの順で書く。当てはまるものが無い節は見出しごと書かない。

| 節         | 行                                                                                                                                                                        | 書くとき                                                                                                                   |
| ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| 作業ツリー | `` 書き換えたファイル: `<パス>` ``                                                                                                                                        | 失敗時の優先規則 2 か Step 3 の取り直しで、`git status --porcelain --untracked-files=no` が空でなかった（1 ファイル 1 行） |
| 作業ツリー | ``未追跡のファイル: `<パス>`（`.gitignore` に足してコミットすることを勧める）``                                                                                           | Step 3 の「チェックが作った未追跡のファイル」で `??` の行が出た（1 ファイル 1 行。ロックファイルは次の行）                 |
| 作業ツリー | ``未追跡のファイル: `<パス>`（ロックファイルのため `.gitignore` には足さない。コミットするか `.git/info/exclude` に足す）``                                               | 同じく `??` の行が出て、それがロックファイルだった（1 ファイル 1 行）                                                      |
| 作業ツリー | ``stash: `<退避したときのメッセージ>`（戻し方: `git stash list` でメッセージから番号を探す → `git stash pop stash@{N}`）``                                                | Step 1 の確認でユーザーが stash を選んだ                                                                                   |
| 作業ツリー | ``統合ブランチ: `<統合ブランチ>` に、`<作業ブランチ>` へ移したコミットが <N> 件残っている（消すには git-workflow のルール 6 の承認が要る）``                              | Step 1 で統合ブランチから作業ブランチへ移し、移す前に 2. で数えた件数 <N> が 1 以上だった                                  |
| 次の手     | 番号付きの選択肢。推奨するものを 1. に置き、末尾に `（推奨）` を付ける。ロックファイルの扱いだけが違う選択肢には付けない（Step 3 の「チェックが作った未追跡のファイル」） | 非対話で Step 1 の中止条件か Step 3 の書き換えを検出した。対話時は `AskUserQuestion` で聞き終えているので書かない          |

Step 1 からやり直したときは、最後の回の結果だけを書く。「作業ツリー」節の stash と統合ブランチの行は、前の回のものも書く。

非対話で、全チェックが通った後に Step 3 で書き換えを検出した例:

```
### push
- — push しない（チェックが追跡ファイルを書き換えたため）

### 作業ツリー
- 書き換えたファイル: `src/a.ts`
- 未追跡のファイル: `dist/`（`.gitignore` に足してコミットすることを勧める）

### 次の手
1. 書き換わったファイルをコミットし、`dist/` を `.gitignore` に足して一緒にコミットしてから push し直す（推奨）
2. 書き換わったファイルをコミットし、`dist/` を `.git/info/exclude` に足してから push し直す
3. 中断する
```
