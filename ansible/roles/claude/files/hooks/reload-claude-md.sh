#!/usr/bin/env bash
# ==================================================
# compact 後に CLAUDE.md をコンテキストへ戻す
# ==================================================
# 会話が長くなると context が要約され、CLAUDE.md に書いた規則が薄まる。
# 要約は「何を話したか」を残すもので、「どう振る舞うか」の指示は落ちる。
#
# **PostCompact ではこれを実現できない。** あのイベントはログや通知などの
# 副作用専用で、hookSpecificOutput.additionalContext を受け付けない。
# SessionStart は受け付け、matcher に compact を指定すると compact 直後にだけ
# 発火する。そのため実装は SessionStart 側に置く。
#   https://code.claude.com/docs/en/hooks.md
#
# 対象は 2 つ。
#   - ユーザー全体の指示: ~/.claude/CLAUDE.md
#   - プロジェクトの指示: <cwd から遡って見つかる>/.claude/CLAUDE.md
#
# プロジェクト側は cwd がリポジトリ内のどこにあっても効くよう、親へ遡って探す。
set -uo pipefail

INPUT="$(cat)"

# JSON の取り出しに jq を使わない。環境によっては入っておらず、その場合
# 抽出が空になって**フックが黙って素通りする**。防御が無効になったことに
# 気づけないため、依存を持たない実装にする (guard-branch-base.sh と同じ理由)。
extract() {
  printf '%s' "$INPUT" | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(0)
cur = d
for k in sys.argv[1].split('.'):
    if not isinstance(cur, dict):
        sys.exit(0)
    cur = cur.get(k)
    if cur is None:
        sys.exit(0)
print(cur, end='')
" "$1" 2>/dev/null
}

CWD="$(extract cwd)"
[ -n "$CWD" ] || CWD="$PWD"

USER_MD="$HOME/.claude/CLAUDE.md"

# cwd から親へ遡って .claude/CLAUDE.md を探す。見つからなければ空のまま。
PROJECT_MD=""
dir="$CWD"
while [ -n "$dir" ] && [ "$dir" != "/" ]; do
  if [ -f "$dir/.claude/CLAUDE.md" ]; then
    PROJECT_MD="$dir/.claude/CLAUDE.md"
    break
  fi
  dir="$(dirname "$dir")"
done

# どちらも無ければ何も出さない。空の additionalContext を返すと、
# 「規則が無い」と読める文字列がコンテキストに入ってしまう。
[ -n "$PROJECT_MD" ] || [ -f "$USER_MD" ] || exit 0

# additionalContext は JSON 文字列なのでエスケープが要る。ファイルの中身に
# 引用符や改行が入るため、シェルでの組み立ては壊れる。python に任せる。
USER_MD="$USER_MD" PROJECT_MD="$PROJECT_MD" python3 <<'PY'
import json, os, pathlib

def read(path):
    if not path:
        return None
    p = pathlib.Path(path)
    if not p.is_file():
        return None
    try:
        return p.read_text(encoding="utf-8")
    except Exception:
        return None

parts = [
    "会話の要約が行われた。要約には「何を話したか」しか残らないため、"
    "従うべき指示を以下に再掲する。以降はこの内容に従うこと。"
]

for label, path in (
    ("ユーザーの全体指示", os.environ.get("USER_MD")),
    ("このプロジェクトの指示", os.environ.get("PROJECT_MD")),
):
    body = read(path)
    if body is None:
        continue
    parts.append(f"\n# {label} ({path})\n\n{body}")

# 見出しだけで本文が 1 つも無いなら黙って終わる。
if len(parts) == 1:
    raise SystemExit(0)

print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": "\n".join(parts),
    }
}))
PY
