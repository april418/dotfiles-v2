---
name: git-push
description: リモートへの push 前に品質チェック（build, lint, test, audit 等）を実行し、安全にプッシュする。プロジェクトのツールチェインを自動検出してチェックを行う。
---

# 概要

- このスキルはリモートブランチへの push を行う。
- push 前にプロジェクト固有の品質チェックを自動検出・実行する。
- すべてのチェックに通過した場合のみ push を実行する。

## 実行モードと AskUserQuestion の省略条件

本スキルは Step 1（中止条件検出時の方針確認）、Step 2（チェック一覧承認）、Step 3（push 最終確認）の **3 箇所** で `AskUserQuestion` を要求する。
ただし以下のいずれかに該当する場合は確認を省略してよい。非対話モードと事前指示済みでは **3 箇所すべて**、前提条件揃いでは Step 2 / Step 3 を省略する。

- **非対話モード**: subagent 実行、CI、Auto Mode 等、ユーザーへの問い合わせができないコンテキスト
- **明確な前提条件揃い**: 全チェック成功（または検出 0 件）+ 未コミット変更なし（Step 1 の 1. の判定。未追跡のファイルも数える）+ push 先が一意に確定（Step 1 の表で push コマンドが決まる行に当たるか、Step 1 の確認への答えで push コマンドが決まった。初回 push と、remote の名指しで決まる行を含む）。判定する時点は下の「Step 2 / Step 3 の承認」の表に従う
- **ユーザーが事前指示済み**: 直近のユーザー指示で push 実行が明示的に承認されている

省略した場合の振る舞い:

- **Step 1 で中止条件を検出した場合**（未コミット変更あり / push 対象 0 件 / detached HEAD / upstream が `[gone]` / push 先の remote が決まらない / 名指しの remote が upstream の remote と違う 等）: push は実行せず、検出内容と次に取りうる方針（コミット / `.gitignore` か `.git/info/exclude` に足す / stash / push 先の remote の指定 / 中断等）を最終応答で 3〜4 択で提示する
- **Step 2 / Step 3 の承認**: 非対話モードと事前指示済みでは省略する。前提条件揃いで省略するかは、各ステップに入るときに下の表で判定する。省略したら最終応答（または Discretionary fill-ins 相当の箇所）に「どの判断で承認を省略したか」を 1 行で明記する

  | 承認 | 判定する時点 | 前提条件揃いで省略できる条件 |
  | --- | --- | --- |
  | Step 2 のチェック一覧承認 | チェックを流す前 | 未コミット変更なし + push 先が一意に確定 |
  | Step 3 の push 最終確認 | 全チェックを流し、作業ツリーを取り直した後 | Step 2 の行の条件（Step 2 に入るときの判定を引き継ぎ、未追跡のファイルを数え直さない）+ 全チェック成功（または検出 0 件） |

なお、**チェックが 1 つでも失敗した場合と、チェックが追跡ファイルを書き換えた場合（Step 3）は省略不可** — どのモードでも必ず内容を報告し push を中止する。

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
   | 同名のリモートブランチ（`[gone]` を除く） | — | upstream と違う remote | `AskUserQuestion` で確認する。`-u` で upstream を名指しの remote へ付け替えるかが決まらない。付け替えずに push すると upstream は変わらず、3. の `@{upstream}..HEAD` は upstream の remote との差しか出さない（upstream の remote に push 済みなら 0 件になり、push せずに終わる。Git 2.54.0 で実測）。答えで `git push -u <名指しの remote> <branch>` か `git push <名指しの remote> <branch>` に決まる。どちらでも、3. は `git log --oneline HEAD --not --remotes=<名指しの remote>` で数える |
   | 末尾が `[gone]`（upstream のリモートブランチが消えた） | — | — | `AskUserQuestion` で確認する。PR がマージ済みでブランチが消された可能性があり、push するとマージ済みのブランチを作り直す（git-pr のルール 11「マージした直後にベースを最新へ戻す」を見る） |
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

以下の優先順で検出する。該当しないものはスキップする。

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

**PATH 解決のフォールバック**: 非ログインシェル（subagent の Bash 等）では `nvm` 配下の `node` / `pnpm` / `npm` が `PATH` に入っていないことがある。`command -v <pm>` で見つからない場合は以下の優先順で探索する:

1. `~/.nvm/versions/node/*/bin/<pm>` の最新版
2. `~/.local/share/pnpm/<pm>` 等の標準的な install path

それでも見つからなければ `AskUserQuestion` でユーザーに PM の場所を確認する（非対話モード時はチェックスキップして失敗扱いで中止）。
`corepack <pm>@latest` で取ってくることはしない。Node.js 25 以降は corepack が同梱されず、`@latest` はプロジェクトが宣言した版を無視するため。

| チェック | 条件 | コマンド |
|---------|------|---------|
| build | `scripts.build` が定義されている | `<pm> run build` |
| lint | `scripts.lint` が定義されている | `<pm> run lint` |
| type-check | `scripts.typecheck` または `scripts.type-check` が定義されている | `<pm> run typecheck` or `<pm> run type-check` |
| test | `scripts.test` が定義されている | `<pm> run test` |
| audit | 常に実行 | `<pm> audit` (`pnpm` の場合は `pnpm audit --prod`) |

**`scripts.test` の値が `npm init` / `pnpm init` の既定の `echo "Error: no test specified" && exit 1` と完全に一致するときは、定義されていないものとして扱う。** package.json 上は `"test": "echo \"Error: no test specified\" && exit 1"` と書かれている。test 行の条件を満たさないので流さず、検出されなかったチェックと同じく push の可否の判定にも入れない。Step 2 の承認で見せる一覧と結果の出力には `— test（scripts.test が npm init の既定のままのためスキップ）` と書き、前段の失敗で打ち切ったときもこの書き方を変えない。
空白やコマンドを足したもの（末尾に `&& jest` を足したもの等）は定義されているものとして流し、0 でない終了コードは失敗である。判定は PM によらない（`npm init` で作ってから別の PM に移したプロジェクトにも残る）。

**ロックファイル（`bun.lock` / `bun.lockb` / `pnpm-lock.yaml` / `yarn.lock` / `package-lock.json` / `npm-shrinkwrap.json`）がどれも無く、`package.json` の `dependencies` / `devDependencies` / `optionalDependencies` / `peerDependencies` / `workspaces` と `pnpm-workspace.yaml` の `packages` もどれも無いか空のときは、audit を流さない。** ロックファイルが無いと、`npm audit` は `ENOLOCK`、`pnpm audit` は `ERR_PNPM_AUDIT_NO_LOCKFILE` で exit 1 になる。依存が無ければ、ロックファイルを作って流しても脆弱性 0 件（exit 0）で終わる。検出されなかったチェックと同じく push の可否の判定には入れず、Step 2 の承認で見せる一覧と結果の出力には `— audit（ロックファイルも依存も無いためスキップ）` と書く。前段の失敗で打ち切ったときもこの書き方を変えない。
ロックファイルが無くても上のどれかが空でなければ流し、ロックファイルが無いことによる失敗も失敗である。ロックファイルを作るコマンド（`npm audit` のエラーが案内する `npm i --package-lock-only`、`pnpm install --lockfile-only` 等）はスキルから流さない（未コミットのファイルが増える）。

**Python プロジェクト（`pyproject.toml` / `setup.py` / `setup.cfg` が存在）:**

| チェック | 条件 | コマンド |
|---------|------|---------|
| lint | `ruff` がインストール済み | `ruff check .` |
| type-check | `mypy` がインストール済み | `mypy .` |
| test | `pytest` がインストール済み | `pytest` |

pytest は収集・選択されたテストが 0 件だと exit 5 で終わる。`uv init` 直後、テスト関数の無い `test_*.py` だけのとき、`addopts` の `-m` / `-k` で全件が外れたときがこれに当たる。テストがあっても `testpaths` / `python_files` の設定や全モジュールの `importorskip` で 0 件になれば同じく exit 5 で、区別しない。
**exit 5 は失敗に数えない。** push の可否を決める判定（冒頭の「全チェック成功」、Step 3 の「すべてのチェックに通過したら」）では通過として扱い、出力だけ `— test（実行するテストが 0 件のためスキップ。pytest の exit 5: <最終行>）` と書く。`<最終行>` は pytest の最後の行から `=` と所要時間を除いたもの（`no tests ran` / `1 deselected` など）。
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
| syntax-check | 常に実行 | `ansible-playbook --syntax-check <playbook>` |

**Docker プロジェクト（`Dockerfile` または `compose.yml` / `docker-compose.yml` が存在）:**

| チェック | 条件 | コマンド |
|---------|------|---------|
| lint | `hadolint` がインストール済み | `hadolint Dockerfile` |
| build | `Dockerfile` が存在 | `docker build --check .` |
| compose-config | `compose.yml` / `docker-compose.yml` が存在 | `docker compose config --quiet` |

**Makefile / Taskfile（`Makefile` / `Taskfile.yml` が存在）:**

`lint`, `check`, `test`, `build` ターゲットが定義されていれば実行する。

出力ではチェック名を `make <ターゲット>` / `task <タスク>` と書く。Python の表の `test` と同時に流れると、同じ pytest の 0 件がスキップと失敗に分かれるので、どちらの結果かを区別するためである。

ターゲットから呼ばれた pytest のテストが 0 件だと、make は exit 2 で終わる。最終行は `make: *** [test] Error 5` で、その直前の行は、要約を出す設定なら pytest の要約になる（既定では `=` で囲まれた `no tests ran in 0.00s`、`-q` では囲みが無い。`-qq` では要約が出ず空行。GNU Make 3.81 と pytest 9.1.1 で実測）。これも失敗として push を止める（理由は Python の表の下の段落）。
最終行が `Error 5` で終わり、直前の行が pytest の要約で `passed` / `failed` / `error` / `skipped` のどれも含まない（`no tests ran` / `1 deselected` / `1 warning` など）ときは、失敗の報告に原因と直し方を添える。make の `Error 5` はレシピのどのコマンドが 5 を返しても出るので、要約の行が無ければ添えない。この判定は make の出力の形に合わせたもので、task には当てはめない。

```
- ✗ make test（失敗。pytest の実行するテストが 0 件で exit 5。テストを足すか、0 件を通すなら Makefile 側で `pytest || [ $$? -eq 5 ]` のように exit 5 を成功に変える）
```

#### チェック実行の原則

- 検出されたチェックの一覧と実行順をユーザーに提示し、`AskUserQuestion` で承認を得てから実行する（省略するかは冒頭の「Step 2 / Step 3 の承認」に従い、チェックを流す前に決める）。
- チェックをスキップしたい場合はユーザーが指定できる。
- 各チェックの実行結果（成功/失敗）をリアルタイムで表示する。
- **失敗時の優先規則（同時発生時の判断）**:
  1. **1 つでもチェックが失敗した時点で残りのチェックは打ち切ってよい**（`audit は常に実行` のような原則よりも「失敗で中止」が優先）。打ち切ったチェックは出力で `— <チェック名>（前段失敗のため未実行）` と明記する
  2. 失敗内容をユーザーに報告し push を中止する。`git status --porcelain --untracked-files=no` が空でなければ、チェックが書き換えたファイルも添える（Step 3 の取り直しは通過したときしか流れない）。Step 3 の「チェックが作った未追跡のファイル」も流す
  3. 非対話モードでもこの中止は省略不可
- プロジェクトの種別が検出できない場合、または該当するチェックが1つもない場合は、チェックをスキップして Step 3 に進む。
  - **種別はプロジェクトルートにある上の構成ファイルだけで決め、拡張子からは推測しない。** `app.py` だけで `pyproject.toml` 等が無いリポジトリは検出 0 件になり、それで正しい。構成ファイルが無いのはプロジェクトがチェックを定めていないということで、推測で流すと合意の無い基準で push が止まる
  - **検出 0 件時の出力**: 「品質チェック」セクションは残し、0 件になった理由を明示する。種別ごとに、その種別の節の規則が `— <チェック名>（理由）` のスキップ行を出すならそれを並べ、出さない種別には下の表の行を書く

    | 場合 | 出力 |
    | --- | --- |
    | 種別を 1 つも検出できなかった | `（プロジェクト種別を検出できなかったため全チェックをスキップ）` |
    | 種別は検出したが、どのチェックも条件を満たさなかった | `（<種別> を検出したが <チェックが無い理由>ため全チェックをスキップ）` |

    例: `（Python を検出したが ruff / mypy / pytest が入っていないため全チェックをスキップ）`、`（Makefile を検出したが lint / check / test / build ターゲットが無いため全チェックをスキップ）`。
    コマンドが入っているかは、条件の列に書かれていない限り 0 件の理由にしない。流すと決まったチェックのコマンドが無ければ失敗として扱う（Node.js の PM は先に上の PATH 解決のフォールバックに従う。見つからないときの確認を含む）

### Step 3: push の実行

すべてのチェックに通過したら（またはチェック不要の場合）、まず作業ツリーを取り直す。

```bash
git status --porcelain --untracked-files=no
```

出力が空でなければ、チェックが追跡ファイルを書き換えている（`eslint --fix` や整形ツールなど）。通ったのは書き換えた後の作業ツリーで、push するコミットではないので、どのモードでも push しない。書き換わったファイルを報告し、コミットしてから push し直すか中断するかを提示する（対話時は `AskUserQuestion`、非対話時は最終応答）。事前指示済みでもこの問いは省略しない。push の承認は、書き換わったファイルのコミットまでは含まない。
未追跡のファイルは見ない。チェックを流す前からあった未追跡のファイルは Step 1 で止めているので、この時点にある未追跡のファイルはチェックが作ったもの（ビルドの生成物など）で、チェックした内容と push するコミットの違いにはならない。

出力が空なら:

1. push コマンドをユーザーに提示する
2. `AskUserQuestion` で最終確認を行う（省略するかは冒頭の「Step 2 / Step 3 の承認」に従う）
3. 承認を得たら push を実行する

```bash
git push <remote> <branch>
```

#### 初回 push（Step 1 の表で初回 push と決めた場合）

```bash
git push -u <remote> <branch>
```

#### チェックが作った未追跡のファイル

チェックを流したら、push したかどうか（失敗・書き換え・確認で断られた場合を含む）にかかわらず、最終報告の前に流す。

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
- ✓ build
- ✓ lint
- ✗ test（失敗）
- — audit（前段失敗のため未実行）
```
