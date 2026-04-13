---
name: git-push
description: リモートへの push 前に品質チェック（build, lint, test, audit 等）を実行し、安全にプッシュする。プロジェクトのツールチェインを自動検出してチェックを行う。
---

# 概要

- このスキルはリモートブランチへの push を行う。
- push 前にプロジェクト固有の品質チェックを自動検出・実行する。
- すべてのチェックに通過した場合のみ push を実行する。

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

**Makefile / Taskfile（`Makefile` / `Taskfile.yml` が存在）:**

`lint`, `check`, `test`, `build` ターゲットが定義されていれば実行する。

#### チェック実行の原則

- 検出されたチェックの一覧と実行順をユーザーに提示し、`AskUserQuestion` で承認を得てから実行する。
- チェックをスキップしたい場合はユーザーが指定できる。
- 各チェックの実行結果（成功/失敗）をリアルタイムで表示する。
- **1つでもチェックが失敗した場合は push を中止する。** 失敗内容をユーザーに報告し、修正を促す。
- プロジェクトの種別が検出できない場合、または該当するチェックが1つもない場合は、チェックをスキップして Step 3 に進む。

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
