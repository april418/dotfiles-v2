---
name: git-push
description: リモートへの push 前に品質チェック（build, lint, test, audit 等）を実行し、安全にプッシュする。プロジェクトのツールチェインを自動検出してチェックを行う。
---

# 概要

- このスキルはリモートブランチへの push を行う。
- push 前にプロジェクト固有の品質チェックを自動検出・実行する。
- すべてのチェックに通過した場合のみ push を実行する。

## 実行モードと AskUserQuestion

本スキルは、流すチェックの一覧にも push にも承認を取らない（`[gone]` のブランチを作り直すかは下の表の 1 行目で聞く）。Step 1 を通った時点で未コミット変更は無く push 先も 1 つに決まっており、作業ブランチへの通常の push（force を伴わない）は後から打ち消せる（git-workflow のルール 0）。
チェックを外すのは push を頼む指示で行う（「流さないチェックの書き方」）。

`AskUserQuestion` で聞くのは次の 3 つの場面だけである。**非対話モード**（subagent 実行、CI、Auto Mode 等、ユーザーへの問い合わせができないコンテキスト）では、右の列のとおりにする。

| 場面 | 対話モード | 非対話モード |
| --- | --- | --- |
| Step 1 で確認が要るか中止条件を検出した（未コミット変更、push 先の remote が決まらない、名指しの remote が upstream の remote と違う、upstream が `[gone]`、detached HEAD、remote が 0 行） | 検出内容を伝え、次に取りうる方針を聞く | 下の段落 |
| Step 2 で Node.js の PM が見つからない | PM の場所を聞く | Node.js のチェックを失敗にする（「PATH 解決のフォールバック」） |
| Step 3 でチェックが追跡ファイルを書き換えた | コミットしてから push し直すか、中断するかを聞く | 同じ選択肢を最終応答で提示する |

非対話モードで Step 1 の中止条件を検出した場合（未コミット変更あり / push 対象 0 件 / detached HEAD / upstream が `[gone]` / push 先の remote が決まらない / 名指しの remote が upstream の remote と違う 等）は、push は実行せず、検出内容と次に取りうる方針（コミット / `.gitignore` か `.git/info/exclude` に足す / stash / push 先の remote の指定 / 中断等）を最終応答で 3〜4 択で提示する。

**チェックが 1 つでも失敗したら、どのモードでも push しない。** 失敗内容を報告して終える（「失敗時の優先規則」）。

## ワークフロー

### Step 1: 現在の状態を確認

```bash
git status --porcelain --untracked-files=normal
```

```bash
git branch -vv --contains HEAD
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
   未追跡のファイルには無視する選択肢も出す。生成物は `.gitignore` に足してコミットする（git-commit skill。このコミットも push 対象に入る）。`.gitignore` を書き換えただけでは ` M .gitignore` が残る。自分だけが作るファイル（メモなど）は `.git/info/exclude` に足す（コミットは要らない）。
   stash は `git stash push -u -m "<branch>: git-push の前に退避 (<退避したパス>)"` にする。`-u` が無いと未追跡のファイルを退避せず、未追跡のファイルだけのときは `No local changes to save` と出して exit 0 で終わる（Git 2.54.0 で実測）。メッセージにパスを入れるのは、同じ文言の stash が 2 つ並ぶと `git stash list` で見分けられないため。
   片付けたら Step 1 からやり直す。stash は push の後も戻さず、最終応答に退避したときのメッセージと戻し方（`git stash list` でメッセージから番号を探す → `git stash pop stash@{N}`）を書く。戻さないのは、チェックが作り直したファイルとパスが重なると、pop が一部だけ戻して exit 1 になり stash も残るためである。
2. **push 先のリモート・ブランチ** — まず `git branch --show-current` が空でないことを確かめる。
   空なら detached HEAD で push するブランチが無いので、中止条件として扱う（`for-each-ref` は
   `refs/heads/` を引くことになり、全ブランチの upstream を並べる）。空でなければ
   `for-each-ref` の出力、`git remote` の行数、remote の名指しで決める。

   **remote の名指し**は、push を頼んだ指示が push 先の remote を名前で指定していること（「fork に push して」、`/git-push fork` の引数など）。
   指示として数えるのは、対話時と Auto Mode ではユーザーの発言、subagent ではタスクの指示文、CI ではジョブが渡したプロンプトである。skill の引数は、1 語のときだけ名前として比べる（2 語以上なら一致しないものとして扱う）。push 先の remote を聞く確認（名指しが `git remote` のどれとも一致しない、2 行以上で名指しが無い）でユーザーが答えた remote も名指しに数え、表を引き直す。エージェントが自分で選んで skill の引数に入れた名前は数えない。
   名前は `git remote` の出力の各行と完全一致で比べる。どれとも一致しなければ、`git remote` が 0 行なら表の最終行で中止し、1 行以上なら表には当てはめず `AskUserQuestion` でユーザーに push 先を確認する。表の「名指し」はすべて一致したものである。

   | upstream（`for-each-ref` の出力） | `git remote` | remote の名指し | push 先 |
   | --- | --- | --- | --- |
   | 同名のリモートブランチ（`<remote>/<branch>`。`[ahead N]` / `[behind N]` / `[ahead N, behind N]` が続いてよい。`[gone]` で終わるものは下の `[gone]` の行） | — | 無い、または upstream の remote | `git push <remote> <branch>` |
   | 同名のリモートブランチ（末尾が `[gone]` のものを含む） | — | upstream と違う remote | `AskUserQuestion` で確認する。`-u` で upstream を名指しの remote へ付け替えるかが決まらない。付け替えずに push すると upstream は変わらず、3. の `@{upstream}..HEAD` は upstream の remote との差しか出さない（upstream の remote に push 済みなら 0 件になり、push せずに終わる。Git 2.54.0 で実測）。答えで `git push -u <名指しの remote> <branch>` か `git push <名指しの remote> <branch>` に決まる。どちらでも、3. は `git log --oneline HEAD --not --remotes=<名指しの remote>` で数える |
   | 末尾が `[gone]`（upstream のリモートブランチが消えた） | — | 無い、または upstream の remote | `AskUserQuestion` で確認する。PR がマージ済みでブランチが消された可能性があり、push するとマージ済みのブランチを作り直す（git-pr のルール 11「マージした直後にベースを最新へ戻す」を見る）。push すると答えたら `git push <upstream の remote> <branch>` に決まる。upstream の設定は残っており、push で追跡が戻るので `-u` は要らない。3. は `@{upstream}` が解決できず exit 128 になるので、`git log --oneline HEAD --not --remotes=<upstream の remote>` で数える（どちらも Git 2.54.0 で実測） |
   | 空（upstream が無い）、または名前の違うブランチ | 1 行 | 無い、またはその remote | **初回 push として扱い、`git push -u <remote> <branch>` で確定とみなす** |
   | 空、または名前の違うブランチ | 2 行以上 | ある | **初回 push として扱い、`git push -u <名指しの remote> <branch>` で確定とみなす** |
   | 空、または名前の違うブランチ | 2 行以上 | 無い | `AskUserQuestion` でユーザーに push 先を確認する |
   | — | 0 行 | — | push 先が無い。中止条件として扱う |

   `origin/<base>` から切ったブランチは upstream が `origin/<base>` になる（名前の違う
   ブランチ）。そのままでは引数なしの `git push` が名前の不一致で拒否され、`-u` を付けずに
   push すると upstream がベースを指したまま残るので、初回 push として `-u` で付け替える。
3. **push 対象のコミット** — 差分コミット一覧をユーザーに表示する。push するコミットが 0 件の場合は「push するコミットがない」旨を伝えて終了する。

   ```bash
   git log --oneline @{upstream}..HEAD               # upstream が同名のリモートブランチ
   git log --oneline HEAD --not --remotes=<remote>   # 初回 push
   ```

   初回 push で `git log -5` のように件数で区切ると、自分のコミットが 0 件でもベースの
   コミットが並び、0 件を判定できない。`--not --remotes=<remote>` はリモートのどのブランチにも
   無いコミットだけを出す。

### Step 2: プロジェクトの品質チェックを自動検出・実行

プロジェクトルートのファイル構成からツールチェインを自動検出し、
利用可能なチェックを順に実行する。

#### 検出ロジック

以下の種別をすべて調べ、当てはまった種別はすべて対象にする（最初に当てはまった種別で止めない）。チェックを流す順は節の並び（Node.js → Python → Rust → Go → Ansible → Docker → Makefile → Taskfile）で、種別の中は表の行の順（Makefile / Taskfile は `lint` → `check` → `test` → `build` の順）である。

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
bun は 1.2.15 で `bun audit` が入ったので、それより前の bun では失敗になる。
pnpm 10 以下の `pnpm audit --prod` が `ERR_PNPM_AUDIT_BAD_RESPONSE` の 410 で失敗したら、package-manager skill のルール 5 の手順で pnpm 11 を使って流し直し、その結果で判定する。出力の `Node.js audit` の行には括弧で `pnpm 10 が 410 を返したため pnpm 11 で流し直した` と書き、ルール 5 が報告に添えるよう求めることも同じ括弧に入れる。

**PATH 解決のフォールバック**: 非ログインシェル（subagent の Bash 等）では `nvm` 配下の `node` / `pnpm` / `npm` が `PATH` に入っていないことがある。`command -v <pm>` で見つからない場合は以下の優先順で探索する:

1. `~/.nvm/versions/node/*/bin/<pm>` の最新版
2. `~/.local/share/pnpm/<pm>` 等の標準的な install path

それでも見つからなければ `AskUserQuestion` でユーザーに PM の場所を確認する。
非対話モード時は Node.js のチェックを流さずに失敗とし、push を中止する。出力は、流すはずだった Node.js のチェックのうち最初のものを `✗ Node.js build（失敗。pnpm が見つからない。探した場所: <command -v と上の 1・2 で見たパス>）` のように書き、残りの Node.js のチェックは前段失敗の行（`— <チェック名>（前段失敗のため未実行）`）にする。ほかの種別のチェックは、ほかの失敗と同じく「失敗時の優先規則」に従う。
`corepack <pm>@latest` で取ってくることはしない。Node.js 25 以降は corepack が同梱されず、`@latest` はプロジェクトが宣言した版を無視するため。
流す Node.js のチェックが 1 つも無ければ（スキップ行だけなら）PM は探さず、見つからなくても失敗にしない。

| チェック | 条件 | コマンド |
|---------|------|---------|
| build | `scripts.build` が定義されている | `<pm> run build` |
| lint | `scripts.lint` が定義されている | `<pm> run lint` |
| typecheck | `scripts.typecheck` が定義されている | `<pm> run typecheck` |
| type-check | `scripts.type-check` が定義されている | `<pm> run type-check` |
| test | `scripts.test` が定義されている | `<pm> run test` |
| audit | 常に実行 | `<pm> audit` (`pnpm` の場合は `pnpm audit --prod`) |

`scripts.typecheck` と `scripts.type-check` が両方定義されていれば両方流す。中身が違いうるので、片方だけでは取りこぼす。

**`scripts.test` の値が `npm init` / `pnpm init` の既定の `echo "Error: no test specified" && exit 1` と完全に一致するときは、定義されていないものとして扱う。** package.json 上は `"test": "echo \"Error: no test specified\" && exit 1"` と書かれている。test 行の条件を満たさないので流さず、検出されなかったチェックと同じく push の可否の判定にも入れない。結果の出力には `— Node.js test（scripts.test が npm init の既定のままのためスキップ）` と書き、前段の失敗で打ち切ったときもこの書き方を変えない。
空白やコマンドを足したもの（末尾に `&& jest` を足したもの等）は定義されているものとして流し、0 でない終了コードは失敗である。判定は PM によらない（`npm init` で作ってから別の PM に移したプロジェクトにも残る）。

**ロックファイル（`bun.lock` / `bun.lockb` / `pnpm-lock.yaml` / `yarn.lock` / `package-lock.json` / `npm-shrinkwrap.json`）がどれも無く、`package.json` の `dependencies` / `devDependencies` / `optionalDependencies` / `peerDependencies` / `workspaces` と `pnpm-workspace.yaml` の `packages` もどれも無いか空のときは、audit を流さない。** ロックファイルが無いと、`npm audit` は `ENOLOCK`、`pnpm audit` は `ERR_PNPM_AUDIT_NO_LOCKFILE` で exit 1 になる。依存が無ければ、ロックファイルを作って流しても脆弱性 0 件（exit 0）で終わる。検出されなかったチェックと同じく push の可否の判定には入れず、結果の出力には `— Node.js audit（ロックファイルも依存も無いためスキップ）` と書く。前段の失敗で打ち切ったときもこの書き方を変えない。
ロックファイルが無くても上のどれかが空でなければ流し、ロックファイルが無いことによる失敗も失敗である。ロックファイルを作るコマンド（`npm audit` のエラーが案内する `npm i --package-lock-only`、`pnpm install --lockfile-only` 等）はスキルから流さない（未コミットのファイルが増える）。

**Python プロジェクト（`pyproject.toml` / `setup.py` / `setup.cfg` が存在）:**

| チェック | 条件 | コマンド |
|---------|------|---------|
| lint | `ruff` がインストール済み | `ruff check .` |
| type-check | `mypy` がインストール済み | `mypy .` |
| test | `pytest` がインストール済み | `pytest` |

pytest は収集・選択されたテストが 0 件だと exit 5 で終わる。`uv init` 直後、テスト関数の無い `test_*.py` だけのとき、`addopts` の `-m` / `-k` で全件が外れたときがこれに当たる。テストがあっても `testpaths` / `python_files` の設定や全モジュールの `importorskip` で 0 件になれば同じく exit 5 で、区別しない。
**exit 5 は失敗に数えない。** push の可否を決める判定（冒頭の「チェックが 1 つでも失敗したら」、Step 3 の「すべてのチェックに通過したら」）では通過として扱い、出力だけ `— Python test（実行するテストが 0 件のためスキップ。pytest の exit 5: <最終行>）` と書く。`<最終行>` は pytest の最後の行から `=` と所要時間を除いたもの（`no tests ran` / `1 deselected` など）。
exit 5 以外の 0 でない終了コードは失敗である。この扱いは Python の表から流した `pytest` に限る。Makefile / Taskfile のターゲットや `scripts.test` から呼ばれた pytest は、テストが 0 件でもそのツールの終了コードで判定する。それらはプロジェクトが定めた入口なので、その終了コードをそのまま採る。表の `pytest` は skill が選んだコマンドなので、exit 5 の読み方も skill が決めてよい。make の出力と報告の書き方は Makefile / Taskfile の節にある。

**Rust プロジェクト（`Cargo.toml` が存在）:**

| チェック | 条件 | コマンド |
|---------|------|---------|
| build | 常に実行 | `cargo build` |
| lint | `clippy` がインストール済み | `cargo clippy -- -D warnings` |
| test | 常に実行 | `cargo test` |
| audit | `cargo-audit` がインストール済み | `cargo audit` |

**Go プロジェクト（`go.mod` が存在）:**

| チェック | 条件 | コマンド |
|---------|------|---------|
| build | 常に実行 | `go build ./...` |
| vet | 常に実行 | `go vet ./...` |
| lint | `golangci-lint` がインストール済み | `golangci-lint run` |
| test | 常に実行 | `go test ./...` |

**Ansible プロジェクト（`ansible.cfg` または `playbook.yml` が存在）:**

| チェック | 条件 | コマンド |
|---------|------|---------|
| lint | `ansible-lint` がインストール済み | `ansible-lint` |
| syntax-check | `playbook.yml` が存在 | `ansible-playbook --syntax-check playbook.yml` |

syntax-check はプロジェクトルートの `playbook.yml` にだけ流す。ほかの YAML を playbook とみなすのは推測で、vars やタスクのリストに流すと落ちる。ほかの playbook は ansible-lint に任せる（外せない syntax-check ルールで、見つけた playbook すべてに `ansible-playbook --syntax-check` を流す）。

**Docker プロジェクト（`Dockerfile` または `compose.yml` / `docker-compose.yml` が存在）:**

| チェック | 条件 | コマンド |
|---------|------|---------|
| lint | `Dockerfile` が存在し、`hadolint` がインストール済み | `hadolint Dockerfile` |
| build | `Dockerfile` が存在 | `docker build --check .` |
| compose-config | `compose.yml` / `docker-compose.yml` が存在 | `docker compose config --quiet` |

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

  | 流さない理由 | `<理由>` |
  | --- | --- |
  | ユーザーが push を頼んだ指示（対話時と Auto Mode ではユーザーの発言、subagent ではタスクの指示文、CI ではジョブが渡したプロンプト。エージェントが自分で決めて外したものは数えない）で外した | `ユーザーの指示でスキップ` |
  | 表の条件のうち「`<ツール>` がインストール済み」だけを満たさない | `<ツール> が入っていないためスキップ`（`— Python lint（ruff が入っていないためスキップ）`） |

  ツールが入っているかは環境で変わり、別の環境や CI では流れて落ちうるので書く。`scripts.build` が無い、`Dockerfile` が無いなど、プロジェクトがそのチェックを定めていないために条件を満たさないものは、各節が書き方を決めたもの（npm init の既定の test、ロックファイルも依存も無い audit）を除いて書かない。
  ユーザーが外したチェックに、ツールが入っていない理由や各節のスキップ理由も当てはまるときは、そちらを書く。ユーザーは外したことを知っているが、ツールが無いことは知らない。
  種別名の無い指示（「lint は飛ばして」）は、すべての種別のその名前のチェック（`make lint` / `task lint` を含む）を外す。条件を満たさず書かないチェックは、外しても書かない。
- 各チェックの実行結果（成功/失敗）をリアルタイムで表示する。
- **失敗時の優先規則（同時発生時の判断）**:
  1. **1 つでもチェックが失敗した時点で残りのチェックは打ち切ってよい**（`audit は常に実行` のような原則よりも「失敗で中止」が優先）。打ち切ったチェックは出力で `— <チェック名>（前段失敗のため未実行）` と明記する
  2. 失敗内容をユーザーに報告し push を中止する。`git status --porcelain --untracked-files=no` が空でなければ、チェックが書き換えたファイルも添える（Step 3 の取り直しは通過したときしか流れない）。Step 3 の「チェックが作った未追跡のファイル」も流す。どのモードでも同じで、skill の手順はそこで終わる。次の手を `AskUserQuestion` で聞くことも、直して流し直すことも、この skill の手順には含めない
- プロジェクトの種別が検出できない場合、または流すチェックが 1 つもない場合（スキップ行だけになる場合を含む）は、チェックを流さずに Step 3 に進む。
  - **種別はプロジェクトルートにある上の構成ファイルだけで決め、拡張子からは推測しない。** `app.py` だけで `pyproject.toml` 等が無いリポジトリは検出 0 件になり、それで正しい。構成ファイルが無いのはプロジェクトがチェックを定めていないということで、推測で流すと合意の無い基準で push が止まる
  - **流すチェックが 0 件のときの出力**: 「品質チェック」セクションは残し、0 件になった理由を明示する。種別ごとに、`— <チェック名>（理由）` のスキップ行（上の「流さないチェックの書き方」や各節の規則で出すもの）があればそれを並べ、1 行も無い種別には下の表の行を書く

    | 場合 | 出力 |
    | --- | --- |
    | 種別を 1 つも検出できなかった | `（プロジェクト種別を検出できなかったため全チェックをスキップ）` |
    | 種別は検出したが、どのチェックも条件を満たさなかった | `（<種別名> を検出したが <チェックが無い理由>ため全チェックをスキップ）` |

    例: `（Makefile を検出したが lint / check / test / build ターゲットが無いため全チェックをスキップ）`。ruff / mypy / pytest がどれも入っていない Python は、この行ではなく `— Python lint（ruff が入っていないためスキップ）` などのスキップ行を 3 行並べる。
    コマンドが入っているかは、条件の列に書かれていない限りスキップの理由にしない。流すと決まったチェックのコマンドが無ければ失敗として扱う（Node.js の PM は先に上の PATH 解決のフォールバックに従う。見つからないときの確認を含む）

### Step 3: push の実行

すべてのチェックに通過したら（またはチェック不要の場合）、まず作業ツリーを取り直す。

```bash
git status --porcelain --untracked-files=no
```

出力が空でなければ、チェックが追跡ファイルを書き換えている（`eslint --fix` や整形ツールなど）。通ったのは書き換えた後の作業ツリーで、push するコミットではないので、どのモードでも push しない。書き換わったファイルを報告し、コミットしてから push し直すか中断するかを提示する（対話時は `AskUserQuestion`、非対話時は最終応答）。push を頼まれていてもこの問いは省略しない。push の依頼は、書き換わったファイルのコミットまでは含まない。
未追跡のファイルは見ない。チェックを流す前からあった未追跡のファイルは Step 1 で止めているので、この時点にある未追跡のファイルはチェックが作ったもの（ビルドの生成物など）で、チェックした内容と push するコミットの違いにはならない。

出力が空なら、Step 1 で決めた push コマンドで push する。

```bash
git push <remote> <branch>
```

#### 初回 push（Step 1 の表で初回 push と決めた場合）

```bash
git push -u <remote> <branch>
```

#### チェックが作った未追跡のファイル

チェックを流したら、push したかどうか（失敗・書き換えで止めた場合を含む）にかかわらず、最終報告の前に流す。

```bash
git status --porcelain --untracked-files=normal
```

`??` の行は、チェックが作り、無視されていない生成物である。作業ツリーに残り、次の push の Step 1 で止まるので、報告に添えて `.gitignore` に足してコミットするよう勧める。

### force push について

- `--force` や `--force-with-lease` は**ユーザーが明示的に要求した場合のみ**使用する。
- スキルから自発的に force push を提案しない。
- main / master ブランチへの force push をユーザーが要求した場合は、リスクを警告する。

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

| 手段 | 使いどころ |
| --- | --- |
| ローカルで preview を立てる | マージ前に見たい。**依存サービスが揃うかを先に確かめる** |
| 先にマージして本番で見る | 戻せる規模のとき。revert の手順を添えて提案する |
| PR ごとの preview 環境を作る | 同じ問題が繰り返し起きているとき。別作業として切り出す |

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

「push」の節は次のどれか 1 行で書く。

| 場合 | 行 |
| --- | --- |
| push した | `` ✓ `<流した push コマンド>` `` |
| push コマンドが 0 以外で終わった | `` ✗ `<流した push コマンド>`（失敗。<git が出した `!` / `error:` / `fatal:` の行>） `` |
| チェックが失敗した（追跡ファイルの書き換えを伴う場合を含む） | `— push しない（チェックが失敗したため）` |
| 全チェックが通った後、Step 3 で追跡ファイルの書き換えを検出した | `— push しない（チェックが追跡ファイルを書き換えたため）` |
| Step 1 で止めた（push 対象 0 件、確認に中断と答えた場合を含む） | `— push しない（<止めた理由>）` |
| Step 2 の PM の確認に中断と答えた | `— push しない（PM の確認で中断したため）` |

リモートに手元に無いコミットがあるときの理由の行は、追跡ブランチが古ければ ` ! [rejected]        <branch> -> <branch> (fetch first)`、fetch 済みで分岐していれば末尾が `(non-fast-forward)` になる（どちらも exit 1。Git 2.54.0 で実測）。拒否されても force push は提案しない（「force push について」）。
Step 1 で止めたときと PM の確認で中断したときは、チェックを流す前なので「品質チェック」の節は書かない。Step 1 で止めたときは、決まらなかった欄（push 先、コミット数、push 対象コミット）も書かない。
