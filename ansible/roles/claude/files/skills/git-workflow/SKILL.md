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

### `<name>` 部分の命名規約

`feature/<name>` / `hotfix/<name>` の `<name>` 部分は以下に従う。

- **文字種**: ASCII 英小文字 / 数字 / `-` のみ。`_` や空白、日本語は使わない
- **区切り**: `kebab-case`（`user-authentication`、`payment-bug-fix` 等）
- **長さ**: 概ね 3〜40 文字。短すぎ（`x`, `fix`）も長すぎも避ける
- **内容**: 何の作業かが他人に伝わる名詞句（変更対象 + 目的）
  - 良い: `feature/user-authentication`、`hotfix/payment-rounding`
  - 悪い: `feature/work`、`feature/april418-1`、`hotfix/bug`
- **issue 番号がある場合**: 末尾に `-<番号>` を付けてよい（例: `feature/login-form-321`）

### `<name>` の決定主体

デフォルト動作は以下の通り。**推測のまま勝手に決めない**。

1. ユーザーの指示や変更対象から `<name>` を **AI が 1〜3 個提案** する
2. `AskUserQuestion` で候補を提示し、ユーザーに選択 / 修正 / 自由入力させる
3. ユーザーが既に明示的に名前を指定している場合は確認をスキップしてよい

提案できる材料がない場合（指示が極端に抽象的等）は、`AskUserQuestion` で「何の作業をするか」を先に確認する。

## ルール 2: 統合ブランチに直接コミットしない

`develop` / `master` / `main` に直接コミット・push してはならない。
作業は必ず `feature/*` または `hotfix/*` ブランチ上で行う。

現在のブランチが統合ブランチのまま変更を加えようとしている場合、
コミット前に `AskUserQuestion` で新しい作業ブランチを切るか確認する。

## ルール 3: ベースブランチの判定ロジック

新しい作業ブランチを切る手順は **3 ステップ** で行う: **(a) 選定 → (b) 取得・更新 → (c) 派生**。
途中を省略しない。

### (a) ベース選定

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

### (b) ベースの取得・更新（派生直前に実施）

選定したベースは **派生直前にリモート最新へ追従させる**。古い HEAD から切ると競合・rebase 苦労の原因になる。

#### 通常ケース（作業ツリーが clean）

```bash
# ローカルにベースが存在する場合: 一旦 checkout してから rebase pull
git switch <base>
git pull --rebase origin <base>

# ローカルにベースが存在しない（リモートのみ）場合: fetch して直接派生に使う
git fetch origin <base>
```

#### 例外 1: 作業ツリーに未コミット変更がある場合

まず **ルール 7** で `AskUserQuestion` を出し、3 択のいずれかをユーザーに選ばせる。
選択肢ごとに (b) → (c) の続きが分岐する:

- **「コミットしてから進める」を選んだ場合** → `git-commit` スキルで現ブランチにコミット後、通常ケースに復帰
- **「stash して進める」を選んだ場合**:

  ```bash
  git stash push -u
  git switch <base>
  git pull --rebase origin <base>
  git switch -c <new-branch>   # (c) 派生
  git stash pop
  ```

  この場合は (b) 取得・更新を **完遂** する。

- **「そのまま持ち込む」を選んだ場合**:

  ```bash
  git switch -c <new-branch>    # 現在の作業ツリーごと新ブランチへ
  ```

  この場合は **(b) 取得・更新を意図的にスキップ** する（pull を走らせると未コミット変更が衝突するため）。
  ベースは古い HEAD のままになるが、未コミット変更の保護を優先する判断である。新ブランチ上で後ほど `git rebase <base>` で追従可能（ルール 8）。

#### 例外 2: オフライン等で fetch / pull が失敗する場合

`AskUserQuestion` で「ローカル HEAD のまま切るか中断するか」を確認する。
「ローカル HEAD のまま切る」を選んだ場合は (b) をスキップして (c) へ。

### (c) 派生

更新済みのベースから新ブランチを切る。

```bash
# ローカルにベースがある場合
git switch -c <new-branch> <base>

# リモートのみの場合（fetch 済みを利用）
git switch -c <new-branch> origin/<base>
```

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

### 選択肢の前提条件（必ず確認）

**現在のブランチが統合ブランチ（`develop` / `master` / `main`）の場合**:
「現在のブランチでコミットしてから進める」は **ルール 2 違反になるため選択肢から除外** する。
残る 2 択（stash / そのまま持ち込む）を提示し、推奨は「そのまま持ち込む」（最短経路、未コミット変更の保護）。

**現在のブランチが既に作業ブランチ（`feature/*` / `hotfix/*`）の場合**:
3 択すべて提示可能。

## ルール 8: `git merge` は使用禁止、rebase で統合する

`git merge` は使用しない。ブランチの統合は rebase で行う。

- `git pull` は常に `--rebase` を付ける
- 作業ブランチをベースブランチに追従させる場合も `git rebase <base>` を使う
- `git merge` を使ってよいのはユーザーが明示的に指示した場合のみ

```bash
# pull 時は必ず --rebase
git pull --rebase origin <branch>

# ベースブランチへの追従
git rebase <base>
```

rebase 中にコンフリクトが発生した場合は、
`AskUserQuestion` でユーザーに状況を報告し指示を仰ぐ。
勝手に `--abort` / `--skip` しない。

## ルール 9: スコープを逸脱しない

このスキルの対象外の操作は、ユーザーから明示的に要求された場合のみ行う。

- PR の作成（`gh pr create` 等）
- PR のマージ（`gh pr merge` 等）
- タグの作成・push
- リモートの追加・削除
- submodule 操作
- git config の変更

### PR マージ時の戦略（明示要求があった場合のみ適用）

ユーザーがマージを要求した場合は **必ず merge commit 形式** を使う。

```bash
gh pr merge <number> --merge
```

`--squash` / `--rebase` は使用しない。理由:

- マージ履歴が残るため、後で「どの PR でこの変更が入ったか」を `git log --first-parent` で辿れる
- 個別コミットの粒度（git-commit skill で revert 可能性最優先に設計したもの）を保てる
- squash は粒度を潰し、rebase は merge commit のメタ情報（PR 番号への参照等）を失わせる

ユーザーが明示的に `--squash` / `--rebase` を指示した場合のみ従う。
`main` / `master` への force push 同様、リスクを警告した上で実行する。

ルール 8（ローカルでの `git merge` 禁止）と矛盾しないこと:

- **ローカルブランチの統合**: `git rebase`（ルール 8）
- **リモート PR のマージ**: `gh pr merge --merge`（このルール）

両者は対象が異なる。

## チェックリスト

git 操作を行う前に、以下を自問する:

- [ ] 現在のブランチは作業ブランチ（`feature/*` / `hotfix/*`）か？
- [ ] コミットを作る場合、`git-commit` スキルを呼ぶ段取りになっているか？
- [ ] push する場合、`git-push` スキルを呼ぶ段取りになっているか？
- [ ] 破壊的操作の場合、ユーザー承認を得たか？
- [ ] 未コミット変更の扱いは明確か？
- [ ] `git merge` ではなく rebase を使っているか？
- [ ] PR マージ時は `--merge`（merge commit）を使っているか？
- [ ] `git pull` に `--rebase` を付けているか？
