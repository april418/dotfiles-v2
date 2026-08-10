"""cwd 配下のどのプロジェクトが「作業中」かを transcript から判定する。

compact 関連のフック 2 本（保存側と復旧側）が同じ判定を必要とする。片方だけ
基準が変わると、保存したのに復旧しない / 無関係なものが混ざる状態になり、
しかもエラーが出ないので気づけない。ここに 1 本化する。

複数リポジトリを束ねた親ディレクトリで起動すると候補が全部ヒットする
（実測で 6 件）。transcript の出現回数で明確に差が出る（7797 / 1099 / 6 / 3 / 0）
ので、それで絞る。
"""

import os
import pathlib

# 子を探す深さ。リポジトリ直下と、その 1 つ下のネストまでで足りる。
MAX_DEPTH = 3
# 出現回数の下限（絶対値）。名前がたまたま 1〜2 回出ただけのものを弾く。
MIN_MENTIONS = 10
# 出現回数の下限（最大値に対する比）。固定閾値だけでは足りない。実測分布は
# 20681 / 575 / 20 / 6 / 3 / 0 で、10 回固定だと「20 回」の無関係な
# リポジトリが通ってしまう。1% にすると 207 が境になり、上位 2 つで切れる。
MIN_RATIO = 0.01
# 同時に扱うプロジェクトの上限。
MAX_PROJECTS = 3

SKIP_DIRS = {"node_modules", ".git", "dist", "build", ".next", "vendor", "target"}


def count_mentions(transcript, roots):
    """transcript に各プロジェクトのパスが何回現れるかを数える。

    transcript は数十 MB になるのでブロック単位で読む。境界をまたぐ一致を
    落とさないよう、前ブロックの末尾を繰り越す。
    """
    counts = {r: 0 for r in roots}
    if not transcript or not os.path.isfile(transcript):
        return counts

    # <project-root>/ の形で数える。単なる名前だと MCP のツール名などが混ざる。
    needles = {r: f"{r}/" for r in roots}
    overlap = max((len(n) for n in needles.values()), default=0)
    tail = ""
    try:
        with open(transcript, encoding="utf-8", errors="ignore") as f:
            while True:
                block = f.read(1 << 20)
                if not block:
                    break
                chunk = tail + block
                for r, needle in needles.items():
                    counts[r] += chunk.count(needle)
                tail = chunk[-overlap:] if overlap else ""
    except Exception:
        return {r: 0 for r in roots}
    return counts


def _scan(cwd, marker_is_dir, marker):
    """cwd 配下で marker を持つディレクトリを集める。"""
    found = []
    base_depth = len(cwd.parts)
    for root, dirs, files in os.walk(cwd):
        rootp = pathlib.Path(root)
        if len(rootp.parts) - base_depth >= MAX_DEPTH:
            dirs[:] = []
            continue
        # 判定を先に行う。SKIP_DIRS には .git が入っているので、先に間引くと
        # marker='.git' が永遠に見つからない (実際にこれで 0 件になった)。
        names = dirs if marker_is_dir else files
        if marker in names:
            found.append(rootp)
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
    return found


def claude_md_files(cwd, transcript):
    """作業中プロジェクトの .claude/CLAUDE.md を返す。

    cwd から親へ遡って見つかればそれを使う（cwd がリポジトリ内にある通常の
    ケース）。見つからない場合だけ子を探す。
    """
    for d in [cwd, *cwd.parents]:
        candidate = d / ".claude" / "CLAUDE.md"
        if candidate.is_file():
            return [candidate]

    holders = [
        p.parent
        for p in _scan(cwd, marker_is_dir=False, marker="CLAUDE.md")
        if p.name == ".claude"
    ]
    return [r / ".claude" / "CLAUDE.md" for r in _rank(holders, transcript)]


def git_repos(cwd, transcript):
    """作業中プロジェクトの git リポジトリのルートを返す。"""
    roots = _scan(cwd, marker_is_dir=True, marker=".git")
    return _rank(roots, transcript)


def _rank(roots, transcript):
    roots = list(dict.fromkeys(roots))
    if len(roots) <= 1:
        return roots
    counts = count_mentions(transcript, roots)
    top = max(counts.values(), default=0)
    if top == 0:
        # transcript が読めない / 一致が無い。どれが作業中か判断できないので
        # 推測で選ばない。誤ったものを流すより何も流さないほうがよい。
        return []
    floor = max(MIN_MENTIONS, top * MIN_RATIO)
    ranked = sorted(roots, key=lambda r: -counts[r])
    return [r for r in ranked if counts[r] >= floor][:MAX_PROJECTS]
