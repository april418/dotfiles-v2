---
name: git-workflow
description: Git 操作を行う際に常に遵守すべきブランチ運用・コミット・push のルール。GitHub Flow に従ったブランチモデル、ベースブランチの判定、コミット / push スキルへの委譲を徹底する。あらゆる git 操作（ブランチ作成、コミット、push、マージ、checkout 等）を行う前に参照する。
---

# 概要

このスキルは Git 操作時に **常に意識すべき原則** をまとめたものである。
個別のワークフローではなく、git 関連の作業を行う際の行動規範として機能する。

git コマンドを実行する、または実行しようとするあらゆる場面で以下のルールを遵守すること。

## ルール 1: ブランチモデルは GitHub Flow に従う

扱ってよいブランチは以下のいずれかに限定される。

- **統合ブランチ**: `develop` / `master` / `main`
- **作業ブランチ**: `feature/<name>` / `hotfix/<name>`

それ以外の命名（`fix/xxx`, `chore/xxx`, `topic/xxx` 等）は使用しない。
ユーザーが明示的に別の命名を指示した場合のみ従う。

## ルール 2: 統合ブランチに直接コミットしない

`develop` / `master` / `main` に直接コミット・push してはならない。
作業は必ず `feature/*` または `hotfix/*` ブランチ上で行う。

現在のブランチが統合ブランチのまま変更を加えようとしている場合、
コミット前に `AskUserQuestion` で新しい作業ブランチを切るか確認する。

## ルール 3: ベースブランチの判定ロジック

新しい作業ブランチを切る際のベースは以下の手順で決定する。

1. `git show-ref --verify --quiet refs/heads/develop` が成功する、または
   `git ls-remote --exit-code --heads origin develop` が成功する場合
   → **`develop` から切る**
2. それ以外は `master` または `main` を使用する
   - `main` と `master` の両方が存在する場合は `main` を優先
   - どちらも存在しない場合は `AskUserQuestion` で確認
3. **例外: `hotfix/*` は必ず `master` / `main` から切る**
   - `develop` があっても hotfix では develop を使わない
   - 本番への緊急修正であるため、安定版からの派生が必要

判定は **ローカルとリモートの両方** を確認する。
ローカルに develop がなくてもリモートに存在すればそれを優先する。

## ルール 4: コミットは必ず `git-commit` スキルに委譲する

git 操作のうちコミット作成を行う場面では、**自前で `git commit` を実行しない**。
必ず `git-commit` スキルを呼び出す。

対象となる操作:
- 新規コミットの作成
- 既存変更のコミット分割
- コミットメッセージの作成

例外:
- `git commit --amend --no-edit`（メッセージを変更しない単純な amend）
- merge commit / rebase 中の continue 等、git が自動生成するコミット
- ユーザーが明示的に「amend して」「fixup して」等と指示した場合

## ルール 5: push は必ず `git-push` スキルに委譲する

リモートへの push を行う場面では、**自前で `git push` を実行しない**。
必ず `git-push` スキルを呼び出す。

対象となる操作:
- 通常の push
- 初回 push（`-u` 付き）
- 作業ブランチの push

例外:
- ユーザーが明示的に「品質チェックをスキップして push して」と指示した場合
- `git-push` スキル自身の内部処理

## ルール 6: 破壊的操作には必ず確認を取る

以下の操作はすべて `AskUserQuestion` で事前承認を得る。自発的に実行しない。

- `git push --force` / `--force-with-lease`
- `git reset --hard`
- `git clean -fd`
- `git branch -D`（マージされていないブランチの削除）
- `git rebase`（特に push 済みブランチに対するもの）
- `git checkout -- <file>` / `git restore <file>`（未コミット変更の破棄）
- stash の `drop` / `clear`

`main` / `master` への force push をユーザーが要求した場合はリスクを警告する。

## ルール 7: 未コミット変更の扱い

ブランチ切り替え・pull・ベース更新の前には必ず作業ツリーの状態を確認する。

```bash
git status --short
```

未コミット変更がある状態でブランチ切り替えや pull を行おうとする場合、
`AskUserQuestion` で以下を選択させる:

- 現在のブランチでコミットしてから進める（→ `git-commit` スキル）
- stash して進める
- そのまま持ち込む（`git switch -c` 等、安全な場合のみ）

## ルール 8: 統合ブランチの最新化は `--ff-only`

ベースブランチを最新化する際は fast-forward のみを許可する。

```bash
git pull --ff-only origin <base>
```

`--ff-only` が失敗した場合（ローカルに先行コミットがある等）は、
`AskUserQuestion` でユーザーに状況を報告し指示を仰ぐ。
勝手に rebase / merge しない。

## ルール 9: スコープを逸脱しない

このスキルの対象外の操作は、ユーザーから明示的に要求された場合のみ行う。

- PR の作成（`gh pr create` 等）
- タグの作成・push
- リモートの追加・削除
- submodule 操作
- git config の変更

## チェックリスト

git 操作を行う前に、以下を自問する:

- [ ] 現在のブランチは作業ブランチ（`feature/*` / `hotfix/*`）か？
- [ ] コミットを作る場合、`git-commit` スキルを呼ぶ段取りになっているか？
- [ ] push する場合、`git-push` スキルを呼ぶ段取りになっているか？
- [ ] 破壊的操作の場合、ユーザー承認を得たか？
- [ ] 未コミット変更の扱いは明確か？
