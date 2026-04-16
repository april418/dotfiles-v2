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

| 階層 | ファイル | 例 |
|------|---------|-----|
| グローバル | `~/.npmrc`, `~/.config/pnpm/rc` | `engine-strict=true`, `minimum-release-age=10080` |
| プロジェクト | `.npmrc`, `pnpm-workspace.yaml` | `engineStrict: true`, `minimumReleaseAge: 10080` |

**Python (uv):**

| 階層 | ファイル | 例 |
|------|---------|-----|
| グローバル | `~/.config/uv/uv.toml` | `exclude-newer = "1 week"` |
| プロジェクト | `pyproject.toml` の `[tool.uv]`, `uv.toml` | `exclude-newer = "1 week"` |

### 禁止される操作

```bash
# Node.js — 絶対にやってはいけない
pnpm install --config.engine-strict=false
pnpm install --config.minimumReleaseAge=0
pnpm install --config.package-manager-strict=false
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

| lockfile | 使用すべきマネージャー |
|----------|---------------------|
| `pnpm-lock.yaml` | pnpm |
| `package-lock.json` | npm |
| `yarn.lock` | yarn |
| `uv.lock` | uv |

`package.json` の `packageManager` フィールドがある場合はそれに従う。

---

## ルール 4: リリース年齢制約（minimumReleaseAge / exclude-newer）への対処

パッケージの公開日が制約に満たずインストールに失敗した場合、
以下のいずれかで対処する:

1. **待つ**: パッケージが公開されて十分な期間が経過するのを待つ
2. **除外設定に追加**: 設定ファイルに除外を追加する
   - pnpm: `pnpm-workspace.yaml` の `minimumReleaseAgeExclude`
   - uv: `pyproject.toml` の `[tool.uv]` 配下で個別に指定
3. **バージョンを下げる**: 制約を満たす古いバージョンを使用する

**絶対にやってはいけないこと:**
`--config.minimumReleaseAge=0` や `--exclude-newer=9999-01-01` で制約を無効化すること。

---

## ルール 5: pnpm audit の実行方法（暫定対応）

pnpm v10.x では `pnpm audit` が npm レジストリの旧エンドポイント廃止により
410 エラーで動作しない（pnpm/pnpm#11265）。

代替コマンド:

```bash
pnpm dlx pnpm@11.0.0-rc.1 audit
```

CI 環境では `minimumReleaseAge` と `packageManagerStrictVersion` の
制約により `pnpm dlx` 自体が失敗するため、以下のように実行する:

```bash
pnpm dlx --config.minimumReleaseAge=0 pnpm@11.0.0-rc.1 --config.package-manager-strict=false audit
```

**注意:** `pnpm dlx` で一時的に別バージョンの pnpm を実行する場合の
`--config` フラグは **ルール 1 の例外** とする。
これは `pnpm dlx` 自体の実行に必要な設定であり、
プロジェクトの依存関係や lockfile に影響しないためである。
pnpm 11 が正式リリースされたらこの回避策は不要になる。

---

## チェックリスト

パッケージマネージャーを操作する前に、以下を自問する:

- [ ] ランタイムバージョンはプロジェクトの要求と一致しているか？
- [ ] CLI フラグでプロジェクト設定やグローバル設定をバイパスしていないか？
- [ ] lockfile の再生成が必要な変更をしていないか？
- [ ] 使用しているパッケージマネージャーはプロジェクトのものと一致しているか？
