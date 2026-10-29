#!/usr/bin/env python3
"""~/.local/state/evacuated/ から、退避して 14 日を過ぎたものを消す（SessionStart の startup で動かす）。

グローバル指示（files/AGENTS.md の「シェルコマンド」）は rm を禁じ、取り除くものを evacuate（files/bin/evacuate）でここへ移させる。
ここは OS が掃除しないので、消す仕組みが無いと溜まり続ける。
"""

import datetime
import json
import os
import pathlib
import re
import shlex
import shutil
import time

# files/AGENTS.md の「退避物の掃除」に書いた日数と、files/bin/evacuate の RETENTION_DAYS に揃える。
RETENTION_DAYS = 14
# files/bin/evacuate の ROOT と揃える。
ROOT = pathlib.Path.home() / ".local" / "state" / "evacuated"
# evacuate が作る <YYYYMMDD>-<作業名> だけを対象にする。ほかの名前は人が置いたものとして触らない。
NAME = re.compile(r"^(\d{8})-")


def expired(entry, now):
    """名前の日付と、配下のすべてのディレクトリの mtime が保持期間を過ぎたか。"""
    m = NAME.match(entry.name)
    if not m:
        return False
    try:
        dated = datetime.datetime.strptime(m.group(1), "%Y%m%d").timestamp()
    except ValueError:
        return False
    cutoff = now - RETENTION_DAYS * 86400
    # 名前だけで決めると、日付を書き間違えたものが退避した直後に消える。
    # mtime だけで決めると、古いディレクトリをそのまま mv で置いたものがすぐ消える（mv は mtime を保つ）。
    if dated >= cutoff:
        return False
    # 既存の写し先へ後から mv すると、mtime が変わるのは入れた先のディレクトリだけでトップは変わらない。
    for dirpath, _, _ in os.walk(entry):
        if os.lstat(dirpath).st_mtime >= cutoff:
            return False
    return True


def prune():
    """消したものの名前と、消しきれなかったもののパスと理由を返す。"""
    try:
        entries = sorted(ROOT.iterdir())
    except FileNotFoundError:
        return [], []
    now = time.time()
    removed, failed = [], []
    for entry in entries:
        # 1 件の失敗で止めると、それまでに消したものを知らせられない。
        try:
            # リンク先は退避物ではないので、symlink は辿らない。
            if entry.is_symlink() or not entry.is_dir() or not expired(entry, now):
                continue
            # 消せないものがあっても止めずに消せる分を消し、残りを知らせる。
            shutil.rmtree(entry, ignore_errors=True)
        except FileNotFoundError:
            # 同時に起動した別のセッションのフックが先に消した。
            continue
        except OSError as e:
            failed.append((entry, type(e).__name__))
            continue
        if entry.exists():
            failed.append((entry, "消せないものが残っている"))
        else:
            removed.append(entry.name)
    return removed, failed


def main():
    lines = []
    try:
        removed, failed = prune()
    except Exception as e:
        # 黙ると、消す仕組みが壊れたまま退避物が溜まっていくことに気づけない。
        lines.append(f"prune-evacuated が失敗した（{type(e).__name__}）")
        removed, failed = [], []
    if removed:
        lines.append(f"退避して {RETENTION_DAYS} 日を過ぎたものを {ROOT} から消した: {', '.join(removed)}")
    for path, reason in failed:
        # sudo mv で置いた root 所有のものが残るのが、最もありうる場合である。
        lines.append(f"{path} を消しきれなかった（{reason}）: sudo rm -rf -- {shlex.quote(str(path))}")
    if lines:
        # systemMessage は利用者に見せる警告で、Claude のコンテキストには入れない。
        print(json.dumps({"systemMessage": "\n".join(lines)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
