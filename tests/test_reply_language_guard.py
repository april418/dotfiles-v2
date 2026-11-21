"""フック reply-language-guard.py を、一時ファイルに作った会話記録で確かめる。

yomiyasu の lint を使う検査は、プラグインが入っている環境（installed_plugins.json がある）でだけ流す。
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest import mock

HOOK_PY = Path(__file__).resolve().parents[1] / "ansible/roles/claude/files/hooks/reply-language-guard.py"


def load_hook():
    # hooks/ は丸ごと ~/.claude/hooks/ へコピーされるので、読み込みで __pycache__ を作ると配布先にも入る。
    spec = importlib.util.spec_from_file_location("reply_language_guard", HOOK_PY)
    module = importlib.util.module_from_spec(spec)
    saved = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = saved
    return module


hook = load_hook()


def write_transcript(directory, content):
    entry = {
        "type": "assistant",
        "uuid": str(uuid.uuid4()),
        "message": {"id": "msg_" + uuid.uuid4().hex, "model": "claude-opus-5-5", "content": content},
    }
    path = Path(directory) / "transcript.jsonl"
    path.write_text(json.dumps(entry, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    return str(path)


def write_block(path, content):
    return {
        "type": "tool_use",
        "id": "toolu_" + uuid.uuid4().hex,
        "name": "Write",
        "input": {"file_path": path, "content": content},
    }


class FirstBatchTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        # lint を読み込まないよう、プラグインの記録の無い設定ディレクトリを向ける。
        patcher = mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": self.dir.name})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.dir.cleanup)

    def run_batch(self, content):
        path = write_transcript(self.dir.name, content)
        payload = {"transcript_path": path, "cwd": self.dir.name}
        context, _ = hook.on_batch(payload, "test-" + uuid.uuid4().hex)
        return context or ""

    def test_english_text_alone(self):
        context = self.run_batch([{"type": "text", "text": "I will check the build output and report back."}])
        self.assertIn("英語", context)

    def test_english_text_with_write_in_same_message(self):
        content = [
            {"type": "text", "text": "I will check the build output and report back."},
            write_block("/tmp/x/notes.md", "日本語のメモを書きます。"),
        ]
        self.assertIn("英語", self.run_batch(content))


class ProseWrittenTest(unittest.TestCase):
    def test_skips_code(self):
        self.assertEqual(hook.prose_written(write_block("/tmp/x/a.py", "# 日本語のコメント")), "")

    def test_skips_word_lists(self):
        block = write_block("/tmp/x/hooks/yomiyasu-words/flag-patterns.txt", "帯→区分\t帯ごと")
        self.assertEqual(hook.prose_written(block), "")

    def test_edit_new_string(self):
        block = {
            "type": "tool_use",
            "id": "t",
            "name": "Edit",
            "input": {"file_path": "/tmp/x/SKILL.md", "old_string": "a", "new_string": "新しい文"},
        }
        self.assertEqual(hook.prose_written(block), "新しい文")

    def test_html_keeps_inline_text_and_drops_code(self):
        body = "<section><h2>見出し</h2><p>文脈が <b>40 万</b>トークン</p><pre>帯ごと</pre><p>x <code>y</code></p></section>"
        self.assertEqual(hook.prose_written(write_block("/tmp/x/s.html", body)), "見出し\n文脈が 40 万トークン\nx")


@unittest.skipUnless(hook.load_lint(), "yomiyasu プラグインが入っていない")
class SharedWordsTest(unittest.TestCase):
    """hooks/yomiyasu-words/flag-patterns.txt の当たりと外れ。"""

    def terms(self, text):
        lint = hook.load_lint()
        _, terms = hook.calque_words(lint, hook.project_words(lint, None), text)
        return terms

    def test_hits(self):
        for text in (
            "反映後は文脈が 40 万トークンを超えたリクエストがほぼ消えた。",
            "委譲のたびに文脈が落ちる。",
            "文脈窓は 1M ある。",
            "費用は `bands` の帯ごとの 1 件の費用とあわせて読む。",
            "40 万トークンの帯がほぼ消えた。",
        ):
            with self.subTest(text=text):
                self.assertTrue(self.terms(text))

    def test_ordinary_japanese(self):
        for text in (
            "コードと文脈から推測して進める。",
            "前後の文脈が大きく異なる。",
            "文脈を超えた引用。",
            "原文の文脈を引き継いで訳す。",
            "時間帯ごとに分ける。",
            "年齢帯ごとに数える。",
            "価格帯の広い商品。",
            "白い帯ごと上に乗っている。",
            "帯域を広げる。",
        ):
            with self.subTest(text=text):
                self.assertEqual(self.terms(text), [])


if __name__ == "__main__":
    unittest.main()
