---
name: package-manager
description: パッケージマネージャー（pnpm, npm, yarn, uv 等）やランタイムバージョンマネージャー（nvm, mise 等）を操作する際に常に遵守すべきルール。依存関係のインストール・更新・lockfile 再生成・audit 等を行う前に参照する。プロジェクト設定の尊重、正しいランタイムバージョンの使用、lockfile の整合性維持を徹底する。
---

# 概要

このスキルはパッケージマネージャー・ランタイムバージョンマネージャー操作時に
**常に意識すべき原則** をまとめたものである。

対象ツール:

- **Node.js**: pnpm, npm, yarn
- **Python**: uv, pip
- **ランタイム管理**: nvm, mise

依存関係に関するコマンド（install, update, add, remove, audit 等）を
実行するあらゆる場面で以下のルールを遵守すること。

---

## ルール 1: プロジェクト設定・グローバル設定を絶対にバイパスしない

### 原則

設定ファイルに定義された制約を CLI フラグで上書き・無効化してはならない。
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
# Node.js — 絶対にやってはいけない
pnpm install --config.engine-strict=false
pnpm install --config.minimumReleaseAge=0
pnpm install --config.package-manager-strict=false
pnpm install --pm-on-fail=ignore
npm install --engine-strict=false

# Python — 絶対にやってはいけない
uv pip install --exclude-newer=9999-01-01
uv sync --exclude-newer=9999-01-01
```

### 設定変更が本当に必要な場合

設定ファイル自体を編集し、コミットとして記録する。
一時的な CLI フラグでの無効化ではなく、プロジェクトの方針として変更する。
変更の妥当性に疑問がある場合は `AskUserQuestion` でユーザーに確認する。

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

```bash
source ~/.nvm/nvm.sh && nvm use <version>
```

インストールされていない場合:

```bash
source ~/.nvm/nvm.sh && nvm install <version>
```

**mise（ポリグロット対応）:**

```bash
mise use node@<version>
mise use python@<version>
```

バージョン不一致のまま `engine-strict=false` 等で回避するのは **ルール 1 違反** である。

git-push skill の push 前のチェックで PM を流すときに限り、Node.js の版の確認と切り替えは、照らさずに流す場面も含めて git-push の「PATH 解決のフォールバック」（「nvm の版の選び方」を含む）と「PATH で見つけた PM の node の版」に従い、**ルール 2 の例外** とする。
git-push は確認先を優先順で 1 つに絞らず、版を切り替えるときは `nvm use` の代わりにその版の `bin` を `PATH` の先頭に足す。合う版が無くても `nvm install` はしない。

---

## ルール 3: lockfile の整合性を維持する

### lockfile の再生成が必要になるケース

- `package.json` の依存関係を変更した場合
- `pnpm-workspace.yaml` の `overrides` を変更した場合
- `pyproject.toml` の依存関係を変更した場合

変更後は必ず lockfile を再生成する:

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

lockfile は **CI と同じ条件**（同じランタイムバージョン、同じ設定）で生成する。
ローカル環境固有のバイパスフラグを使って生成した lockfile は
CI で `--frozen-lockfile` 実行時に不整合を起こす。

### `ERR_PNPM_LOCKFILE_CONFIG_MISMATCH`

このエラーは `pnpm-workspace.yaml` の `overrides` と `pnpm-lock.yaml` が
不整合であることを示す。`--no-frozen-lockfile` で回避するのではなく、
lockfile を再生成して整合性を取る。

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

パッケージの公開日が制約に満たずインストールに失敗した場合、
以下のいずれかで対処する:

1. **待つ**: パッケージが公開されて十分な期間が経過するのを待つ
2. **除外設定に追加**: 設定ファイルに除外を追加する（CLI フラグではなくファイル編集）
   - **pnpm** (`pnpm-workspace.yaml`):

     ```yaml
     minimumReleaseAge: 10080
     minimumReleaseAgeExclude:
       - cool-pkg
       - "@scope/another-pkg"
     ```

     除外は **配列** で 1 パッケージずつ指定する。globパターン不可。

   - **uv** (`pyproject.toml` の `[tool.uv]`、または `uv.toml`):

     ```toml
     [tool.uv]
     exclude-newer = "1 week"  # 全体に効くグローバル制約
     # 個別パッケージの除外は dict 形式: { package = "日付" or false }
     # - 日付（RFC 3339 形式）を渡すとそのパッケージはその日付までに公開された版のみ許可
     # - false を渡すと、そのパッケージのみ exclude-newer 制約から完全除外
     exclude-newer-package = { cool-pkg = "2025-12-31T00:00:00Z", another-pkg = false }
     ```

     注: `exclude-newer-package` キーは uv 公式 API（公式ドキュメント参照）。`[tool.uv.sources]` 配下のオプションではない。

3. **バージョンを下げる**: 制約を満たす古いバージョンを使用する

**絶対にやってはいけないこと:**
`--config.minimumReleaseAge=0` や `--exclude-newer=9999-01-01` で制約を無効化すること。

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
- [ ] lockfile の再生成が必要な変更をしていないか？
- [ ] 使用しているパッケージマネージャーはプロジェクトのものと一致しているか？
