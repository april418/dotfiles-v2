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
- **このファイルを消さない。** リポジトリに CLAUDE.md が 1 つも無いと、
  Claude Code は `files/AGENTS.md` をこのリポジトリの指示として読み込む
  （compact 後のフックも同様）
