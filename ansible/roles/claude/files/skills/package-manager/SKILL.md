---
name: package-manager
description: パッケージマネージャー（pnpm, npm, yarn, uv 等）やランタイムバージョンマネージャー（nvm, mise 等）を操作するときのルール。依存関係のインストール・更新・lockfile 再生成・audit 等を行う前に参照する。プロジェクト設定の尊重、正しいランタイムバージョンの使用、lockfile の整合性維持を扱う。
---

# 概要

依存関係に関するコマンド（install, update, add, remove, audit 等）と、ランタイムのバージョンの
切り替えに当てる規則である。

対象ツール:

- **Node.js**: pnpm, npm, yarn
- **Python**: uv, pip
- **ランタイム管理**: nvm, mise

---

## ルール 1: プロジェクト設定・グローバル設定を、設定ファイルを編集せずにバイパスしない

### 原則

設定ファイルに定義された制約を、CLI フラグや環境変数（`pnpm_config_*`、npm と pnpm 10 が読む `npm_config_*`、`UV_EXCLUDE_NEWER` など）で上書き・無効化してはならない。
これらの設定はセキュリティポリシーとして意図的に配置されている。

### 設定ファイルの階層

設定は以下の階層で適用される。
下位（プロジェクト）の設定が上位（グローバル）を上書きする。

**Node.js (pnpm / npm):**

| 階層         | ファイル                                | 読む PM           | 例                                                             |
| ------------ | --------------------------------------- | ----------------- | -------------------------------------------------------------- |
| グローバル   | `~/.npmrc`                              | npm、pnpm 10 以下 | `engine-strict=true`                                           |
| グローバル   | `<pnpm の設定ディレクトリ>/rc`          | pnpm 10 以下      | `engine-strict=true`, `minimum-release-age=10080`              |
| グローバル   | `<pnpm の設定ディレクトリ>/config.yaml` | pnpm 11 以降      | `engineStrict: true`, `minimumReleaseAge: 10080`               |
| プロジェクト | `.npmrc`                                | npm、pnpm 10 以下 | `engine-strict=true`, `minimum-release-age=10080`（pnpm のみ） |
| プロジェクト | `pnpm-workspace.yaml`                   | pnpm              | `engineStrict: true`, `minimumReleaseAge: 10080`               |

`<pnpm の設定ディレクトリ>` は `$XDG_CONFIG_HOME/pnpm`。未設定なら macOS は `~/Library/Preferences/pnpm`、
Linux は `~/.config/pnpm`。pnpm 11 以降は `rc` を読まず、`.npmrc` からは認証・レジストリ・プロキシなどの接続設定しか読まない。

**casing 規則**: `.npmrc` と `rc`（ini 形式）はキーが **kebab-case**、`pnpm-workspace.yaml` と `config.yaml`（YAML）は **camelCase**。
ファイル形式に合わせて表記する。

**Python (uv):**

| 階層         | ファイル                                   | 例                         |
| ------------ | ------------------------------------------ | -------------------------- |
| グローバル   | `~/.config/uv/uv.toml`                     | `exclude-newer = "1 week"` |
| プロジェクト | `pyproject.toml` の `[tool.uv]`, `uv.toml` | `exclude-newer = "1 week"` |

### 禁止される操作

```bash
# Node.js
pnpm install --config.engine-strict=false
pnpm install --config.minimum-release-age=0
pnpm install --config.package-manager-strict=false
pnpm install --pm-on-fail=ignore
pnpm_config_minimum_release_age=0 pnpm install
npm install --engine-strict=false

# Python
uv pip install --exclude-newer=9999-01-01
uv sync --exclude-newer=9999-01-01
UV_EXCLUDE_NEWER=9999-01-01 uv sync
```

### 設定変更が本当に必要な場合

設定ファイル自体を編集し、コミットとして記録する。
一時的な CLI フラグでの無効化ではなく、プロジェクトの方針として変更する。
変更の妥当性に疑問がある場合は `AskUserQuestion` でユーザーに確認する。
リリース年齢の制約（`minimumReleaseAge`・`exclude-newer`）を緩める変更は、ルール 4 のとおり、疑問が無くても承認を取ってから行う。

---

## ルール 2: 正しいランタイムバージョンを使用する

### 確認手順

パッケージマネージャーを実行する前に、
プロジェクトが要求するランタイムバージョンと一致していることを確認する。

**Node.js のバージョン確認先（優先順）:**

1. `package.json` の `engines.node`
2. `.node-version`
3. `.nvmrc`

**Python のバージョン確認先:**

1. `pyproject.toml` の `requires-python`
2. `.python-version`

### バージョンの切り替え

**nvm（Node.js）:**

`<nvm>` は nvm の置き場所で、`NVM_DIR` が空でなければそれ、空なら `$XDG_CONFIG_HOME/nvm`、`XDG_CONFIG_HOME` も空なら `~/.nvm` である（nvm の install.sh と同じ規則）。

```bash
source <nvm>/nvm.sh && nvm use <version>
```

インストールされていない場合:

```bash
source <nvm>/nvm.sh && nvm install <version>
```

**mise（ポリグロット対応）:**

```bash
mise use node@<version>
mise use python@<version>
```

バージョン不一致のまま `engine-strict=false` 等で回避するのはルール 1 違反である。

git-push skill の push 前のチェックで PM を流すときに限り、Node.js のバージョンの確認と切り替えは、照らさずに流す場面も含めて git-push の node.md の「PATH 解決のフォールバック」（「nvm のバージョンの選び方」を含む）と「PATH で見つけた PM の node のバージョン」に従い、**ルール 2 の例外** とする。
git-push は確認先を優先順で 1 つに絞らず、バージョンを切り替えるときは `nvm use` の代わりにそのバージョンの `bin` を `PATH` の先頭に足す。合うバージョンが無くても `nvm install` はしない。

---

## ルール 3: lockfile の整合性を維持する

### lockfile の再生成が必要になるケース

- `package.json` の依存関係を変更した場合
- `pnpm-workspace.yaml` の `overrides` を変更した場合
- `pyproject.toml` の依存関係を変更した場合

変更後は lockfile を再生成する:

```bash
# pnpm
pnpm install --no-frozen-lockfile

# npm
npm install

# yarn
yarn install

# uv
uv lock
```

再生成後は差分を確認し、意図した変更のみであることを検証する:

```bash
git diff pnpm-lock.yaml   # or package-lock.json, yarn.lock, uv.lock
```

### CI 環境との一致

lockfile は CI と同じ条件（同じランタイムバージョン、同じ設定）で生成する。
ローカル環境固有のバイパスフラグを使って生成した lockfile は
CI で `--frozen-lockfile` 実行時に不整合を起こす。

### `ERR_PNPM_LOCKFILE_CONFIG_MISMATCH`

このエラーは `pnpm-workspace.yaml` の `overrides` と `pnpm-lock.yaml` が
不整合であることを示す。CI やビルド（Dockerfile、デプロイ先）の frozen な install に `--no-frozen-lockfile` を
足して通さず、上の「lockfile の再生成が必要になるケース」の手順で lockfile を再生成してコミットする。そこで足すと、
lockfile に無いバージョンがその場で解決されて入りうるうえ、リポジトリの lockfile は不整合のまま残る。

### パッケージマネージャーの混在禁止

1つのプロジェクトで複数のパッケージマネージャーを混在させない。

| lockfile            | 使用すべきマネージャー |
| ------------------- | ---------------------- |
| `pnpm-lock.yaml`    | pnpm                   |
| `package-lock.json` | npm                    |
| `yarn.lock`         | yarn                   |
| `uv.lock`           | uv                     |

`package.json` に `packageManager` があればそれに、無ければ `devEngines.packageManager` があればそれに、ロックファイルより優先して従う（配列ならロックファイルの PM が含まれていればそれ、無ければ先頭）。

---

## ルール 4: リリース年齢制約（minimumReleaseAge / exclude-newer）への対処

パッケージの公開日が制約に満たずインストールに失敗したら、失敗したバージョンを誰が選んだかで扱いを分ける。
制約は公開直後の悪意あるバージョンを避けるための守りなので、どちらでも緩めずに進められる手を既定にする。

- このセッションで自分がバージョンを選んだとき（新しく足す依存、バージョンを指定せずに頼まれた更新）は、制約を
  満たすうちで最も新しいバージョンを入れ直す。バージョンの指定を緩めて PM に選ばせ、入ったバージョンを出力か
  lockfile で確かめる。頼まれたものより古いバージョンになるので、入れたバージョンを最終応答に書く
- ユーザーが名指ししたバージョン、コミット済みの package.json や lockfile の固定、推移的な依存の範囲から来た失敗と、
  制約を満たすバージョンが 1 つも無いパッケージは、書き換えない。誰かが選んだバージョンを下げると、その更新を
  巻き戻すことになる。パッケージ名・バージョン・失敗の出どころ・制約を満たす日時（公開日時に制約の期間を足した
  もの）を報告する

失敗したバージョンでないと困る理由（脆弱性の修正、要る機能など）があるときだけ、除外設定に足すことを提案する。
除外はそのパッケージの守りを緩めるので、パッケージ名・失敗したバージョン・理由・足すファイルを示して
`AskUserQuestion` で承認を取ってから、プロジェクトの設定ファイルに足す（下の書き方）。グローバルの設定は dotfiles が
配っていて、次にプレイブックを流すと戻るので書き換えない。pnpm が除外に足して進めるかを尋ねてきても、承認を
取るまで答えない。失敗したバージョンが制約を満たしたら、足したエントリーを消す。

除外のほかに制約を緩める設定の編集（`minimumReleaseAgeStrict: false`、`minimumReleaseAge` を下げる・外す、uv の
`exclude-newer` を外す・`false` にする）は、除外より広く守りを緩めるので、除外と同じく承認を取ってから行う。
non-strict の pnpm は、失敗せずに制約を満たさないバージョンを入れ、`minimumReleaseAgeExclude` に自分で書き足す
ことがある。install の後に `git diff` で設定ファイルを見て、除外が増えていたら除外と同じく承認を取る。承認が
得られなければ増えた行を消し、上の分け方に戻る。

承認が得られなければ待つ。待つ間は何も書き換えない（既定で入れ直したものはそのまま）。非対話では、除外も制約を
緩める編集もしない。その導入だけ行わずにほかの作業は進め、最終応答にパッケージ名・失敗したバージョン・失敗の
出どころ・除外が要る理由・制約を満たす日時と、除外の案を書く。

`--config.minimum-release-age=0` や `--exclude-newer=9999-01-01` のような CLI フラグや環境変数で制約を無効化しない（ルール 1）。

### 除外設定の書き方

除外は、承認したバージョンだけに効く形で書く。パッケージ名だけのエントリーや `false` は、そのパッケージの
これから出るバージョンまで制約から外す。

pnpm（`pnpm-workspace.yaml`）:

```yaml
minimumReleaseAgeExclude:
  - cool-pkg@1.2.3
  - "@scope/another-pkg@4.5.6 || 4.5.7"
```

1 エントリーに 1 パッケージを `名前@バージョン` で書き、複数のバージョンは `||` で並べる。範囲（`^1.2.3`）は
受け付けない。この書き方は pnpm 12.6.0 で確かめたもので、pnpm 10・11 で使えるかは確かめていない。

uv（`pyproject.toml` の `[tool.uv]`、または `uv.toml`）:

```toml
[tool.uv]
# 承認したバージョンの公開の直後の日時を、そのパッケージにだけ指定する
exclude-newer-package = { cool-pkg = "2026-11-20T00:00:00Z" }
```

uv にはバージョン単位の除外が無いので、承認したバージョンまでが入る日時を指定する。日時より後に出たバージョンは、
エントリーを消すまで入らない。

---

## ルール 5: pnpm 10 以下の audit が 410 を返したとき

pnpm 10 以下の `pnpm audit` は、npm が廃止を予告している旧エンドポイント
（`/-/npm/v1/security/audits` と `/audits/quick`）を使うため、410 で失敗することがある
（pnpm/pnpm#11265）。pnpm 11 以降は後継の `/-/npm/v1/security/advisories/bulk` を使う。

`ERR_PNPM_AUDIT_BAD_RESPONSE` で 410 が出たら、pnpm 11 を一時的に取ってきて audit する。
`--prod` など audit に渡していた引数はそのまま付ける。

```bash
pnpm dlx pnpm@11 --pm-on-fail=ignore audit --prod
```

- `--pm-on-fail=ignore` を外すと、pnpm 11 はプロジェクトが宣言した pnpm 10 との食い違いで止まるか、pnpm 10 に切り替わって同じ 410 になる
- pnpm 11 は pnpm 10 の audit の除外設定を一部読まない。package.json の `pnpm` フィールドは丸ごと無視し、`pnpm-workspace.yaml` の `auditConfig.ignoreCves` も読まない。除外していた脆弱性でも失敗するので、報告にその旨を添える
- pnpm 11 は Node.js 22.13 以上が要る。Node.js がそれより古いとき、または pnpm 11 でも失敗したときは、ほかの回避を試さず audit の失敗として報告する
- `--ignore-registry-errors` では回避しない。レジストリのエラーを成功扱いにし、脆弱性を見ないまま通してしまう

この audit で `pnpm dlx pnpm@11` に渡す `--pm-on-fail=ignore` に限り、**ルール 1 の例外** とする。
`pnpm dlx` で取ってきた一時的な pnpm にプロジェクトの PM の宣言を無視させるだけで、
プロジェクトの依存関係や lockfile には影響しないためである。

---

## チェックリスト

パッケージマネージャーを操作する前に、以下を自問する:

- [ ] ランタイムバージョンはプロジェクトの要求と一致しているか？（git-push の push 前のチェックでは、ルール 2 の例外のとおり git-push の手順に従う）
- [ ] CLI フラグでプロジェクト設定やグローバル設定をバイパスしていないか？
- [ ] リリース年齢制約に当たったとき、失敗したバージョンを誰が選んだかを見て、自分が選んだものだけを入れ直したか？
- [ ] 制約を緩める編集（除外を含む）は承認を取ってから行い、除外は承認したバージョンだけに効く形にしたか？ install の後に除外が増えていないか？
- [ ] lockfile の再生成が必要な変更をしていないか？
- [ ] 使用しているパッケージマネージャーはプロジェクトのものと一致しているか？
