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
ただし以下のいずれかに該当する場合は **3 箇所すべての確認を省略してよい**。

- **非対話モード**: subagent 実行、CI、Auto Mode 等、ユーザーへの問い合わせができないコンテキスト
- **明確な前提条件揃い**: 全チェック成功（または検出 0 件）+ 未コミット変更なし + tracking branch が一意に確定 + 単一の upstream 候補（origin 1 つ）
- **ユーザーが事前指示済み**: 直近のユーザー指示で push 実行が明示的に承認されている

省略した場合の振る舞い:

- **Step 1 で中止条件を検出した場合**（未コミット変更あり / push 対象 0 件 / tracking 不明 等）: push は実行せず、検出内容と次に取りうる方針（コミット / stash / 中断等）を最終応答で 3〜4 択で提示する
- **Step 2 / Step 3 の承認**: 前提条件揃いの場合のみ省略可。最終応答（または Discretionary fill-ins 相当の箇所）に「どの判断で承認を省略したか」を 1 行で明記する

なお、**チェックが 1 つでも失敗した場合は省略不可** — どのモードでも必ず失敗内容を報告し push を中止する。

## ワークフロー

### Step 1: 現在の状態を確認

```bash
git status --short
```

```bash
git branch -vv --contains HEAD
```

```bash
git log --oneline @{upstream}..HEAD 2>/dev/null || git log --oneline -5
```

以下を確認する:

1. **未コミットの変更がないこと** — 未コミットの変更がある場合は `AskUserQuestion` でユーザーに報告し、先にコミットするか stash するか確認する。push は行わない。
2. **push 先のリモート・ブランチ** — tracking branch がない場合は `AskUserQuestion` でユーザーに push 先を確認する。
3. **push 対象のコミット** — upstream との差分コミット一覧をユーザーに表示する。push するコミットが 0 件の場合は「push するコミットがない」旨を伝えて終了する。

### Step 2: プロジェクトの品質チェックを自動検出・実行

プロジェクトルートのファイル構成からツールチェインを自動検出し、
利用可能なチェックを順に実行する。

#### 検出ロジック

以下の優先順で検出する。該当しないものはスキップする。

**Node.js プロジェクト（`package.json` が存在）:**

パッケージマネージャーの検出順: `bun.lock` → `pnpm-lock.yaml` → `yarn.lock` → `package-lock.json`。
該当するロックファイルのマネージャーを使用する。いずれもなければ `npm` を使用する。

**PATH 解決のフォールバック**: 非ログインシェル（subagent の Bash 等）では `nvm` 配下の `node` / `pnpm` / `npm` が `PATH` に入っていないことがある。`command -v <pm>` で見つからない場合は以下の優先順で探索する:

1. `~/.nvm/versions/node/*/bin/<pm>` の最新版
2. `~/.local/share/pnpm/<pm>` 等の標準的な install path
3. `corepack <pm>@latest` （corepack 利用可能時）

それでも見つからなければ `AskUserQuestion` でユーザーに PM の場所を確認する（非対話モード時はチェックスキップして失敗扱いで中止）。

| チェック | 条件 | コマンド |
|---------|------|---------|
| build | `scripts.build` が定義されている | `<pm> run build` |
| lint | `scripts.lint` が定義されている | `<pm> run lint` |
| type-check | `scripts.typecheck` または `scripts.type-check` が定義されている | `<pm> run typecheck` or `<pm> run type-check` |
| test | `scripts.test` が定義されている | `<pm> run test` |
| audit | 常に実行 | `<pm> audit` (`pnpm` の場合は `pnpm audit --prod`) |

**Python プロジェクト（`pyproject.toml` / `setup.py` / `setup.cfg` が存在）:**

| チェック | 条件 | コマンド |
|---------|------|---------|
| lint | `ruff` がインストール済み | `ruff check .` |
| type-check | `mypy` がインストール済み | `mypy .` |
| test | `pytest` がインストール済み | `pytest` |

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

#### チェック実行の原則

- 検出されたチェックの一覧と実行順をユーザーに提示し、`AskUserQuestion` で承認を得てから実行する（冒頭「実行モード」の省略条件参照）。
- チェックをスキップしたい場合はユーザーが指定できる。
- 各チェックの実行結果（成功/失敗）をリアルタイムで表示する。
- **失敗時の優先規則（同時発生時の判断）**:
  1. **1 つでもチェックが失敗した時点で残りのチェックは打ち切ってよい**（`audit は常に実行` のような原則よりも「失敗で中止」が優先）。打ち切ったチェックは出力で `—（前段失敗のため未実行）` と明記する
  2. 失敗内容をユーザーに報告し push を中止する
  3. 非対話モードでもこの中止は省略不可
- プロジェクトの種別が検出できない場合、または該当するチェックが1つもない場合は、チェックをスキップして Step 3 に進む。
  - **検出 0 件時の出力**: 「品質チェック」セクションは残し、`（プロジェクト種別を検出できなかったため全チェックをスキップ）` と 1 行で明示する

### Step 3: push の実行

すべてのチェックに通過したら（またはチェック不要の場合）:

1. push コマンドをユーザーに提示する
2. `AskUserQuestion` で最終確認を行う
3. 承認を得たら push を実行する

```bash
git push <remote> <branch>
```

#### 初回 push（tracking branch がない場合）

```bash
git push -u <remote> <branch>
```

### force push について

- `--force` や `--force-with-lease` は**ユーザーが明示的に要求した場合のみ**使用する。
- スキルから自発的に force push を提案しない。
- main / master ブランチへの force push をユーザーが要求した場合は、リスクを警告する。

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
```
