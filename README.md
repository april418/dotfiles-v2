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
