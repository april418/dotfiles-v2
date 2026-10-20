"""guard-branch-base.sh が使う、bash のコマンド文字列の解析。

標準入力のコマンド文字列から、ベース (start-point) を付けずにブランチを作る
git switch -c / -C、git checkout -b / -B、git worktree add -b / -B を探す。見つけた
コマンドごとに、対象のリポジトリの現在のブランチを 1 行ずつ標準出力へ書く。detach
していれば HEAD を書き、リポジトリを特定できなければその行を書かない。

引数は 1 つで、コマンドを実行するディレクトリ (フック入力の cwd)。cd / pushd / popd の
後ろのコマンドは移動先で判定する。移動先が実行時まで決まらないもの (cd "$X"、直前に
cd していない cd - など) と、今は無いディレクトリへの移動は、移動しなかったものとして扱う。
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

# cd の前に置いても、cd を今のシェルで実行させる語
CD_PREFIXES = {"if", "then", "else", "elif", "do", "while", "until", "!", "{", "time", "builtin", "command"}
ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\+?=")
# bash の -L / -P / -e / -@ と、zsh の -q / -s
CD_OPTION = re.compile(r"-[LPe@qs]+")
# zsh の cd +2 / cd -1 はディレクトリスタックを指す
CD_STACK = re.compile(r"[+-][0-9]+")
EMPTY_PARENS = re.compile(r"\(\s*\)")

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
    "paths": 0,  # 起点より前に置く位置引数の数
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
    "paths": 0,
    # git checkout -b <new> -- <x> の x はパスとして扱われ、起点にならない。
    "start_after_dashdash": False,
}
# git worktree add -h の一覧 (2.54 と 2.56 で同じ)。-b / -B に長い名前は無い。
WORKTREE_ADD = {
    "create": {"b", "B"},
    "value": {"reason"},
    "optional": set(),
    "longs": {
        "force", "orphan", "detach", "checkout", "lock", "reason", "quiet", "track",
        "guess-remote", "relative-paths",
    },
    # git worktree add -b <new> <path> [<commit-ish>]。-- の後ろも <path> と起点として読む。
    "paths": 1,
    "start_after_dashdash": True,
    # --orphan -b <new> は中身の無いブランチを作るので、HEAD のコミットを引き連れない
    "unborn": {"orphan"},
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
    """bash のコマンド文字列を単純コマンドに分ける。

    run() は (単語のリスト, そのコマンドを実行するときの状態) のリストを返す。状態は
    state() と同じ (cwd, oldpwd, dirs, lost) で、cd / pushd / popd をたどったもの。
    """

    def __init__(self, text, cwd, oldpwd=None, dirs=(), lost=False):
        self.s = text
        self.commands = []
        self.cwd = cwd
        self.oldpwd = oldpwd  # cd - の移動先。コマンド文字列の中で cd するまでは分からない
        # pushd で積んだ (ディレクトリ, lost)。コマンド文字列より前に積んだものは分からない
        self.dirs = dirs
        self.lost = lost  # 直前の移動先が分からず、cwd は最後に分かっていた場所である
        self.braces = 0  # 開いている { ... } の数
        self.functions = []  # 読んでいる関数の本体ごとの、開いたときの (braces, 入る前の状態)
        self.function_next = False  # 次の { ... } が関数の本体になる

    def state(self):
        return self.cwd, self.oldpwd, self.dirs, self.lost

    def restore(self, state):
        self.cwd, self.oldpwd, self.dirs, self.lost = state

    def run(self):
        self.scan(0, None)
        return self.commands

    def scan(self, i, closer):
        """s[i:] を単純コマンドに分ける。closer が ")" なら対応する閉じ括弧の次の位置を返す。"""
        s, n = self.s, len(self.s)
        cur = _Command()
        heredocs = []  # 本文を読み飛ばす待ちの (終端の行, 先頭のタブを除くか, 本文を展開するか)
        outer = []  # 開いている ( ... ) ごとの、入る前の状態
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
                i = self.subshell(i + 2)
            elif c in "<>" or s.startswith("&>", i):
                i = self.redirect(i, cur, heredocs)
            elif c in ";&|":
                op = s[i:i + 2] if s[i:i + 2] in ("&&", "||", "|&") else c
                self.end_command(cur, heredocs, op)
                i += len(op)
            elif c == "(" and s.startswith("(", i + 1) and cur.parts is None and not cur.words:
                # (( ... )) は算術式で、中の << はヒアドキュメントではない
                i = self.skip_nested(i + 2, "(", ")", 2)
            elif c == "(" and EMPTY_PARENS.match(s, i) and (
                cur.words if cur.parts is None else not "".join(cur.parts).endswith("=")
            ):
                # f() { ... } は関数の定義で、本体は呼ぶまで動かない。a=() は空の配列の代入である
                self.end_command(cur, heredocs)
                self.function_next = True
                i = EMPTY_PARENS.match(s, i).end()
            elif c == "(":
                self.end_command(cur, heredocs)
                outer.append(self.state())
                i += 1
            elif c == ")":
                self.end_command(cur, heredocs)
                i += 1
                if not outer and closer == ")":
                    return i
                if outer:
                    self.restore(outer.pop())
            else:
                if cur.parts is None and c == "~":
                    cur.tilde = True
                cur.add(c)
                i += 1
        self.end_command(cur, heredocs)
        return n

    def end_command(self, cur, heredocs, op=""):
        """読みかけのコマンドを閉じる。op はその後ろの演算子 (; && || | |& &) で、改行などは空。"""
        cur.end_word(heredocs)
        words = cur.words
        if words:
            self.commands.append((words, self.state()))
            # function f { ... } の { は 3 語目に来る
            body = words[2:] if words[0] == "function" else words
            self.open_groups(body, words[0] == "function")
            # | と & の前のコマンドはサブシェルで動くので、cd が後ろに残らない。パイプラインの
            # 最後の要素は、bash ではサブシェルだが zsh では今のシェルで動く。Bash ツールは
            # 利用者のシェルで動き、このリポジトリが設定するのは zsh なので、zsh に合わせて残す
            if op not in ("|", "|&", "&"):
                self.chdir(body)
            if words[0] == "}":
                self.braces = max(self.braces - 1, 0)
                if self.functions and self.functions[-1][0] == self.braces:
                    self.restore(self.functions.pop()[1])
        cur.words = []
        cur.redirect = None

    def open_groups(self, words, after_function):
        """コマンドの先頭の { を数える。関数の本体なら、閉じたときに戻す状態を積む。"""
        opens = 0
        for w in words:
            if w == "{":
                opens += 1
            elif w not in CD_PREFIXES:
                break
        if opens and (self.function_next or after_function):
            self.functions.append((self.braces, self.state()))
        # function f と書いて改行してから { を書いたときは、次の { が本体になる
        self.function_next = after_function and not opens
        self.braces += opens

    def chdir(self, words):
        """cd / pushd / popd なら、self.cwd を移動先にする。"""
        k = 0
        while k < len(words) and (words[k] in CD_PREFIXES or ASSIGNMENT.match(words[k])):
            k += 1
        name, args = (words[k], words[k + 1:]) if k < len(words) else ("", [])
        dirs, lost = self.dirs, False
        if name == "cd":
            while args and CD_OPTION.fullmatch(args[0]):
                args = args[1:]
            if args[:1] == ["--"]:
                args = args[1:]
            if not args:
                target = os.path.expanduser("~")
            elif args == ["-"]:
                target = self.oldpwd
            elif len(args) > 1 or CD_STACK.fullmatch(args[0]):
                target = None
            else:
                target = args[0]
        elif name == "pushd" and len(args) == 1 and args[0][:1] not in ("-", "+"):
            target, dirs = args[0], dirs + ((self.cwd, self.lost),)
        elif name == "popd" and not args and dirs:
            (target, lost), dirs = dirs[-1], dirs[:-1]
        elif name in ("pushd", "popd"):
            # 引数なしの pushd や pushd -n / +N はスタックを並べ替えるので、追うのをやめる
            target, dirs = None, ()
        else:
            return
        # 今いる場所が分からなければ、相対パスの移動先も分からない
        if target is not None and (UNKNOWN in target or self.lost and not os.path.isabs(target)):
            target = None
        if target is not None:
            target = os.path.normpath(os.path.join(self.cwd, target))
            # 長すぎる移動先は分からないものとする。cd を並べたコマンドで解析時間が長さの 2 乗に伸びるのを防ぐ
            if len(target) > 4096:
                target = None
            elif not os.path.isdir(target):
                return  # 今は無いディレクトリへの移動は失敗し、シェルの状態は変わらないものとする
        # 移動先が分からなければ、移動しなかったものとして判定を続ける。止めすぎてもベースを付けるか
        # コマンドを分けて打ち直せば済むが、通すとこのフックが防ぐはずの事故になる
        self.oldpwd, self.dirs, self.lost = self.cwd, dirs, lost or target is None
        if target is not None:
            self.cwd = target

    def subshell(self, i):
        """$(...) や <(...) の中を読み、閉じ括弧の次の位置を返す。中の cd は外に持ち出さない。"""
        state = self.state()
        i = self.scan(i, ")")
        self.restore(state)
        return i

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
            return self.subshell(i + 2)
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
        self.commands.extend(Lexer("".join(body), *self.state()).run())
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
    """git switch / checkout / worktree add の引数が、起点を付けずにブランチを作るものか。"""
    creates = unborn = False
    operands = 0
    k = 0
    while k < len(args):
        a = args[k]
        k += 1
        if a == "--":
            if spec["start_after_dashdash"]:
                operands += len(args) - k
            break
        if a.startswith("--"):
            name, eq, _ = a[2:].partition("=")
            name = resolve_long(name, spec["longs"])
            if name in spec["create"]:
                creates = True
            unborn = unborn or name in spec.get("unborn", ())
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
            operands += 1
    # 位置引数が起点の手前までしか無ければ、起点を省いている
    return creates and not unborn and operands == spec["paths"]


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
    if args[k:k + 2] == ["worktree", "add"]:
        spec, rest = WORKTREE_ADD, args[k + 2:]
    elif k < len(args):
        spec, rest = {"switch": SWITCH, "checkout": CHECKOUT}.get(args[k]), args[k + 1:]
    else:
        return None
    if spec is None or not lacks_start_point(rest, spec):
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


def branches(text, *state):
    """state は Lexer の引数 (cwd, oldpwd, dirs, lost) で、cwd のほかは省ける。"""
    found = []
    for words, (cwd, oldpwd, dirs, lost) in Lexer(text, *state).run():
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
            # eval は今のシェルで動くので、cd - の移動先も pushd のスタックも引き継ぐ
            found += branches(" ".join(args), cwd, oldpwd, dirs, lost)
        else:
            script = shell_script(args)
            if script is not None:
                # bash -c は子のシェルで動き、OLDPWD もスタックも引き継がない
                found += branches(script, cwd, None, (), lost)
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
