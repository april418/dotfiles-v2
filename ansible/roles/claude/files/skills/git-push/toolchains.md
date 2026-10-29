# Node.js 以外の種別のチェック

SKILL.md の Step 2 で、Python / Rust / Go / Ansible / Docker / Makefile / Taskfile のどれかを検出したときに読む。チェックの名前、スキップ行、失敗したときの扱いは SKILL.md の「チェック実行の原則」に従う。

## 目次

- ツールがインストール済みかの判定
- Python
- Rust
- Go
- Ansible
- Docker
- Makefile / Taskfile

## ツールがインストール済みかの判定

表の条件の「`<ツール>` がインストール済み」は次のとおりに判定する。入っていなければ SKILL.md の「流さないチェックの書き方」のスキップ行にする。

| ツール                                                | 判定                                                                                   | 流すコマンド                                                                                      |
| ----------------------------------------------------- | -------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| Python の表（`ruff` / `mypy` / `pytest`）             | プロジェクトルートの `.venv/bin/<ツール>` が実行可能か。無ければ `command -v <ツール>` | `.venv/bin/<ツール>` で見つけたら、表のコマンドの先頭をそのパスにする（`.venv/bin/ruff check .`） |
| `clippy` / `cargo-audit`                              | `cargo clippy --version` / `cargo audit --version` が exit 0 か                        | 表のとおり                                                                                        |
| ほか（`golangci-lint` / `ansible-lint` / `hadolint`） | `command -v <ツール>`                                                                  | 表のとおり                                                                                        |

`.venv/bin` を先に見るのは、uv などがプロジェクトルートに作る `.venv` のツールは、venv を有効にしないと `PATH` に無いため。`PATH` の pytest は自分の環境で動くので、`.venv` に入れたプロジェクトの依存を import できない。
`uv run` は使わない。`.venv` や `uv.lock` が無ければ作り、`pyproject.toml` と食い違う `uv.lock` を書き換える（uv 0.13.1 で実測）。
`clippy` という実行ファイルは無く、`cargo clippy` の実体の `cargo-clippy` は rustup がコンポーネントの有無によらず置く proxy なので、`command -v` では判定できない。

## Python

`pyproject.toml` / `setup.py` / `setup.cfg` が存在するとき。

| チェック   | 条件                        | コマンド       |
| ---------- | --------------------------- | -------------- |
| lint       | `ruff` がインストール済み   | `ruff check .` |
| type-check | `mypy` がインストール済み   | `mypy .`       |
| test       | `pytest` がインストール済み | `pytest`       |

pytest は収集・選択されたテストが 0 件だと exit 5 で終わる。`uv init` 直後、テスト関数の無い `test_*.py` だけのとき、`addopts` の `-m` / `-k` で全件が外れたときがこれに当たる。テストがあっても `testpaths` / `python_files` の設定や全モジュールの `importorskip` で 0 件になれば同じく exit 5 で、区別しない。
exit 5 は失敗に数えない。push の可否を決める判定（SKILL.md の「チェックが 1 つでも失敗したら」と、Step 3 の「すべてのチェックに通過したら」）では通過として扱い、出力だけ `— Python test（実行するテストが 0 件のためスキップ。pytest の exit 5: <最終行>）` と書く。`<最終行>` は pytest の最後の行から `=` と所要時間を除いたもの（`no tests ran` / `1 deselected` など）。
exit 5 以外の 0 でない終了コードは失敗である。この扱いは Python の表から流した `pytest` に限る。Makefile / Taskfile のターゲットや `scripts.test` から呼ばれた pytest は、テストが 0 件でもそのツールの終了コードで判定する。それらはプロジェクトが定めた入口なので、その終了コードをそのまま採る。表の `pytest` は skill が選んだコマンドなので、exit 5 の読み方も skill が決めてよい。make の出力と報告の書き方は下の「Makefile / Taskfile」にある。

## Rust

`Cargo.toml` が存在するとき。

| チェック | 条件                             | コマンド                      |
| -------- | -------------------------------- | ----------------------------- |
| build    | 常に実行                         | `cargo build`                 |
| lint     | `clippy` がインストール済み      | `cargo clippy -- -D warnings` |
| test     | 常に実行                         | `cargo test`                  |
| audit    | `cargo-audit` がインストール済み | `cargo audit`                 |

## Go

`go.mod` が存在するとき。

| チェック | 条件                               | コマンド            |
| -------- | ---------------------------------- | ------------------- |
| build    | 常に実行                           | `go build ./...`    |
| vet      | 常に実行                           | `go vet ./...`      |
| lint     | `golangci-lint` がインストール済み | `golangci-lint run` |
| test     | 常に実行                           | `go test ./...`     |

## Ansible

`ansible.cfg` または `playbook.yml` が存在するとき。

| チェック     | 条件                              | コマンド                                       |
| ------------ | --------------------------------- | ---------------------------------------------- |
| lint         | `ansible-lint` がインストール済み | `ansible-lint`                                 |
| syntax-check | `playbook.yml` が存在             | `ansible-playbook --syntax-check playbook.yml` |

syntax-check はプロジェクトルートの `playbook.yml` にだけ流す。ほかの YAML を playbook とみなすのは推測で、vars やタスクのリストに流すと落ちる。ほかの playbook は ansible-lint に任せる（外せない syntax-check ルールで、見つけた playbook すべてに `ansible-playbook --syntax-check` を流す）。

## Docker

`Dockerfile` または `compose.yml` / `docker-compose.yml` が存在するとき。

| チェック       | 条件                                                 | コマンド                        |
| -------------- | ---------------------------------------------------- | ------------------------------- |
| lint           | `Dockerfile` が存在し、`hadolint` がインストール済み | `hadolint Dockerfile`           |
| build          | `Dockerfile` が存在                                  | `docker build --check .`        |
| compose-config | `compose.yml` / `docker-compose.yml` が存在          | `docker compose config --quiet` |

## Makefile / Taskfile

`Makefile` / `Taskfile.yml` が存在するとき。`lint`, `check`, `test`, `build` ターゲットが定義されていれば実行する（順は SKILL.md の「検出ロジック」）。

ターゲットから呼ばれた pytest のテストが 0 件だと、make は exit 2 で終わる。最終行は `make: *** [test] Error 5` で、その直前の行は、要約を出す設定なら pytest の要約になる（既定では `=` で囲まれた `no tests ran in 0.00s`、`-q` では囲みが無い。`-qq` では要約が出ず空行。GNU Make 3.81 と pytest 9.1.1 で実測）。これも失敗として push を止める（理由は上の「Python」の exit 5 の段落）。
最終行が `Error 5` で終わり、直前の行が pytest の要約で `passed` / `failed` / `error` / `skipped` のどれも含まない（`no tests ran` / `1 deselected` / `1 warning` など）ときは、失敗の報告に原因と直し方を添える。make の `Error 5` はレシピのどのコマンドが 5 を返しても出るので、要約の行が無ければ添えない。この判定は make の出力の形に合わせたもので、task には当てはめない。

```
- ✗ make test（失敗。pytest の実行するテストが 0 件で exit 5。テストを足すか、0 件を通すなら Makefile 側で `pytest || [ $$? -eq 5 ]` のように exit 5 を成功に変える）
```
