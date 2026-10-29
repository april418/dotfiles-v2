# dotfiles-v2

## Installation

```sh
bash -c "$(curl -L g.oftn.lv/dtfls)"
```

## Claude Code のキャラクター

応答のキャラクターは `ansible/roles/claude/files/characters/` から 1 つ選び、
`~/.claude/rules/character.md` に置く。既定は `zundamon`、`none` でキャラクターを使わない。

```sh
~/.local/bin/ansible-playbook ~/.dotfiles/ansible/playbook.yml --connection=local -e claude_character=none
```

選んだキャラクターは配置したファイルの 1 行目に記録され、次に `install` を流しても変わらない。
新しいセッションから効く。選んでいたキャラクターのファイルを改名・削除すると `install` が
lookup の失敗で止まるので、`-e` で選び直す。

キャラクターを足すときは次に従う。

- ファイル名は英小文字・数字・`-` だけにする。それ以外は次の `install` で読めずに既定へ戻るため、
  プレイブックが止める
- `characters/zundamon.md` と同じく「プロフィール」「文末と言い回し」「場面ごとの反応」の節を書く。
  振る舞いの規則は `files/AGENTS.md` の「場面ごとの振る舞い」にあり、キャラクターのファイルは声だけを持つ
- 「場面ごとの反応」の場面の名前は `AGENTS.md` の表と揃える。反応の言葉が要らない場面は「入れない」と書く
- frontmatter は書かない。配置時に 1 行目へ印が入るので、frontmatter として読まれない
