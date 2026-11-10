#!/usr/bin/env python3
"""主系列の直近の応答本文が英語なら、日本語に戻す一文を PostToolUse の additionalContext で差し込む。

グローバル指示（files/AGENTS.md の「言語」）は会話の先頭に 1 回入るだけなので、文脈が長くなると英語で返る
ツールの結果のほうが近くなり、応答本文が英語にずれる。一度ずれると自分の英語の文に引かれて続くので、
ずれた text 1 つにつき 1 回だけ、文脈のいちばん新しい位置に差し込む。日本語のあいだは何も出さない。
"""

import hashlib
import json
import os
import re
import sys
import tempfile

# ツールを呼ぶたびに走るので、会話記録は末尾だけを読む。直前の text がこれより前にあれば、取り逃して何もしない。
TAIL_BYTES = 2 * 1024 * 1024
# 同じ text に 2 回差し込まないための印を置く。中身は空のファイルなので、掃除は OS の一時ディレクトリに任せる。
STATE_DIR = os.path.join(tempfile.gettempdir(), "claude-reply-language-guard")

KANA = re.compile(r"[぀-ヿ]")
WORD = re.compile(r"[A-Za-z]{2,}")
# コード・コマンド・パスは原文のまま書く決まりなので、英語かどうかの判定から外す。
NOT_PROSE = [
    re.compile(r"```.*?```", re.S),
    re.compile(r"`[^`\n]*`"),
    re.compile(r"\[[^\]]*\]\([^)]*\)"),
    re.compile(r"https?://\S+"),
    re.compile(r"\S*/\S*"),
]
MESSAGE = (
    "直前の応答本文が英語になっている。グローバル指示の「言語」に従い、合間の一文も最終応答も日本語で書く。"
    "ツールの結果が英語でも、それに続けて英語で書かない。"
)


def is_english(text):
    for pattern in NOT_PROSE:
        text = pattern.sub(" ", text)
    if KANA.search(text):
        return False
    # 「OK」「LGTM」のような短い返事は言語を決められないので数えない。
    return len(WORD.findall(text)) >= 3


def latest_text(path):
    """主系列で最後の assistant の text を (行の uuid, 本文) で返す。記録が無いか、読んだ範囲に無ければ None。"""
    try:
        f = open(path, "rb")
    except FileNotFoundError:
        # 記録を残さない実行（claude -p の --no-session-persistence など）では、見るものが無い。
        return None
    with f:
        f.seek(0, os.SEEK_END)
        size = f.tell()
        f.seek(max(0, size - TAIL_BYTES))
        data = f.read()
    lines = data.split(b"\n")
    if size > TAIL_BYTES:
        # 途中から読んだので、最初の行は欠けている。
        lines = lines[1:]
    for raw in reversed(lines):
        # 行の大半はツールの結果なので、JSON として読む前に文字列で絞る。会話記録は空白なしの JSON で書かれる。
        if b'"type":"assistant"' not in raw or b'"text"' not in raw:
            continue
        try:
            entry = json.loads(raw)
        except ValueError:
            continue
        if entry.get("type") != "assistant" or entry.get("isSidechain"):
            continue
        message = entry.get("message") or {}
        # API のエラーなどを Claude Code が代わりに書いた行は英語の定型文で、モデルの応答ではない。
        if message.get("model") == "<synthetic>":
            continue
        texts = [
            c.get("text") or "" for c in message.get("content") or [] if isinstance(c, dict) and c.get("type") == "text"
        ]
        text = "\n".join(t for t in texts if t.strip())
        if text:
            return entry.get("uuid") or hashlib.sha256(text.encode()).hexdigest(), text
    return None


def first_time(session_id, key):
    """この key で初めて呼ばれたら True。並列のツール呼び出しで同時に走っても、True になるのは 1 回だけ。"""
    directory = os.path.join(STATE_DIR, re.sub(r"[^A-Za-z0-9-]", "_", session_id))
    os.makedirs(directory, exist_ok=True)
    try:
        fd = os.open(
            os.path.join(directory, re.sub(r"[^A-Za-z0-9-]", "_", key)),
            os.O_CREAT | os.O_EXCL | os.O_WRONLY,
            0o600,
        )
    except FileExistsError:
        return False
    os.close(fd)
    return True


def main():
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return
    # subagent の text はユーザーに見えず、メインの文脈にも結果としてしか戻らない。
    if payload.get("agent_id"):
        return
    path = payload.get("transcript_path")
    session_id = payload.get("session_id")
    if not path or not session_id:
        return
    try:
        found = latest_text(path)
        if found is None or not is_english(found[1]) or not first_time(session_id, found[0]):
            return
    except Exception as e:
        # ツールを呼ぶたびに走るので、知らせるのはセッションに 1 回だけにする。黙ると壊れたことに気づけない。
        try:
            if first_time(session_id, "error"):
                message = f"reply-language-guard が失敗した（{type(e).__name__}）"
                print(json.dumps({"systemMessage": message}, ensure_ascii=False))
        except Exception:
            pass
        return
    output = {
        "hookSpecificOutput": {
            "hookEventName": payload.get("hook_event_name") or "PostToolUse",
            "additionalContext": MESSAGE,
        }
    }
    print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    main()
