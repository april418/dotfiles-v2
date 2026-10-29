# dotfiles-v2

## Installation

```sh
bash -c "$(curl -L g.oftn.lv/dtfls)"
```

## Claude Code のキャラクター

応答のキャラクターは `ansible/roles/claude/files/characters/` から 1 つ選び、
`~/.claude/rules/character.md` に置く。既定は `zundamon`、`none` でキャラクターを使わない。

まだ選んでいなければ、プレイブック（`install` を含む）がロールを流す前に名前を聞く。Enter で既定になる。
選んだキャラクターは配置したファイルの 1 行目に記録され、次からは聞かずにそれを使う。
選んでいたキャラクターのファイルを改名・削除すると、もう一度聞く。新しいセッションから効く。

端末が無いときは聞かずに既定を選び、選んだものとして記録する。次に端末から流しても聞かない。
改名・削除で聞き直す場面でも、端末が無ければ既定に置き換え、そのことを表示する。

選び直すときは `-e` で渡す。

```sh
~/.local/bin/ansible-playbook ~/.dotfiles/ansible/playbook.yml --connection=local -e claude_character=none
```

キャラクターを足すときは次に従う。

- ファイル名は英小文字・数字・`-` だけにする。それ以外の名前は 1 行目の印に残しても読めないため、
  選択肢に出さず、`-e` で渡してもプレイブックが止める
- `characters/zundamon.md` と同じく「プロフィール」「文末と言い回し」「場面ごとの反応」の節を書く。
  振る舞いの規則は `files/AGENTS.md` の「場面ごとの振る舞い」にあり、キャラクターのファイルは声だけを持つ
- 「場面ごとの反応」の場面の名前は `AGENTS.md` の表と揃える。反応の言葉が要らない場面は「入れない」と書く
- frontmatter は書かない。配置時に 1 行目へ印が入るので、frontmatter として読まれない
