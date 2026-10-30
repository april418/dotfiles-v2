# dotfiles-v2

`install` が Ansible を入れ、`ansible/playbook.yml` で各ツールの設定を
ホームディレクトリへ配置する。ツールごとに `ansible/roles/<tool>/` を持つ。

## `ansible/roles/claude/files/` は配布物である

このディレクトリの中身は `~/.claude/`（`files/bin/` は `~/.local/bin/`）へ
コピーされ、すべてのプロジェクトで効く。このリポジトリ向けの指示ではない。

| リポジトリ                                                       | 配置先                                      |
| ---------------------------------------------------------------- | ------------------------------------------- |
| `files/AGENTS.md`                                                | `~/.claude/CLAUDE.md`（ユーザー全体の指示） |
| `files/hooks/` `files/skills/` `files/agents/` `files/rules/`    | `~/.claude/` の同名ディレクトリ             |
| `files/characters/<名前>.md`（`claude_character` で選んだ 1 つ） | `~/.claude/rules/character.md`              |
| `files/settings.json`                                            | `~/.claude/settings.json`                   |
| `files/bin/evacuate`                                             | `~/.local/bin/evacuate`                     |

- 編集はプレイブックを流すまで `~/.claude/`（と `~/.local/bin/`）に反映されない。動作確認は
  `HOME` を一時ディレクトリに向けて claude ロールだけを流すと、実環境を
  汚さずに配置結果を見られる
- `files/settings.json` は上書きではなく、配置先の既存の内容へ重ねる。
  ここにあるキーは配列も含めてリポジトリ側の値になるため、`/model` や
  `/permissions` で配置先を変えても、そのキーなら流すたびに戻る。キーを
  消しても配置先には残るので、`~/.claude/settings.json` からも手で消す
- `files/rules/` の .md は配置先で毎セッション読まれる。リポジトリで消したり改名したり
  しても配置先には残って効き続けるので、`~/.claude/rules/` からも `evacuate` で取り除く。
  `character.md` はキャラクターのタスクが書くので、`files/rules/` に同じ名前を置かない
- **このファイルを消さない。** リポジトリに CLAUDE.md が 1 つも無いと、
  Claude Code は `files/AGENTS.md` をこのリポジトリの指示として読み込む

## 配布する指示を書き換えるとき

`files/AGENTS.md`・`files/rules/`・`files/skills/`・`files/agents/`・`files/characters/`
は、Claude Opus 5.5 / Fable 5.1 に向けて次のように書く。

- `files/AGENTS.md` は 200 行前後に収める。長いと遵守が落ちる
  （[memory](https://code.claude.com/docs/en/memory)）。毎回の作業で効く判断だけを置き、
  手順は skill かスクリプトへ出す
- 強調（`【最重要】`、太字の重ね、「必ず」「一切」）で守らせない。今のモデルは素直に
  書いた 1 行に従い、強調を重ねると規則を過剰に当てはめる
  （[best-practices](https://code.claude.com/docs/en/best-practices)）。曲げてはいけない
  規則は deny 規則かフックにする
- 規則には理由を 1 行添え、現在形で書く。日付付きの事故談は書かず、経緯は git log に
  残す。同じ規則を別の言い方で重ねず、正本を 1 か所に決めてほかからは節の名前で指す
- 肩書き（「熟練した〜である」）を中身の代わりにしない。専門家の役割を与えても
  正答率は上がらない（[arXiv 2311.10054](https://arxiv.org/abs/2311.10054)、
  [arXiv 2512.05858](https://arxiv.org/abs/2512.05858)）。焦点を絞る 1 文の役割は書いてよいが
  （[prompting best practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices)）、
  何を受け取り、何を返すかは別に書く
- 汎用の「検証しろ」「subagent で検証しろ」を書かない。Opus 5 系では過剰な検証と委譲を
  招く（[prompting-claude-opus-5](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5)）。
  何をどの場面で確かめるかまで書く
- キャラクターは形容詞ではなく、`files/AGENTS.md` の「場面ごとの振る舞い」と同じ場面名
  での反応で書く。ペルソナを状況と振る舞いで組むとロールプレイの再現度が上がり
  （[arXiv 2609.21349](https://arxiv.org/abs/2609.21349)）、振る舞いを名指しした指示は
  ペルソナを入れ直すより逸脱を抑える（[arXiv 2609.24532](https://arxiv.org/abs/2609.24532)）
- ほかのファイル（キャラクター、skill、フックのコメント）が節の名前で参照しているので、
  見出しを変えたら `grep -rn "<旧い見出し>" ansible/roles/claude/files` で参照を直す

書き換えたら、前後で `/doctor prompt-audit` を流して指摘を比べるよう、ユーザーに
提案する。白紙のエージェントで実測する empirical-prompt-tuning は API を使うので、
流すかはユーザーに聞く。
