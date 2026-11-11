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

ブラウザ版 ChatGPT はローカルファイルを自動では読み込まない。
全チャットに適用する指示は Settings → Personalization の Custom instructions に設定する。
ローカルの `AGENTS.md` とは自動同期されない。

仕様: [AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md)、
[デスクトップの Personalization](https://learn.chatgpt.com/docs/app/settings)、
[ChatGPT のカスタム指示](https://learn.chatgpt.com/docs/personalize)。

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

| プラグイン                                                                     | 中身                                                                                                         | 版                                      |
| ------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------ | --------------------------------------- |
| `yomiyasu@yomiyasu`（[nanaism/yomiyasu](https://github.com/nanaism/yomiyasu)） | AI が書いた日本語を推敲する skill。名前で頼んだときだけ動く（`/yomiyasu:yomiyasu`、「yomiyasu で推敲して」） | `claude_yomiyasu_version`（タグで固定） |

プレイブックはプラグインを取得しない。宣言を読んだ Claude Code が、セッションの開始後にマーケットプレイスを
クローンしてプラグインを取得する。宣言だけの状態では、`claude plugin install` も `claude plugin marketplace update` も
マーケットプレイスが見つからずに失敗する。セッションを待たずに入れるときは、宣言と同じ版を指定して流す。

```sh
claude plugin marketplace add 'nanaism/yomiyasu#<claude_yomiyasu_version の値>'
claude plugin install yomiyasu@yomiyasu
```

yomiyasu の lint と check は Python 3 の標準ライブラリで動き、skill の `allowed-tools` により確認なしで実行される。
Python が無いと、検査を飛ばして目視で点検する。

新しい版の公開から 1 週間たつと `dotfiles check` が知らせる。`claude_yomiyasu_version` を書き換えてプレイブックを流したら、
`claude plugin list` の Version で上がったかを確かめ、上がっていなければ `claude plugin update yomiyasu@yomiyasu` を流す。

`/plugin` で無効にしても、`enabledPlugins` はリポジトリ側の値なので、プレイブックを流すたびに有効に戻る。
外すときは `claude_plugin_settings` から消し、`claude plugin marketplace remove yomiyasu` を流す（プラグインも
アンインストールされる）。配置先の `~/.claude/settings.json` に `extraKnownMarketplaces.yomiyasu` が残っていれば
手で消す。残ると、次のセッションでまた取得される。

## AWS CLI

`awscli` ロールは AWS CLI v2 を固定バージョンでインストールする。公式の `install.sh` に版を渡し、
`~/.local/share/aws-cli`（`XDG_DATA_HOME` があればその下）へ入れて、`~/.local/bin/aws` から起動する。
Linux では、`install.sh` が使う `unzip` と `gpg` を先に sudo でパッケージから入れる。

`~/.local/bin` は PATH の末尾にあるので、Homebrew や OS のパッケージで入れた別の `aws`
（`/opt/homebrew/bin`、`/usr/local/bin`、`/usr/bin`、`/snap/bin` など）があると、そちらが使われる。
固定した版を使うときは、別の `aws` を取り除く。

`aws update` などで固定より新しい版が入っていれば、そのまま使う。固定より古い版へ戻すときは、
`~/.local/share/aws-cli` と `~/.local/bin/aws`、`~/.local/bin/aws_completer` を取り除いてからプレイブックを流す。
