#!/usr/bin/env python3
"""主系列の直近の応答本文が英語なら、日本語に戻す一文を PostToolUse の additionalContext で差し込む。

長い会話では、応答本文が英語にずれ、そのまま英語が続くことがある（グローバル指示の「言語」は files/AGENTS.md）。
ずれた text 1 つにつき 1 回だけ、文脈のいちばん新しい位置に差し込む。日本語のあいだは何も出さない。

見るのは会話記録の text だけで、thinking の要約（thinking display の updates）として画面に出る行は対象にしない。
"""

import hashlib
import json
import os
import re
import stat
import sys
import tempfile

# ツールを呼ぶたびに走るので、会話記録は末尾だけを読む。直前の text がこれより前にあれば、取り逃して何もしない。
TAIL_BYTES = 2 * 1024 * 1024
# 同じ text に 2 回差し込まないための印を置く。英語の text 1 つに空のファイルが 1 つ増えるだけなので、消さない。
# Linux の /tmp はほかのユーザーと共有なので、uid を名前に入れ、自分だけが読み書きできるようにする。
STATE_DIR = os.path.join(tempfile.gettempdir(), f"claude-reply-language-guard-{os.getuid()}")

KANA = re.compile("[\u3040-\u30ff]+")
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
    "直前の応答本文が英語になっている。ユーザーが別の言語を求めていなければ、グローバル指示の「言語」に従い、"
    "合間の一文も最終応答も日本語で書く。ツールの結果が英語でも、それに続けて英語で書かない。"
)


def is_english(text):
    for pattern in NOT_PROSE:
        text = pattern.sub(" ", text)
    words = len(WORD.findall(text))
    # 「OK」「LGTM」のような短い返事は言語を決められないので数えない。
    if words < 3:
        return False
    # 英語の長い報告でも、日本語の語を引くと仮名が混ざる。日本語の文は助詞ごとに仮名の塊が出るので、
    # 仮名の塊の数が英単語の 1 割以下なら英語と見なす。
    return len(KANA.findall(text)) <= words * 0.1


def latest_text(path):
    """主系列で最後の assistant の text を (行の uuid, 本文) で返す。記録が無いか、読んだ範囲に無ければ None。

    会話記録の書き出しは少し遅れるので、直前に書いた text がまだ無いことがある。そのときは次の呼び出しで拾う。
    """
    try:
        f = open(path, "rb")
    except FileNotFoundError:
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
        # assistant の text を含まない行は、JSON として読まずに飛ばす。会話記録は空白なしの JSON で書かれる。
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


def private_dir(path):
    os.makedirs(path, mode=0o700, exist_ok=True)
    st = os.lstat(path)
    # 同じ名前をほかのユーザーが先に作っていたら、その中には書かない。
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.getuid():
        raise PermissionError(f"{path} が自分のディレクトリではない")
    return path


def first_time(session_id, key):
    """この key で初めて呼ばれたら True。並列のツール呼び出しで同時に走っても、True になるのは 1 回だけ。"""
    directory = os.path.join(private_dir(STATE_DIR), re.sub(r"[^A-Za-z0-9-]", "_", session_id))
    os.makedirs(directory, mode=0o700, exist_ok=True)
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
                message = f"reply-language-guard が失敗した（{type(e).__name__}: {str(e)[:200]}）"
                print(json.dumps({"systemMessage": message}, ensure_ascii=False))
        except Exception:
            # 印を置けないと、知らせるのもツールを呼ぶたびになるので黙る。
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
