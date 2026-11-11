# dotfiles-v2

## Installation

```sh
bash -c "$(curl -L g.oftn.lv/dtfls)"
```

## Codex / ChatGPT のグローバル指示

`codex` ロールは `~/.codex/AGENTS.md` にグローバル指示を配置する。
`CODEX_HOME` が設定されていれば、そのディレクトリに配置する。
次の原本を連結し、Codex 向けの環境差の説明を添えて生成する。

- `ansible/roles/claude/files/AGENTS.md`
- `ansible/roles/claude/files/rules/*.md`（ファイル名順）
- `ansible/roles/claude/files/characters/<選択した名前>.md`

原本は分割したまま管理できる。生成したファイルには規則の本文が入るため、
Codex が参照先を開くかどうかに依存しない。rules の削除やキャラクターの変更も再生成時に反映する。
既存の配置先を更新するときは Ansible がバックアップを残す。

Codex CLI と Codex / ChatGPT デスクトップの、新しいチャットから適用される。
グローバル指示を読むための追加プラグインは不要。
Claude 専用のフックや権限設定は Codex には適用されない。
skill など、収録していない Claude 側のファイルは、存在して利用できる場合だけ参照する。

`dotfiles character set <名前>` は Claude Code のキャラクターを配置した後、
Codex のグローバル指示も再生成する。`none` を選ぶと両方でキャラクターを使わない。
この処理では Codex CLI や Node.js をインストールしない。

同じロールで Codex CLI（`@openai/codex`）も固定バージョンでインストールする。
配置先は `~/.local/share/codex`（`XDG_DATA_HOME` があればその下）で、
`~/.local/bin/codex` から起動する。ChatGPT アプリ同梱版とは別に管理する。
Node.js が無い、または古い場合はインストールをスキップして知らせるので、
nvm で対応する Node.js を入れてから流し直す。

同じロールで、Claude Code のプラグインと同じ yomiyasu の skill を Codex にも置く（[Claude Code のプラグイン](#claude-code-のプラグイン)）。
`claude_yomiyasu_version` のタグを `~/.local/share/yomiyasu`（`XDG_DATA_HOME` があればその下）に浅く clone し、
Codex がユーザー全体の skill を探す `~/.agents/skills/yomiyasu` を、その中の `skills/yomiyasu` へのリンクにする。
置き場は `CODEX_HOME` を設定していても変わらない。ChatGPT アプリ同梱の codex も同じ場所を読むので、
Codex CLI を入れられなかったときも置く。skill の名前は Codex でも `yomiyasu:yomiyasu` になる
（skill のフォルダにある `.codex-plugin/plugin.json` による）。Codex は skill の変化を自分で拾い、
一覧に出てこなければ Codex を起動し直す。一覧に載ったかは、モデルを呼ばずに数えられる。
1 なら載っていて、0 なら載っていない。グローバル指示にも `yomiyasu:yomiyasu` の文字があるので、一覧の行の形で数える。

```sh
codex debug prompt-input | grep -c -F -e '- yomiyasu:yomiyasu: '
```

`~/.agents/skills/yomiyasu` にリンクではないフォルダ（`npx skills add -g` で入れたものなど）があれば、
置き換えずに知らせる。`evacuate` で退避してから流し直す。別の場所へのリンクと壊れたリンクは、流すたびに張り替える。

ブラウザ版 ChatGPT はローカルファイルを自動では読み込まない。
全チャットに適用する指示は Settings → Personalization の Custom instructions に設定する。
ローカルの `AGENTS.md` とは自動同期されない。

仕様: [AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md)、
[デスクトップの Personalization](https://learn.chatgpt.com/docs/app/settings)、
[ChatGPT のカスタム指示](https://learn.chatgpt.com/docs/personalize)、
[skill の置き場](https://learn.chatgpt.com/docs/build-skills)。

## Claude Code のキャラクター

応答のキャラクターは `ansible/roles/claude/files/characters/` から 1 つ選び、
`~/.claude/rules/character.md` に置く。既定は `zundamon`、`none` でキャラクターを使わない。

まだ選んでいなければ、プレイブック（`install` を含む）がロールを流す前に名前を聞く。Enter で既定になる。
選んだキャラクターは `~/.local/state/dotfiles/claude-character.json`（`XDG_STATE_HOME` があればその下）に
記録され、次からは聞かずにそれを使う。選んでいたキャラクターのファイルを改名・削除すると、もう一度聞く。
新しいセッションから効く。

端末が無いときは聞かずに既定を選び、選んだものとして記録する。次に端末から流しても聞かない。
改名・削除で聞き直す場面でも、端末が無ければ既定に置き換え、そのことを表示する。

今のキャラクターと選べるものは `dotfiles character` で見る。選び直すときは `dotfiles character set` に名前を渡す。
名前を省くと一覧から聞く（Enter で今のまま）。

```sh
dotfiles character set pico
```

プレイブックに `-e claude_character=<名前>` を渡しても選べる。

キャラクターを足すときは次に従う。

- ファイル名は英小文字・数字・`-` だけにする。それ以外の名前は記録に残しても読めないため、
  選択肢に出さず、名前を渡してもプレイブックが止める
- `characters/zundamon.md` と同じく「プロフィール」「文末と言い回し」「場面ごとの反応」の節を書く。
  振る舞いの規則は `files/AGENTS.md` の「場面ごとの振る舞い」にあり、キャラクターのファイルは声だけを持つ
- 「場面ごとの反応」の場面の名前は `AGENTS.md` の表と揃える。反応の言葉が要らない場面は「入れない」と書く

## Claude Code のプラグイン

`claude` ロールは、プラグインとそのマーケットプレイスを `~/.claude/settings.json` の `enabledPlugins` と
`extraKnownMarketplaces` に宣言する。宣言は `ansible/roles/claude/vars/main.yml` の `claude_plugin_settings` にあり、
`files/settings.json` の後に重ねる。

| プラグイン                                                                     | 中身                                                                                                                                                                                 | 版                                      |
| ------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------- |
| `yomiyasu@yomiyasu`（[nanaism/yomiyasu](https://github.com/nanaism/yomiyasu)） | AI が書いた日本語を推敲する skill。名前を出したとき（`/yomiyasu:yomiyasu`、「yomiyasu で推敲して」）、スキルでの推敲をはっきり頼んだとき、CLAUDE.md などで使うよう指示したときに動く | `claude_yomiyasu_version`（タグで固定） |

どの文章を `yomiyasu:yomiyasu` で推敲するかは、共有のグローバル指示（`files/AGENTS.md`）の「手順を持つ skill」の節が決める。
この節は Codex のグローバル指示にも入り、Codex には `codex` ロールが同じ版の skill を置く
（[Codex / ChatGPT のグローバル指示](#codex--chatgpt-のグローバル指示)）。

プレイブックはプラグインを取得しない。宣言を読んだ Claude Code が、セッションの開始後にマーケットプレイスを
クローンしてプラグインを取得する。宣言だけの状態では、マーケットプレイスがまだ取得されていないので、
`claude plugin install` も `claude plugin marketplace update` も not found で失敗する。セッションを待たずに入れるときは、
宣言と同じ版を指定して流す。

```sh
claude plugin marketplace add 'nanaism/yomiyasu#<claude_yomiyasu_version の値>'
claude plugin install yomiyasu@yomiyasu
```

yomiyasu の lint と check は Python 3 の標準ライブラリで動き、skill の `allowed-tools` により確認なしで実行される。
ファイルを渡したときに読むのは作業フォルダの中のものだけで、作業フォルダの外のものと、作業フォルダからのパスに
点で始まる部分（`.claude/` など）を含むものは、読まずに終了コード 2 で止まる。標準入力からは読める。
check は原稿の写しと記録を git の最上位の `.yomiyasu/`（環境変数 `YOMIYASU_STATE_DIR` で変えられる）に書き、
既定の場所では `.gitignore` も置くので git の管理には入らない。Python が無いと、検査を飛ばして目視で点検する。

新しい版の公開から 1 週間たつと `dotfiles check` が知らせる。`claude_yomiyasu_version` を書き換えてプレイブックを流すと、
取得済みのマーケットプレイスの source が宣言と食い違い、プラグインは読み込まれなくなる（`claude plugin list` が
`failed to load` と `added but ignored` を出す）。前に別の版や `ref` なしで足していたマシンに初めて配ったときも同じになる。
宣言の版でマーケットプレイスを足し直してから、プラグインをその版に合わせる。足し直すだけでは版は変わらず、
足し直す前の `claude plugin update` は not found で失敗する。合ったかは `claude plugin list` の Version で確かめる。

```sh
claude plugin marketplace add 'nanaism/yomiyasu#<claude_yomiyasu_version の値>'
claude plugin update yomiyasu@yomiyasu
```

Codex の側は手で揃えなくてよい。プレイブックが clone を新しいタグへ checkout し直し、リンクはそのまま新しい版を指す。

`/plugin` で無効にしても、`enabledPlugins` はリポジトリ側の値なので、プレイブックを流すたびに有効に戻る。
外すときは `claude_plugin_settings` から yomiyasu の 2 項目を消し、`claude plugin marketplace remove yomiyasu` を流す。
取得済みなら、プラグインのアンインストールと、配置先の `~/.claude/settings.json` の 2 つのキーの削除まで行われる。
一度も取得していなければ remove は not found で失敗するので、配置先から `extraKnownMarketplaces.yomiyasu` と
`enabledPlugins` の `yomiyasu@yomiyasu` を手で消す。宣言が残ると、次のセッションでまた取得される。
Codex の側も外すときは、`ansible/roles/codex/tasks/main.yml` から `skills.yml` の取り込みを、
`ansible/roles/codex/vars/main.yml` から `codex_yomiyasu_version`・`codex_yomiyasu_dir`・`codex_skills_dir` を消す。
配置先の `~/.agents/skills/yomiyasu`（リンク）と `~/.local/share/yomiyasu`（`XDG_DATA_HOME` があればその下）は
`evacuate` で退避する。取り込みを残したまま `claude_yomiyasu_version` を消すと、codex ロールが版を読めずに止まる。
両方から外すときは、`files/AGENTS.md` の「手順を持つ skill」にある yomiyasu の行も消す。残すと、無い skill で推敲するよう指示し続ける。

## AWS CLI

`awscli` ロールは AWS CLI v2 を固定バージョンでインストールする。公式の `install.sh` に版を渡し、
`~/.local/share/aws-cli`（`XDG_DATA_HOME` があればその下）へ入れて、`~/.local/bin/aws` から起動する。
Linux では、`install.sh` が使う `unzip` と `gpg` を先に sudo でパッケージから入れる。

`~/.local/bin` は PATH の末尾にあるので、Homebrew や OS のパッケージで入れた別の `aws`
（`/opt/homebrew/bin`、`/usr/local/bin`、`/usr/bin`、`/snap/bin` など）があると、そちらが使われる。
固定した版を使うときは、別の `aws` を取り除く。

`aws update` などで固定より新しい版が入っていれば、そのまま使う。固定より古い版へ戻すときは、
`~/.local/share/aws-cli` と `~/.local/bin/aws`、`~/.local/bin/aws_completer` を取り除いてからプレイブックを流す。
