"""guard-branch-base.sh が使う、bash のコマンド文字列の解析。

標準入力のコマンド文字列から、ベース (start-point) を付けずにブランチを作る
git switch -c / -C と git checkout -b / -B を探す。見つけたコマンドごとに、
対象のリポジトリの現在のブランチを 1 行ずつ標準出力へ書く。detach していれば
HEAD を書き、リポジトリを特定できなければその行を書かない。

引数は 1 つで、コマンドを実行するディレクトリ (フック入力の cwd)。
解析に失敗したら、標準エラーへ 1 行書いて exit 1 する。

コマンドとして読むのは bash が実行する部分だけである。引用符の中、終端を引用符で
囲んだヒアドキュメントの本文、コメントは読まない。$(...)、バッククォート、<(...) の中、
シェルの -c (bash -c など) と eval に渡した文字列、xargs や sudo の引数にした git は読む。
"""

import os
import re
import subprocess
import sys

# 単語のうち、実行時まで値が決まらない部分 ($VAR や $(...)) の代わりに入れる。
# 引数に NUL は現れないので、オプション名やブランチ名と一致しない。
UNKNOWN = "\0"

SHELLS = {"bash", "sh", "zsh", "dash", "ksh"}
VARIABLE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|[0-9@*#?$!-]")

# git のグローバルオプションのうち、値を次の単語に取るもの (2.54 / 2.56 で実測)
GIT_VALUE_OPTS = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--config-env", "--attr-source"}
# 対象のリポジトリを変えるもの。現在のブランチを調べるときに同じものを渡す。
GIT_REPO_OPTS = {"-C", "--git-dir", "--work-tree"}

# longs は git switch -h / git checkout -h の一覧 (2.54 と 2.56 で同じ)。parse-options は
# 長いオプションを一意な接頭辞に省略させる (--cr は --create) ので、解決に全部の名前が要る。
SWITCH = {
    "create": {"c", "C", "create", "force-create"},
    "value": {"conflict", "orphan"},
    "optional": {"t"},
    "longs": {
        "create", "force-create", "guess", "discard-changes", "quiet", "recurse-submodules",
        "progress", "merge", "conflict", "detach", "track", "force", "orphan",
        "overwrite-ignore", "ignore-other-worktrees",
    },
    # git switch -c <new> -- <start-point> は -- の後ろを起点にする。
    "start_after_dashdash": True,
}
CHECKOUT = {
    "create": {"b", "B"},
    "value": {"U", "conflict", "orphan", "unified", "inter-hunk-context", "pathspec-from-file"},
    "optional": {"t"},
    "longs": {
        "guess", "overlay", "auto-advance", "quiet", "recurse-submodules", "progress", "merge",
        "conflict", "detach", "track", "force", "orphan", "overwrite-ignore",
        "ignore-other-worktrees", "ours", "theirs", "patch", "unified", "inter-hunk-context",
        "ignore-skip-worktree-bits", "pathspec-from-file", "pathspec-file-nul",
    },
    # git checkout -b <new> -- <x> の x はパスとして扱われ、起点にならない。
    "start_after_dashdash": False,
}


class _Command:
    """読みかけの単純コマンド。"""

    def __init__(self):
        self.words = []
        self.redirect = None  # 次の単語がリダイレクト先なら、その種類
        self.discard_word()

    def discard_word(self):
        self.parts = None  # 読みかけの単語の断片。None は単語の外にいること
        self.quoted = False  # 読みかけの単語に引用符かバックスラッシュがある
        self.tilde = False  # 読みかけの単語が引用符の外の ~ で始まった

    def add(self, text):
        if self.parts is None:
            self.parts = []
        self.parts.append(text)

    def end_word(self, heredocs):
        if self.parts is None:
            return
        word = "".join(self.parts)
        if self.tilde and (word == "~" or word.startswith("~/")):
            word = os.path.expanduser("~") + word[1:]
        if self.redirect in ("heredoc", "heredoc-strip"):
            heredocs.append((word, self.redirect == "heredoc-strip", not self.quoted))
        elif self.redirect is None:
            self.words.append(word)
        self.redirect = None
        self.discard_word()


class Lexer:
    """bash のコマンド文字列を単純コマンド (単語のリスト) に分ける。"""

    def __init__(self, text):
        self.s = text
        self.commands = []

    def run(self):
        self.scan(0, None)
        return self.commands

    def scan(self, i, closer):
        """s[i:] を単純コマンドに分ける。closer が ")" なら対応する閉じ括弧の次の位置を返す。"""
        s, n = self.s, len(self.s)
        cur = _Command()
        heredocs = []  # 本文を読み飛ばす待ちの (終端の行, 先頭のタブを除くか, 本文を展開するか)
        depth = 0
        while i < n:
            c = s[i]
            if c == "\\":
                if not s.startswith("\n", i + 1):
                    cur.add(s[i + 1:i + 2])
                    cur.quoted = True
                i += 2
            elif c == "'":
                j = s.find("'", i + 1)
                j = n if j < 0 else j
                cur.add(s[i + 1:j])
                cur.quoted = True
                i = j + 1
            elif c == '"':
                i = self.dquote(i + 1, cur)
            elif c == "$":
                i = self.dollar(i, cur, False)
            elif c == "`":
                i = self.backquote(i + 1, cur)
            elif c in " \t":
                cur.end_word(heredocs)
                i += 1
            elif c == "\n":
                self.end_command(cur, heredocs)
                i = self.skip_heredocs(i + 1, heredocs)
            elif c == "#" and cur.parts is None:
                j = s.find("\n", i)
                i = n if j < 0 else j
            elif c in "<>" and s.startswith("(", i + 1):
                cur.add(UNKNOWN)
                i = self.scan(i + 2, ")")
            elif c in "<>" or s.startswith("&>", i):
                i = self.redirect(i, cur, heredocs)
            elif c in ";&|":
                self.end_command(cur, heredocs)
                i += 1
            elif c == "(" and s.startswith("(", i + 1) and cur.parts is None and not cur.words:
                # (( ... )) は算術式で、中の << はヒアドキュメントではない
                i = self.skip_nested(i + 2, "(", ")", 2)
            elif c == "(":
                self.end_command(cur, heredocs)
                depth += 1
                i += 1
            elif c == ")":
                self.end_command(cur, heredocs)
                i += 1
                if depth == 0 and closer == ")":
                    return i
                depth = max(depth - 1, 0)
            else:
                if cur.parts is None and c == "~":
                    cur.tilde = True
                cur.add(c)
                i += 1
        self.end_command(cur, heredocs)
        return n

    def end_command(self, cur, heredocs):
        cur.end_word(heredocs)
        if cur.words:
            self.commands.append(cur.words)
        cur.words = []
        cur.redirect = None

    def skip_heredocs(self, i, heredocs):
        s, n = self.s, len(self.s)
        for delim, strip_tabs, expands in heredocs:
            start, end = i, n
            while i < n:
                j = s.find("\n", i)
                j = n if j < 0 else j
                line = s[i:j]
                if (line.lstrip("\t") if strip_tabs else line) == delim:
                    end = i
                    i = j + 1
                    break
                i = j + 1
            if expands:
                self.expand(start, min(end, n))
        heredocs.clear()
        return min(i, n)

    def expand(self, i, end):
        """終端を引用符で囲まないヒアドキュメントの本文 s[i:end] にある、コマンド置換を読む。"""
        s = self.s
        sink = _Command()
        while i < end:
            if s[i] == "\\":
                i += 2
            elif s[i] == "$":
                i = self.dollar(i, sink, True)
            elif s[i] == "`":
                i = self.backquote(i + 1, sink)
            else:
                i += 1

    def redirect(self, i, cur, heredocs):
        s = self.s
        if cur.parts is not None and not cur.quoted and "".join(cur.parts).isdigit():
            # 2>&1 の 2 はファイル記述子で、コマンドの引数ではない
            cur.discard_word()
        else:
            cur.end_word(heredocs)
        for op, kind in (
            ("<<<", "file"), ("<<-", "heredoc-strip"), ("<<", "heredoc"),
            ("&>>", "file"), ("&>", "file"), (">>", "file"), (">&", "file"), ("<&", "file"),
            (">|", "file"), ("<>", "file"), ("<", "file"), (">", "file"),
        ):
            if s.startswith(op, i):
                cur.redirect = kind
                return i + len(op)
        return i + 1

    def dquote(self, i, cur):
        """二重引用符の中を読み、閉じ引用符の次の位置を返す。"""
        s, n = self.s, len(self.s)
        cur.add("")
        cur.quoted = True
        while i < n:
            c = s[i]
            if c == '"':
                return i + 1
            if c == "\\" and s[i + 1:i + 2] in ("$", "`", '"', "\\", "\n"):
                if s[i + 1] != "\n":
                    cur.add(s[i + 1])
                i += 2
            elif c == "$":
                i = self.dollar(i, cur, True)
            elif c == "`":
                i = self.backquote(i + 1, cur)
            else:
                cur.add(c)
                i += 1
        return n

    def dollar(self, i, cur, in_dquote):
        s, n = self.s, len(self.s)
        if s.startswith("((", i + 1):
            cur.add(UNKNOWN)
            return self.skip_nested(i + 3, "(", ")", 2)
        if s.startswith("(", i + 1):
            cur.add(UNKNOWN)
            return self.scan(i + 2, ")")
        if s.startswith("{", i + 1):
            cur.add(UNKNOWN)
            return self.skip_nested(i + 2, "{", "}", 1)
        if s.startswith("'", i + 1) and not in_dquote:
            j = i + 2
            while j < n and s[j] != "'":
                j += 2 if s[j] == "\\" else 1
            cur.add(s[i + 2:j])
            cur.quoted = True
            return j + 1
        if s.startswith('"', i + 1) and not in_dquote:
            return self.dquote(i + 2, cur)
        m = VARIABLE.match(s, i + 1)
        if m:
            cur.add(UNKNOWN)
            return m.end()
        cur.add("$")
        return i + 1

    def skip_nested(self, i, opener, closer, depth):
        s, n = self.s, len(self.s)
        while i < n and depth:
            if s[i] == "\\":
                i += 2
                continue
            if s[i] == opener:
                depth += 1
            elif s[i] == closer:
                depth -= 1
            i += 1
        return i

    def backquote(self, i, cur):
        s, n = self.s, len(self.s)
        body = []
        while i < n and s[i] != "`":
            if s[i] == "\\" and s[i + 1:i + 2] in ("`", "\\", "$"):
                body.append(s[i + 1])
                i += 2
            else:
                body.append(s[i])
                i += 1
        self.commands.extend(Lexer("".join(body)).run())
        cur.add(UNKNOWN)
        return i + 1


def resolve_long(name, longs):
    """省略された長いオプション名を正式な名前にする。決まらなければ None。"""
    if name.startswith("no-"):
        return None  # 否定形は値を取らないので、どの名前かは要らない
    if name in longs:
        return name
    hits = [long for long in longs if long.startswith(name)]
    return hits[0] if len(hits) == 1 else None


def lacks_start_point(args, spec):
    """git switch / checkout の引数が、起点を付けずにブランチを作るものか。"""
    creates = False
    starts = 0
    k = 0
    while k < len(args):
        a = args[k]
        k += 1
        if a == "--":
            if spec["start_after_dashdash"]:
                starts += len(args) - k
            break
        if a.startswith("--"):
            name, eq, _ = a[2:].partition("=")
            name = resolve_long(name, spec["longs"])
            if name in spec["create"]:
                creates = True
            if (name in spec["create"] or name in spec["value"]) and not eq:
                k += 1
        elif a.startswith("-") and a != "-":
            # -qc y のように短いオプションはまとめられ、値を取るものの後ろは値になる (-cy)
            for pos, ch in enumerate(a[1:], 1):
                if ch in spec["create"]:
                    creates = True
                if ch in spec["create"] or ch in spec["value"]:
                    if pos == len(a) - 1:
                        k += 1
                    break
                if ch in spec["optional"]:
                    break
        else:
            starts += 1
    return creates and starts == 0


def unbased_branch_repo(args):
    """git の引数がベース無しの派生なら、対象のリポジトリを決めるオプションを返す。違えば None。"""
    repo = []
    k = 0
    while k < len(args) and args[k].startswith("-"):
        a = args[k]
        if a in GIT_VALUE_OPTS:
            if a in GIT_REPO_OPTS:
                repo += args[k:k + 2]
            k += 2
        else:
            if a.split("=", 1)[0] in GIT_REPO_OPTS:
                repo.append(a)
            k += 1
    if k >= len(args):
        return None
    spec = {"switch": SWITCH, "checkout": CHECKOUT}.get(args[k])
    if spec is None or not lacks_start_point(args[k + 1:], spec):
        return None
    return repo


def shell_script(args):
    """bash -c <script> の <script> を返す。-c が無ければ None。"""
    has_c = False
    k = 0
    while k < len(args):
        a = args[k]
        if a in ("-o", "+o", "-O", "+O"):
            k += 2
        elif a.startswith("--"):
            k += 1
        elif len(a) > 1 and a[0] in "-+":
            has_c = has_c or (a[0] == "-" and "c" in a[1:])
            k += 1
        else:
            return a if has_c else None
    return None


def current_branch(repo, cwd):
    if any(UNKNOWN in opt for opt in repo):
        return None
    try:
        result = subprocess.run(
            ["git", *repo, "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=cwd, capture_output=True, text=True, errors="replace",
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def branches(text, cwd):
    found = []
    for words in Lexer(text).run():
        # コマンド名に限らず、最初に現れた git から読む。xargs、sudo -u、env、time などの
        # 引数にした git を、それぞれのオプションを知らずに拾える。
        k = next((k for k, w in enumerate(words) if os.path.basename(w) in ("git", "eval", *SHELLS)), None)
        if k is None:
            continue
        name, args = os.path.basename(words[k]), words[k + 1:]
        if name == "git":
            repo = unbased_branch_repo(args)
            branch = None if repo is None else current_branch(repo, cwd)
            if branch:
                found.append(branch)
        elif name == "eval":
            found += branches(" ".join(args), cwd)
        else:
            script = shell_script(args)
            if script is not None:
                found += branches(script, cwd)
    return found


def main():
    cwd = sys.argv[1] if len(sys.argv) > 1 else "."
    text = sys.stdin.buffer.read().decode("utf-8", "surrogateescape")
    try:
        found = branches(text, cwd)
    except Exception as e:
        # トランスクリプトに出るのは stderr の 1 行目だけなので、トレースバックにしない
        print(f"guard-branch-base: コマンド文字列を解析できず、判定していない ({type(e).__name__}: {e})",
              file=sys.stderr)
        sys.exit(1)
    for branch in found:
        print(branch)


if __name__ == "__main__":
    main()
