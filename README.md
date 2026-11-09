# dotfiles-v2

## Installation

```sh
bash -c "$(curl -L g.oftn.lv/dtfls)"
```

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

## AWS CLI

`awscli` ロールは AWS CLI v2 を固定バージョンでインストールする。公式の `install.sh` に版を渡し、
`~/.local/share/aws-cli`（`XDG_DATA_HOME` があればその下）へ入れて、`~/.local/bin/aws` から起動する。
Linux では、`install.sh` が使う `unzip` と `gpg` を先に sudo でパッケージから入れる。

`~/.local/bin` は PATH の末尾にあるので、Homebrew や OS のパッケージで入れた別の `aws`
（`/opt/homebrew/bin`、`/usr/local/bin`、`/usr/bin`、`/snap/bin` など）があると、そちらが使われる。
固定した版を使うときは、別の `aws` を取り除く。

`aws update` などで固定より新しい版が入っていれば、そのまま使う。固定より古い版へ戻すときは、
`~/.local/share/aws-cli` と `~/.local/bin/aws`、`~/.local/bin/aws_completer` を取り除いてからプレイブックを流す。
