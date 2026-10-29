# Node.js プロジェクトのチェック

プロジェクトルートに `package.json` があるときに、SKILL.md の Step 2 から読む。チェックの名前、スキップ行、失敗したときの扱いは SKILL.md の「チェック実行の原則」に従う。

## 目次

- PM の決め方
- audit のコマンド（yarn の版、bun、pnpm 10 の 410）
- PATH 解決のフォールバック
  - nvm の版の選び方
  - 表の場所で見つけたとき
  - 表の場所でも見つからないとき
- PATH で見つけた PM の node の版
- チェックの表
  - pnpm の verifyDepsBeforeRun
  - npm init の既定の test
  - ロックファイルも依存も無いときの audit

## PM の決め方

パッケージマネージャー（PM）は上から順に見て、最初に決まったものを使う。

1. `package.json` の `packageManager`（`pnpm@10.33.0` のような値の `@` より前）
2. `package.json` の `devEngines.packageManager` の `name`。配列なら、3 のロックファイルで決まる PM がどれかの `name` に一致すればそれを、一致しないかロックファイルが無ければ先頭の `name` を使う
3. ロックファイル: `bun.lock` / `bun.lockb` → `pnpm-lock.yaml` → `yarn.lock` → `package-lock.json`
4. どれも無ければ `npm`

宣言（1・2）をロックファイルより先に見るのは、宣言と違う PM で流すと止まるからである（npm は `devEngines.packageManager` が他の PM を指すと `EBADDEVENGINES`、pnpm は `packageManager` が、11 以降は `devEngines.packageManager` も他の PM を指すと `This project is configured to use …` で exit 1）。
宣言とロックファイルが食い違っていても宣言の PM で流す。その PM のロックファイルが無いことで audit などが失敗したら、ほかの失敗と同じく push を止める。

## audit のコマンド

下の「チェックの表」の audit 行の `<pm> audit` は、yarn では `yarn --version` のメジャー版で分ける。

- 1: `yarn audit`
- 2・3: `yarn npm audit --all --recursive`
- 4 以上: `yarn npm audit --all --recursive --no-deprecations`

`yarn npm audit` の既定は今いるワークスペースの直接依存だけなので、`--all` と `--recursive` で全ワークスペースの推移的な依存まで見る。4 以上は非推奨のパッケージも moderate として数えて exit 1 になるので、npm / pnpm と同じく脆弱性だけで止まるよう `--no-deprecations` を付ける（このフラグは 4 から）。
yarn 1 の終了コードは見つかった重大度の値の和（info 1 / low 2 / moderate 4 / high 8 / critical 16）で、info だけでも 0 にならず失敗である。
`yarn --version` は audit を流すと決まったときに、audit の直前に流す。0 以外で終わったら audit のコマンドが決まらないので、audit を流さずに `✗ Node.js audit（失敗。yarn --version が exit <N> で終わった）` と書く。
bun は 1.2.15 で `bun audit` が入ったので、それより前の bun では失敗になる。
pnpm 10 以下の `pnpm audit --prod` が `ERR_PNPM_AUDIT_BAD_RESPONSE` の 410 で失敗したら、package-manager skill のルール 5 の手順で pnpm 11 を使って流し直し、その結果で判定する。出力の `Node.js audit` の行には括弧で `pnpm 10 が 410 を返したため pnpm 11 で流し直した` と書き、ルール 5 が報告に添えるよう求めることも同じ括弧に入れる。

## PATH 解決のフォールバック

非ログインシェル（subagent の Bash 等）では、nvm 配下やスタンドアロンのインストーラで入れた PM が `PATH` に入っていないことがある。`command -v <pm>` で見つかった場合は、下の「PATH で見つけた PM の node の版」で node の版を照らす。見つからない場合は、下の表の場所を上の行から、行の中は左から順に見て、最初に見つかった実行ファイルを使う。

| PM     | 探す場所                                                                                                                                          |
| ------ | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| すべて | `$NVM_DIR/versions/node/*/bin/<pm>` のうち、プロジェクトが求める Node.js の版に合う最も新しいもの（下の「nvm の版の選び方」）                     |
| pnpm   | `$PNPM_HOME/bin/pnpm`、`$PNPM_HOME/pnpm`（`pnpm setup` が pnpm 11 以降は前者、10 以前は後者に置く。プロジェクトが宣言した版では選ばず、両方見る） |
| bun    | `$BUN_INSTALL/bin/bun`                                                                                                                            |

変数が空なら、各インストーラの既定の場所を使う。

| 変数          | 空のときの場所                                                                                            |
| ------------- | --------------------------------------------------------------------------------------------------------- |
| `NVM_DIR`     | `$XDG_CONFIG_HOME/nvm`（`XDG_CONFIG_HOME` も空なら `~/.nvm`）                                             |
| `PNPM_HOME`   | `$XDG_DATA_HOME/pnpm`（`XDG_DATA_HOME` も空なら macOS は `~/Library/pnpm`、ほかは `~/.local/share/pnpm`） |
| `BUN_INSTALL` | `~/.bun`                                                                                                  |

### nvm の版の選び方

`bin/<pm>` が実行できる（`test -x`）版だけを候補にする。プロジェクトルートにある次の指定のすべてに合う候補のうち、最も新しい版を使う。中身が空か空白だけの指定は無いものとする。

- `package.json` の `engines.node`
- `.node-version` の中身
- `.nvmrc` の中身

package-manager skill のルール 2 と同じ確認先だが、優先順で 1 つに絞らない。`engines.node` が `>=18` のような下限だけだと、それだけで選んだ版は `.nvmrc` などで固定した版より新しくなりうる。
指定が 1 つも無ければ、候補を `sort -V` で比べて最も新しい版を使う（文字列で比べると `v9` が `v24` より新しくなる）。
指定があれば、合うかを npm が同梱する semver の CLI で決める。`<nvm>` は上の表で決めた `NVM_DIR` の場所で、展開した絶対パスで書く。
`<最新>` は、候補に限らず `<nvm>/versions/node/` の下で `bin/node` が実行でき、`lib/node_modules/npm/node_modules/semver/bin/semver.js` がある（`test -f`）版のうち、`sort -V` で最も新しいもの。候補の版の npm を使わないのは、npm 6 が同梱する semver 5 系の CLI は `bin/semver` で `.js` が無いため（`npm view npm@6.14.18 dependencies.semver` が `^5.7.1`、`npm view semver@5.7.1 bin` が `./bin/semver`）。`<最新>` が無ければ版を比べられないので、合う版が無い扱いにする。
指定は、読んだ値の前後の空白を除いて単一引用符で 1 つずつ `-r` に渡し、続けて候補の版を並べる。ファイルをシェルで読ませない。`"$(cat .nvmrc)"` は cwd が違うと空になり、`-r ''` はすべての版に合う。

```bash
'<nvm>/versions/node/<最新>/bin/node' '<nvm>/versions/node/<最新>/lib/node_modules/npm/node_modules/semver/bin/semver.js' -r '>=18' -r '24' v20.19.0 v24.15.0
```

すべての `-r` に合う版だけを、`v` を外して古い順に出す（この例では `24.15.0`）。最後の行に `v` を付けた版の `bin`（`<nvm>/versions/node/v24.15.0/bin`）が下の `<dir>` になる。合う版が無ければ何も出さずに exit 1 で終わる（semver 7.7.4 / npm 11.12.1 で実測）。0 以外で終わったら合う版が無い扱いにする。
semver の範囲として読めない指定は、どの版にも合わない。nvm は `.nvmrc` の `#` から後ろをコメントとして除き、`lts/*`・`node` などの alias を版に置き換えて読むが、ここではどちらもせずにそのまま `-r` に渡す。指定が無いものとしても扱わない。
合う版が無ければ、nvm の行では見つからなかった扱いにして次の行へ進む。

### 表の場所で見つけたとき

表の場所で見つけたら、その実行ファイルのあるディレクトリを `<dir>` とし、以降 PM と node を呼ぶコマンド（`yarn --version`、下の表のチェック、pnpm 11 での流し直しとその前の Node.js の版の確認）は `PATH="<dir>:$PATH" <pm> run build` のように `<dir>` を `PATH` の先頭に足して流す。nvm の行は指定に合う版を選ぶが、後ろの行（`PNPM_HOME` / `BUN_INSTALL`）で見つけたときは node の版を指定と照らさない。
corepack が置く pnpm / yarn と npm は `#!/usr/bin/env node` で始まり、フルパスで呼んでも `node` が `PATH` に無いと `env: node: No such file or directory` で exit 127 になる。`<dir>/node <dir>/npm run build` と node をフルパスで呼んでも、scripts の中の `node` が `sh: node: command not found` で落ちる（どちらも npm 11.12.1 / pnpm 12.6.0 で実測）。nvm の `<dir>` にはその版の `node` がある。
シンボリックリンクは辿らない。nvm の `bin/pnpm` などは `../lib/node_modules/` の下へのリンクで、辿った先のディレクトリに `node` は無い。
`node` があるかは確かめない。`<dir>` にも `PATH` にも `node` が無ければ（スタンドアロンの pnpm など）、node を呼ぶチェックは失敗し、ほかの失敗と同じく push を止める。
`<dir>` は展開した絶対パスで書き（引用符の中の `~` は展開されない）、コマンドごとに付ける。Bash の呼び出しの間で環境変数は引き継がれないことがある。
出力では、流した Node.js のチェック（`yarn --version` の失敗で ✗ にした audit も数える）のうち最初の行の括弧の最後に `pnpm が PATH に無いため ~/.nvm/versions/node/v24.15.0/bin を PATH の先頭に足して流した` のように書く（ホームディレクトリは `~` と書く）。括弧にほかの説明（`失敗。`、410 で流し直したことなど）があれば、その後に `。` で区切って続ける。nvm ならパスから node の版が読め、CI と結果が違ったときの手がかりになる。
nvm に候補があったのに合う版が無く、後ろの行かユーザーの答えの `<dir>` で流したときは、`流した` の後に `。nvm は engines.node の >=26 に合う版が無い。pnpm があるのは v24.15.0` のように続ける。`nvm は` の後は、下の `探した場所:` で nvm の場所に添える括弧の中身と同じである。

### 表の場所でも見つからないとき

表の場所でも見つからなければ `AskUserQuestion` でユーザーに PM の場所を確認する。nvm に候補があったのに合う版が無かったときは、下の `探した場所:` で nvm の場所に添える括弧と同じ内容を質問に添える。
答えが実行ファイルならその親を、ディレクトリならそれを `<dir>` にし、表の場所で見つけたときと同じに扱う。答えの `<dir>` の版は指定と照らさない。合わない版で流すかはユーザーが決める。`<dir>/<pm>` が実行できなければ（`test -x`）見つからなかった扱いにして、`<dir>/<pm>` が実行できなかったことを添え、中断を選択肢に入れてもう一度聞く。`bin/` の下などを自分で探しには行かない。
非対話モード時は Node.js のチェックを流さずに失敗とし、push を中止する。出力は、流すはずだった Node.js のチェックのうち最初のものを `✗ Node.js build（失敗。bun が見つからない。探した場所: PATH, ~/.nvm/versions/node/*/bin/bun, ~/.bun/bin/bun）` のように書き、残りの Node.js のチェックは前段失敗の行（`— <チェック名>（前段失敗のため未実行）`）にする。ほかの種別のチェックは、ほかの失敗と同じく SKILL.md の「失敗時の優先規則」に従う。
`探した場所:` には、`command -v` を `PATH` と書き、続けて表で見た場所を見た順に `, ` で区切って並べる。変数は展開した値で書き、ホームディレクトリは `~` と書き、glob は展開しない。
nvm に候補があったのに合う版が無かったときは、nvm の場所の後ろに `~/.nvm/versions/node/*/bin/pnpm（engines.node の >=26 に合う版が無い。pnpm があるのは v24.15.0）` のように括弧を付ける。指定は「nvm の版の選び方」の並びの順に `engines.node の >=18 と .nvmrc の 20` のように `と` でつなぎ（値の中の改行は空白 1 つにする）、候補の版は古い順に `, ` で区切って並べる。`<最新>` が無くて比べられなかったときは、括弧の前半を `semver を流せる版が無い` にする（`（semver を流せる版が無い。pnpm があるのは v14.21.3）`）。
`corepack <pm>@latest` で取ってくることはしない。Node.js 25 以降は corepack が同梱されず、`@latest` はプロジェクトが宣言した版を無視するため。
流す Node.js のチェックが 1 つも無ければ（スキップ行だけなら）PM は探さず、見つからなくても失敗にしない。

## PATH で見つけた PM の node の版

`command -v <pm>` で PM が見つかったら、`node --version` の版を「nvm の版の選び方」の 3 つの指定と照らす。PM によらず 3 つとも照らす。照らさないと、同じプロジェクトでもログインシェルでは PATH の版で、subagent では nvm の行で選んだ版で流れる。PM に任せても揃わない。npm 11.12.1 の `npm run build` は、`engines.node` に合わない版でも `engine-strict=true` のまま exit 0 で流れる。pnpm 12.6.0 の `pnpm run build` は、`engines.node` に合わなければ `engine-strict` が無くても `ERR_PNPM_UNSUPPORTED_ENGINE` で exit 1 になるが、`.nvmrc` と `.node-version` は見ない。
この節の切り替えは package-manager skill のルール 2 の `nvm use` の代わりで、`nvm install` で取ってくることはしない。push 前のチェックのために node を取ってきて `~/.nvm` を書き換えない。

次のどれかに当たれば照らさずに流す。上から見て最初に当たったものを採る。

- 指定が 1 つも無い
- `command -v node` が空か、`node --version` が 0 以外で終わった（「表の場所で見つけたとき」の「`node` があるかは確かめない」と同じく、node を呼ぶチェックの失敗に任せる）
- 「nvm の版の選び方」の `<最新>` が無い。切り替える先も無いので、nvm の無い環境で毎回止めない。注記は `~/.nvm/versions/node に semver を流せる版が無いため、PATH の node v24.15.0 を指定と照らさなかった` のように、探した `<nvm>/versions/node` と PATH の node の版を添える
- 下で外した結果、読める指定が残らない。注記は外した指定の注記だけ

semver の範囲として読めない指定（`lts/*`・`node`・`#` のコメントを含む値など）は外して照らす。合わない扱いにすると、`.nvmrc` が `lts/*` のプロジェクト（nvm 0.40.8 の README が載せる例）は PATH の node にも nvm のどの版にも合わず、毎回失敗する。nvm の行の扱い（どの版にも合わない）は変えない。
読めるかは、指定ごとに次のコマンドを 1 回流し、`null` を出すかで決める。`<指定>` は「nvm の版の選び方」と同じく前後の空白を除いた値である。semver.js の `-r` では決められない。読めない指定も合わない指定も、何も出さずに exit 1 で終わる。

```bash
'<nvm>/versions/node/<最新>/bin/node' -p 'require(process.argv[1]).validRange(process.argv[2])' '<nvm>/versions/node/<最新>/lib/node_modules/npm/node_modules/semver' '<指定>'
```

semver 7.7.4 では `lts/*`・`node`・`24 # pinned` が `null` を出し、読める指定は `>=24.0.0 <25.0.0-0` のような範囲を出す（どちらも exit 0）。0 以外で終わったら、残りの指定には流さず、照らさずに流す。注記は `semver の validRange が exit <N> で終わったため、PATH の node v24.15.0 を指定と照らさなかった` だけにする（それまでに外した指定の注記も書かない）。
外した指定の注記は `.nvmrc の lts/* は semver の範囲として読めないため照らさなかった` のように書く。指定の書き方は `探した場所:` の括弧と同じで、値の中の改行は空白 1 つにし、2 つ以上なら `と` でつないで 1 文にする（`.node-version の node と .nvmrc の lts/* は semver の範囲として読めないため照らさなかった`）。

残った指定を「nvm の版の選び方」と同じく `-r` に渡し、続けて PATH の版を 1 つだけ並べる。exit 0 ならそのまま流す。
0 以外なら、`<nvm>/versions/node/` の下で `bin/node` が実行できる版を同じ `-r` の後ろに並べ、最後の行に `v` を付けた版を選ぶ。nvm の行と違って `bin/<pm>` で絞らない。`<pm>` の無い版でも、PATH の `<pm>` がその版の node で動くからである（`node` だけを置いた版の `bin` を PATH の先頭に足すと、PATH にある pnpm 12.6.0 の corepack のシムはその `node` で起動した）。`corepack enable` はシムを corepack の隣に置くので、nvm では版ごとに `bin/pnpm` があったり無かったりする。選んだ版に `<pm>` があれば、PATH の `<pm>` ではなくそちらが動く（npm は nvm のどの版にもある）。
選んだ版の `bin` を `<dir>` にし、表の場所で見つけたときと同じく PATH の先頭に足して流す。注記は `PATH の node v24.15.0 が .nvmrc の 22 に合わないため ~/.nvm/versions/node/v22.12.0/bin を PATH の先頭に足して流した` のように書く。
注記の `PATH の node … が` の後ろには、PATH の版に合わなかった指定だけを書く。指定ごとに `-r '<指定>'` と PATH の版を 1 つ並べて流し、0 以外で終わったものである。照らした指定をすべて書くと、PATH の版が合っている指定にも合わないように読める。指定のつなぎ方は `探した場所:` の括弧と同じである。

合う版が無ければ、表の場所は見ない。表の後ろの行（`PNPM_HOME` / `BUN_INSTALL`）で PM を見つけても、node は PATH の合わない版のままだからである。
非対話モード時は「表の場所でも見つからないとき」と同じく、Node.js のチェックを流さずに失敗とし、残りの Node.js のチェックを前段失敗の行にする。失敗の行は、`<pm> が見つからない。探した場所: …` の代わりに `PATH の node v24.15.0 が .nvmrc の 22 に合わない。~/.nvm/versions/node/*/bin/node には engines.node の >=20 と .nvmrc の 22 に合う版が無い。node があるのは v20.19.0, v24.15.0` のように書く。`には` の後ろには、照らしたすべての指定を書く。node がある版は古い順に `, ` で区切って並べる。
対話時は、「表の場所でも見つからないとき」の質問ではなく、失敗の行と同じ内容を添えて、指定に合う node か `<pm>` のある場所を聞く。答えが実行ファイルならその親を、ディレクトリならそれを `<dir>` にし、`<dir>/node` か `<dir>/<pm>` のどちらかが実行できれば（`test -x`）PATH の先頭に足して流す。そこの `<dir>/<pm>` だけを確かめる手順は使わない。どちらも実行できなければ、それを添え、中断を選択肢に入れてもう一度聞く。答えの版を指定と照らさないことと、`bin/` の下を探しに行かないことは、そこと同じである。注記は `PATH の node v24.15.0 が engines.node の >=27 に合わず、nvm にも合う版が無いため、答えの /opt/homebrew/opt/node@27/bin を PATH の先頭に足して流した` のように書く。

この節の注記は、流した Node.js のチェックのうち最初の行の括弧に、「表の場所で見つけたとき」と同じく、ほかの説明の後に `。` で区切って続ける。パスのホームディレクトリは `~` と書く。外した指定の注記は、この節のほかの注記より前に書く。失敗の行は、`失敗。`、外した指定の注記、上の失敗の文の順になる（`✗ Node.js build（失敗。.nvmrc の lts/* は semver の範囲として読めないため照らさなかった。PATH の node v24.15.0 が engines.node の >=26 に合わない。…）`）。
この節の経路では、「表の場所で見つけたとき」の `<pm> が PATH に無いため …` と `nvm は …` の注記は書かない。PM は PATH にあり、nvm の行は見ていない。

## チェックの表

| チェック   | 条件                                  | コマンド                                           |
| ---------- | ------------------------------------- | -------------------------------------------------- |
| build      | `scripts.build` が定義されている      | `<pm> run build`                                   |
| lint       | `scripts.lint` が定義されている       | `<pm> run lint`                                    |
| typecheck  | `scripts.typecheck` が定義されている  | `<pm> run typecheck`                               |
| type-check | `scripts.type-check` が定義されている | `<pm> run type-check`                              |
| test       | `scripts.test` が定義されている       | `<pm> run test`                                    |
| audit      | 常に実行                              | `<pm> audit` (`pnpm` の場合は `pnpm audit --prod`) |

`scripts.typecheck` と `scripts.type-check` が両方定義されていれば両方流す。中身が違いうるので、片方だけでは取りこぼす。

### pnpm の verifyDepsBeforeRun

PM が pnpm なら、`pnpm run` のチェックは `verifyDepsBeforeRun` の指定のまま流す。環境変数の前置（`PNPM_CONFIG_VERIFY_DEPS_BEFORE_RUN=false`）や CLI の `--config.verify-deps-before-run=false` で切らない（package-manager skill のルール 1）。
pnpm 11 以降はこの設定の既定が `install` で、`pnpm run` が `node_modules` を確かめ、ずれていれば install を流す。依存もロックファイルも無ければ `pnpm-lock.yaml` と `node_modules` を作り、package.json がロックファイルより新しければ `pnpm-lock.yaml` を書き換え、store に無い依存は registry へ取りに行く（11.9.0 / 12.6.0 で実測。10.33.0 は既定が `false` で何もしない）。dotfiles の pnpm ロールがグローバル設定（`config.yaml` / `rc`）で `error` にしているので、ずれていれば `ERR_PNPM_VERIFY_DEPS_BEFORE_RUN` で exit 1 になり、何も書き換えない。プロジェクトが pnpm-workspace.yaml で `install` などを指定していればそれに従い、書き換わったファイルはほかのチェックが作ったファイルと同じく扱う。`pnpm audit` は install を流さない。
`error` と、11.9.0 / 12.6.0 で端末が無いときの `prompt` は、`node_modules` が無いかずれていると `ERR_PNPM_VERIFY_DEPS_BEFORE_RUN` で exit 1 になる（12.6.0 は依存を宣言していないプロジェクトでも `node_modules` が無ければ止まる）。これもほかの失敗と同じく失敗である。10.33.0 の `prompt` は答えを読めず、スクリプトを流さないまま exit 0 で終わる。出力に `Would you like to run "pnpm install"` が出たら、exit 0 でも `✗ Node.js build（失敗。verifyDepsBeforeRun の prompt に答えられず、スクリプトが流れなかった）` のように失敗とする。
チェックが失敗し、出力に `ERR_PNPM_VERIFY_DEPS_BEFORE_RUN` があるか、依存を宣言していて（下の「ロックファイルも依存も無いときの audit」に並べた package.json と pnpm-workspace.yaml の欄のどれかが空でない）プロジェクトルートに `node_modules` が無ければ、失敗の行の括弧の `失敗。` の直後（ほかの注記より前）に `node_modules が無いかずれている。pnpm install を流してから push し直す` を続ける（`✗ Node.js build（失敗。node_modules が無いかずれている。pnpm install を流してから push し直す）`）。`false` の指定では依存のコマンドが `sh: tsc: command not found`（exit 127）で落ち、12.6.0 は 10.33.0 と違って `node_modules` が無いことを知らせない。

### npm init の既定の test

`scripts.test` の値が `npm init` / `pnpm init` の既定の `echo "Error: no test specified" && exit 1` と完全に一致するときは、定義されていないものとして扱う。package.json 上は `"test": "echo \"Error: no test specified\" && exit 1"` と書かれている。test 行の条件を満たさないので流さず、検出されなかったチェックと同じく push の可否の判定にも入れない。結果の出力には `— Node.js test（scripts.test が npm init の既定のままのためスキップ）` と書き、前段の失敗で打ち切ったときもこの書き方を変えない。
空白やコマンドを足したもの（末尾に `&& jest` を足したもの等）は定義されているものとして流し、0 でない終了コードは失敗である。判定は PM によらない（`npm init` で作ってから別の PM に移したプロジェクトにも残る）。

### ロックファイルも依存も無いときの audit

ロックファイル（SKILL.md の「チェックが作った未追跡のファイル」に並べたもの）がどれも無く、`package.json` の `dependencies` / `devDependencies` / `optionalDependencies` / `peerDependencies` / `workspaces` と `pnpm-workspace.yaml` の `packages` もどれも無いか空のときは、audit を流さない。ロックファイルが無いと、`npm audit` は `ENOLOCK`、`pnpm audit` は `ERR_PNPM_AUDIT_NO_LOCKFILE` で exit 1 になる。依存が無ければ、ロックファイルを作って流しても脆弱性 0 件（exit 0）で終わる。検出されなかったチェックと同じく push の可否の判定には入れず、結果の出力には `— Node.js audit（ロックファイルも依存も無いためスキップ）` と書く。前段の失敗で打ち切ったときもこの書き方を変えない。
ロックファイルが無くても上のどれかが空でなければ流し、ロックファイルが無いことによる失敗も失敗である。ロックファイルを作るコマンド（`npm audit` のエラーが案内する `npm i --package-lock-only`、`pnpm install --lockfile-only` 等）はスキルから流さない（未コミットのファイルが増える）。pnpm 11 以降の `pnpm run` が既定で流す install は、上の「pnpm の verifyDepsBeforeRun」のとおりグローバル設定の `error` で止まる。
