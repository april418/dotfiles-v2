#!/usr/bin/env python3
"""メインの会話（subagent を除く）の応答本文の言語の崩れを見つけ、直させる一文を additionalContext で差し込む。

見る崩れは 2 つある（グローバル指示の「言語」は files/AGENTS.md）。

- 英語にずれた text。長い会話では、英語で返るツールの結果に続けて応答本文が英語になる
- 英語の術語を漢字に置き換えた造語（version を「版」と書くなど）。yomiyasu プラグインの lint で拾う

登録するイベントは 2 つで、どちらもこのスクリプトを呼ぶ。

- PostToolBatch: ツールのバッチが終わるたびに、まだ見ていない直近の text をすべて見る。会話記録の
  書き出しは遅れるので、最新の 1 件だけを見ると、遅れて書かれた text を取り逃す
- Stop: 最終応答（last_assistant_message）が英語なら、日本語で書き直させる。最終応答の後には
  ツールを呼ばないので、PostToolBatch では間に合わない。造語は書き直させず、次のバッチで名指しする

Claude Code では、合間の一文が会話記録でも画面でも thinking の要約に置き換わることがあり、その要約は英語の
こともある。置き換わった一文は text の無いメッセージの thinking に入る。会話記録では、空の thinking の
直後か、2 つ以上ある thinking の最後に入っている。どちらにも当たらない thinking は見ない。
"""

import hashlib
import importlib.util
import json
import os
import re
import stat
import sys
import tempfile

# バッチごとに走るので、会話記録は末尾だけを読む。
TAIL_BYTES = 2 * 1024 * 1024
# 1 回に見るメッセージの数。会話記録の遅れで前のバッチに間に合わなかった text を拾える数にしてある。
RECENT_MESSAGES = 10
# 見た text の記録を残す数。RECENT_MESSAGES の中の text の数より十分多ければ、同じ text を 2 回見ない。
SEEN_LIMIT = 500
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
# 指摘の文面の形を読む lint の出力形式。違う形式では語を取り出せないので、知らせて lint を使わない。
LINT_FORMAT_VERSION = 2
# yomiyasu の calque の型のうち、名詞の造語に当たるもの。型1（動詞）と型3（句）は定着した言い方との境が
# 文脈で決まるので、会話の中では名指ししない。
CALQUE_NOUN_TYPES = {"2", "4", "5"}
# 同じ行に型1の動詞や型3の句と名詞の型が当たると、lint の文面では語が型ごとに分かれない。型3は lint の句の
# 名前と照らして外し、型1の動詞は辞書形の語尾で外す。
VERB_ENDING = re.compile("[うくぐすつぬぶむる]$")

ENGLISH_MID = (
    "直近の応答本文の{snippets}が英語になっている。ユーザーが別の言語を求めていなければ、グローバル指示の"
    "「言語」に従い、合間の一文も最終応答も日本語で書く。ツールの結果が英語でも、それに続けて英語で書かない。"
)
ENGLISH_SUMMARY = (
    "直近の合間の一文が、画面では英語の要約（{snippets}）に置き換わって表示された。合間の一文は日本語で、"
    "グローバル指示の「言語」の長さ（1 文か短い 2 文）に収める。"
)
ENGLISH_FINAL = (
    "直前の最終応答が英語になっている。ユーザーが別の言語を求めていなければ、ツールを呼ばずに同じ内容を日本語で"
    "書き直し、それを最終応答にする。"
)
CALQUE = (
    "直近の応答本文の{words}は、英語の術語を漢字に置き換えた造語の候補（yomiyasu の lint）。その分野の人が"
    "書く呼び名（カタカナ語や原語を含む）があれば、以後はそれで書く。定着した言い方なら替えない。"
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


def is_structured(text):
    """JSON の形の最終応答。スクリプトが読む出力なので、日本語に書き直させない。"""
    return text.lstrip().startswith(("{", "["))


def text_key(text):
    return hashlib.sha256(text.strip().encode()).hexdigest()[:32]


def recent_texts(path):
    """メインの会話の最後の RECENT_MESSAGES 件のメッセージから、画面に出た行を古い順に (記録の鍵, 種類, 本文) で返す。

    種類は "text"（text の block）か "summary"（text が無いメッセージで、合間の一文が置き換わった thinking の
    要約）。鍵はメッセージの id と block の位置で、同じ一文を後のメッセージで繰り返しても別の鍵になる。
    記録が無ければ空。
    """
    try:
        f = open(path, "rb")
    except FileNotFoundError:
        return []
    with f:
        f.seek(0, os.SEEK_END)
        size = f.tell()
        f.seek(max(0, size - TAIL_BYTES))
        data = f.read()
    lines = data.split(b"\n")
    if size > TAIL_BYTES:
        # 途中から読んだので、最初の行は欠けている。
        lines = lines[1:]
    # メッセージの id ごとに text と thinking を集める。1 つのメッセージの block は別々の行に書かれる。
    messages = {}
    for raw in reversed(lines):
        # assistant の text か thinking を含まない行は、JSON として読まずに飛ばす。会話記録は空白なしの JSON で書かれる。
        if b'"type":"assistant"' not in raw or (b'"text"' not in raw and b'"thinking"' not in raw):
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
        key = message.get("id") or entry.get("uuid")
        if key not in messages:
            # いちばん古いメッセージは、読み始めの位置で block が欠けていることがあるので 1 件多く集めて捨てる。
            if len(messages) > RECENT_MESSAGES:
                break
            messages[key] = {"text": [], "thinking": []}
        for c in message.get("content") or []:
            if isinstance(c, dict) and c.get("type") in ("text", "thinking"):
                body = (c.get(c["type"]) or "").strip()
                # thinking は空のものも位置を数えるために残す。
                if body or c["type"] == "thinking":
                    messages[key][c["type"]].insert(0, body)
    found = []
    for key, blocks in list(messages.items())[:RECENT_MESSAGES]:
        items = []
        if blocks["text"]:
            # advisor のようなサーバー側のツールを挟むと、1 つのメッセージに text が複数入る。つなぐと、英語の
            # text が日本語の text に埋もれて英語と判定されないので、block ごとに見る。
            items = [(f"{key}:t{i}", "text", t) for i, t in enumerate(blocks["text"])]
        elif len(blocks["thinking"]) >= 2:
            thinking = blocks["thinking"]
            last = len(thinking) - 1
            items = [
                (f"{key}:h{i}", "summary", t)
                for i, t in enumerate(thinking)
                if t and (i == last or (i > 0 and not thinking[i - 1]))
            ]
        found += reversed(items)
    found.reverse()
    return found


def private_dir(path):
    os.makedirs(path, mode=0o700, exist_ok=True)
    st = os.lstat(path)
    # 同じ名前をほかのユーザーが先に作っていたら、その中には書かない。
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.getuid():
        raise PermissionError(f"{path} が自分のディレクトリではない")
    return path


def state_path(session_id):
    return os.path.join(private_dir(STATE_DIR), re.sub(r"[^A-Za-z0-9-]", "_", session_id) + ".json")


def load_state(session_id):
    """セッションの状態。seen は見た text の鍵の並び、seeded は前からある text を見たことにしたか。"""
    try:
        with open(state_path(session_id), encoding="utf-8") as f:
            state = json.load(f)
    except (FileNotFoundError, ValueError):
        return {"seen": [], "seeded": False}
    if not isinstance(state, dict):
        return {"seen": [], "seeded": False}
    return {"seen": list(state.get("seen") or []), "seeded": bool(state.get("seeded"))}


def save_state(session_id, state):
    # PostToolBatch と Stop は同じセッションで重ならないので、書き換えの競合は置き換えの原子性だけで足りる。
    path = state_path(session_id)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".seen-")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump({"seen": state["seen"][-SEEN_LIMIT:], "seeded": state["seeded"]}, f)
    os.replace(tmp, path)


def first_time(session_id, key):
    """この key で初めて呼ばれたら True。seeded は変えない。"""
    state = load_state(session_id)
    if key in state["seen"]:
        return False
    state["seen"].append(key)
    save_state(session_id, state)
    return True


def stop_key(text):
    """Stop が書き直させた最終応答の鍵。Stop の入力にはメッセージの id が無いので本文で決める。"""
    return "stop:" + text_key(text)


def load_lint():
    """yomiyasu プラグインの yomiyasu_lint モジュール。入っていなければ None。

    プラグインの置き場所はバージョンごとに変わるので、Claude Code が記録する installPath から引く。
    """
    config = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude")
    try:
        with open(os.path.join(config, "plugins", "installed_plugins.json"), encoding="utf-8") as f:
            installs = json.load(f).get("plugins", {}).get("yomiyasu@yomiyasu") or []
    except (FileNotFoundError, ValueError):
        return None
    if not installs:
        return None
    # project スコープの記録はほかのプロジェクトのものでありうるので、user スコープを先に使う。
    install = next((i for i in installs if i.get("scope") == "user"), installs[0])
    scripts = os.path.join(install.get("installPath") or "", "skills", "yomiyasu", "scripts")
    path = os.path.join(scripts, "yomiyasu_lint.py")
    if not os.path.isfile(path):
        return None
    # lint は同じフォルダの markdown_visibility を import する。プラグインのフォルダに .pyc を書かない。
    sys.dont_write_bytecode = True
    sys.path.insert(0, scripts)
    spec = importlib.util.spec_from_file_location("yomiyasu_lint", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def phrase_names(lint):
    """lint の型3の句の名前。"""
    phrases = getattr(lint, "_CALQUE_PHRASES", ()) + getattr(lint, "_CALQUE_PHRASES_V250", ())
    return {name for name, _ in phrases}


def calque_words(lint, words, text):
    """text の中の、英語の術語を直訳した名詞の候補。lint の指摘の文面から語を取り出す。

    lint の出力形式が LINT_FORMAT_VERSION と違えば、文面から語を取り出せないので ValueError を出す。
    """
    result = lint.lint_text(text, words=words)
    if result.get("format_version") != LINT_FORMAT_VERSION:
        raise ValueError(
            f"yomiyasu lint の出力形式が {result.get('format_version')} で、{LINT_FORMAT_VERSION} ではない"
        )
    phrases = phrase_names(lint)
    found = []
    for finding in result.get("findings", []):
        message = finding.get("message") or ""
        if finding.get("rule") == "translated_term":
            found += re.findall(r"直訳「([^」]+)」", message)
        elif finding.get("rule") == "calque" and CALQUE_NOUN_TYPES & set(re.findall(r"型(\d)", message)):
            hit = re.search(r"当たった言い方: ([^）]+)）", message)
            if hit:
                found += [
                    w
                    for w in hit.group(1).split("、")
                    if w.strip() not in phrases and not VERB_ENDING.search(w.strip())
                ]
    return list(dict.fromkeys(w.strip() for w in found if w.strip()))


def project_words(lint, cwd):
    """作業ディレクトリから上にたどった git の最上位の .yomiyasu-words（allow.txt で外す語）。読めなければ None。"""
    try:
        return lint.resolve_words(cwd)
    except (OSError, getattr(lint, "WordsError", OSError)):
        return None


def snippet(text, limit=60):
    line = " ".join(text.split())
    return line if len(line) <= limit else line[:limit] + "…"


def quoted(texts):
    return "".join(f"「{snippet(t)}」" for t in texts)


def on_batch(payload, session_id):
    """差し込む文と、lint が失敗したときの知らせの組。"""
    found = recent_texts(payload.get("transcript_path") or "")
    if not found:
        return None, None
    state = load_state(session_id)
    if not state["seeded"]:
        # 途中から入れたセッションや再開したセッションで、前からある text をまとめて指摘しない。
        state["seen"] += [key for key, _, _ in found[:-1]]
        state["seeded"] = True
    # Stop が書き直させた最終応答は、ここで重ねて指摘しない。
    new = [(kind, t) for key, kind, t in found if key not in state["seen"] and stop_key(t) not in state["seen"]]
    state["seen"] += [key for key, _, t in found if key not in state["seen"]]
    english = [t for kind, t in new if kind == "text" and is_english(t)]
    summaries = [t for kind, t in new if kind == "summary" and is_english(t)]
    japanese = [t for _, t in new if not is_english(t) and KANA.search(t)]
    calques = []
    lint_error = None
    if japanese:
        # lint はほかのプラグインのコードなので、失敗しても英語の検査と状態の保存は続ける。
        try:
            lint = load_lint()
            if lint:
                words = project_words(lint, payload.get("cwd"))
                for text in japanese:
                    calques += calque_words(lint, words, text)
        except Exception as e:  # noqa: BLE001
            lint_error = f"reply-language-guard が yomiyasu の lint で失敗した（{type(e).__name__}: {str(e)[:200]}）"
    save_state(session_id, state)
    notes = []
    if english:
        notes.append(ENGLISH_MID.format(snippets=quoted(english)))
    if summaries:
        notes.append(ENGLISH_SUMMARY.format(snippets=quoted(summaries)))
    if calques:
        notes.append(CALQUE.format(words="".join(f"「{w}」" for w in dict.fromkeys(calques))))
    if lint_error and not first_time(session_id, "lint-error"):
        lint_error = None
    return "\n".join(notes) or None, lint_error


def on_stop(payload, session_id):
    # 書き直させた後の最終応答で、もう一度続けさせない。
    if payload.get("stop_hook_active"):
        return None, None
    text = payload.get("last_assistant_message") or ""
    if is_structured(text) or not is_english(text) or not first_time(session_id, stop_key(text)):
        return None, None
    return ENGLISH_FINAL, None


def main():
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return
    # subagent の text はユーザーに見えず、メインの文脈にも結果としてしか戻らない。
    if payload.get("agent_id"):
        return
    session_id = payload.get("session_id")
    event = payload.get("hook_event_name")
    if not session_id or event not in ("PostToolBatch", "Stop"):
        return
    try:
        context, notice = on_stop(payload, session_id) if event == "Stop" else on_batch(payload, session_id)
    except Exception as e:
        # バッチごとに走るので、知らせるのはセッションに 1 回だけにする。黙ると壊れたことに気づけない。
        try:
            if first_time(session_id, "error"):
                message = f"reply-language-guard が失敗した（{type(e).__name__}: {str(e)[:200]}）"
                print(json.dumps({"systemMessage": message}, ensure_ascii=False))
        except Exception:
            # 記録を書けないと、知らせるのもバッチごとになるので黙る。
            pass
        return
    output = {}
    if context:
        output["hookSpecificOutput"] = {"hookEventName": event, "additionalContext": context}
    if notice:
        output["systemMessage"] = notice
    if output:
        print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    main()
