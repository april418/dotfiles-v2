# dotfiles-v2

`install` が Ansible を入れ、`ansible/playbook.yml` で各ツールの設定を
ホームディレクトリへ配置する。ツールごとに `ansible/roles/<tool>/` を持つ。

## `ansible/roles/claude/files/` は配布物である

このディレクトリの中身は `~/.claude/` へコピーされ、すべてのプロジェクトで
効く。このリポジトリ向けの指示ではない。

| リポジトリ | 配置先 |
| --- | --- |
| `files/AGENTS.md` | `~/.claude/CLAUDE.md`（ユーザー全体の指示） |
| `files/hooks/` `files/skills/` `files/agents/` | `~/.claude/` の同名ディレクトリ |
| `files/settings.json` | `~/.claude/settings.json` |

- 編集はプレイブックを流すまで `~/.claude/` に反映されない。動作確認は
  `HOME` を一時ディレクトリに向けて claude ロールだけを流すと、実環境を
  汚さずに配置結果を見られる
- `files/settings.json` は上書きではなく、配置先の既存の内容へ重ねる。
  ここにあるキーは配列も含めてリポジトリ側の値になるため、`/model` や
  `/permissions` で配置先を変えても、そのキーなら流すたびに戻る。キーを
  消しても配置先には残るので、`~/.claude/settings.json` からも手で消す
- **このファイルを消さない。** リポジトリに CLAUDE.md が 1 つも無いと、
  Claude Code は `files/AGENTS.md` をこのリポジトリの指示として読み込む
