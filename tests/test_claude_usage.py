"""token-usage skill の usage.py を、一時ディレクトリに作った会話記録で確かめる。

期待する値は SKILL.md の「数え方」と API の定価（入力・出力・キャッシュの倍率）から手で計算する。
ファイル名に token を入れないのは、権限設定の Read(**/*_token*) に当たって読めなくなるため。
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

USAGE_PY = Path(__file__).resolve().parents[1] / "ansible/roles/claude/files/skills/token-usage/scripts/usage.py"


def load_usage():
    # scripts/ は丸ごと ~/.claude/skills/ へコピーされるので、読み込みで __pycache__ を作ると配布先にも入る。
    spec = importlib.util.spec_from_file_location("claude_usage", USAGE_PY)
    module = importlib.util.module_from_spec(spec)
    saved = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = saved
    return module


usage = load_usage()


def assistant(ts, msg_id, model="claude-opus-5-5", session="s1", **u):
    body = {"input_tokens": 0, "output_tokens": 0, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}
    body.update(u)
    return {
        "type": "assistant",
        "timestamp": ts,
        "sessionId": session,
        "requestId": "r-" + msg_id,
        "message": {"id": msg_id, "model": model, "usage": body},
    }


def compact(ts, pre, uuid=None, trigger="auto"):
    return {
        "type": "system",
        "subtype": "compact_boundary",
        "uuid": uuid or "c-" + ts,
        "timestamp": ts,
        "compactMetadata": {"preTokens": pre, "trigger": trigger},
    }


class Logs:
    """~/.claude/projects と同じ形の一時ディレクトリ。"""

    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def write(self, rel, entries, agent=None):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(json.dumps(e) + "\n" for e in entries))
        if agent:
            path.with_suffix(".meta.json").write_text(json.dumps({"agentType": agent}))

    def run(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = usage.main(["--projects", str(self.root), *args])
        return code, json.loads(out.getvalue())

    def close(self):
        self.tmp.cleanup()


class CostTest(unittest.TestCase):
    def test_opus_prices_with_one_hour_cache_write(self):
        u = {
            "input_tokens": 1_000_000,
            "output_tokens": 1_000_000,
            "cache_read_input_tokens": 1_000_000,
            "cache_creation_input_tokens": 1_000_000,
            "cache_creation": {"ephemeral_5m_input_tokens": 0, "ephemeral_1h_input_tokens": 1_000_000},
        }
        # 入力 4 + 出力 20 + 読み取り 0.20 + 1 時間の書き込み 4×2
        self.assertAlmostEqual(usage.cost_of("claude-opus-5-5", u, False, usage.Counter()), 32.2)
        self.assertAlmostEqual(usage.cost_of("claude-opus-5-5", u, True, usage.Counter()), 64.4)

    def test_write_without_breakdown_is_five_minute(self):
        u = {"cache_creation_input_tokens": 1_000_000}
        self.assertAlmostEqual(usage.cost_of("claude-sonnet-5-5", u, False, usage.Counter()), 2.5)

    def test_unknown_model_is_reported_and_costs_nothing(self):
        unknown = usage.Counter()
        self.assertEqual(usage.cost_of("claude-new-9", {"output_tokens": 10}, False, unknown), 0.0)
        self.assertEqual(unknown["claude-new-9"], 1)

    def test_normalize_prefers_longest_id(self):
        self.assertEqual(usage.normalize_model("claude-opus-5-5[1m]"), "claude-opus-5-5")
        self.assertEqual(usage.normalize_model("claude-opus-5"), "claude-opus-5")


class ReadLogsTest(unittest.TestCase):
    def setUp(self):
        self.logs = Logs()
        self.addCleanup(self.logs.close)

    def read(self, since="2026-01-01T00:00:00+00:00"):
        return usage.read_logs(usage.log_files(self.logs.root), datetime.fromisoformat(since), usage.Counter())

    def test_last_line_of_a_request_wins(self):
        self.logs.write(
            "p/s1.jsonl",
            [
                assistant("2026-11-20T10:00:00Z", "m1", output_tokens=2),
                assistant("2026-11-20T10:00:01Z", "m1", output_tokens=581),
            ],
        )
        requests, _ = self.read()
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0].output, 581)

    def test_advisor_iteration_is_priced_on_its_own_model(self):
        # 実際の記録と同じく、トップレベルの usage は advisor 以外の iteration の和になっている。
        entry = assistant("2026-11-20T10:00:00Z", "m1", input_tokens=1_000_000)
        entry["message"]["usage"]["iterations"] = [
            {"type": "message", "input_tokens": 1_000_000, "output_tokens": 0},
            {"type": "advisor_message", "model": "claude-fable-5-2", "input_tokens": 1_000_000, "output_tokens": 0},
        ]
        self.logs.write("p/s1/subagents/agent-a.jsonl", [entry], agent="general-purpose")
        r = self.read()[0][0]
        self.assertTrue(r.sub)
        self.assertEqual(r.agent, "general-purpose")
        self.assertAlmostEqual(r.cost, 4.0)
        self.assertEqual(r.adv_calls, 1)
        self.assertAlmostEqual(r.adv_cost, 8.0)

    def test_context_is_the_last_iteration_input(self):
        self.logs.write(
            "p/s1.jsonl",
            [
                assistant(
                    "2026-11-20T10:00:00Z",
                    "m1",
                    input_tokens=5,
                    cache_read_input_tokens=300_000,
                    cache_creation_input_tokens=1_000,
                )
            ],
        )
        self.assertEqual(self.read()[0][0].ctx, 301_005)

    def test_context_skips_a_trailing_advisor_iteration(self):
        entry = assistant("2026-11-20T10:00:00Z", "m1", input_tokens=3, cache_read_input_tokens=300_000)
        entry["message"]["usage"]["iterations"] = [
            {"type": "message", "input_tokens": 1, "cache_read_input_tokens": 100_000},
            {"type": "message", "input_tokens": 2, "cache_read_input_tokens": 200_000},
            {"type": "advisor_message", "model": "claude-fable-5-2", "input_tokens": 250_000},
        ]
        self.logs.write("p/s1.jsonl", [entry])
        r = self.read()[0][0]
        self.assertEqual(r.ctx, 200_002)
        self.assertEqual(r.cread, 300_000)
        self.assertEqual(r.adv_input, 250_000)

    def test_lines_copied_into_a_resumed_session_count_once(self):
        lines = [assistant("2026-11-20T10:00:00Z", "m1", output_tokens=5), compact("2026-11-20T10:05:00Z", 400_000)]
        self.logs.write("p/s1.jsonl", lines)
        self.logs.write("p/s2.jsonl", [*lines, compact("2026-11-20T10:06:00Z", 300_000)])
        requests, compactions = self.read()
        self.assertEqual(len(requests), 1)
        self.assertEqual(sorted(c["pre_tokens"] for c in compactions), [300_000, 400_000])

    def test_manual_compaction_is_not_counted(self):
        self.logs.write("p/s1.jsonl", [compact("2026-11-20T10:05:00Z", 400_000, trigger="manual")])
        self.assertEqual(self.read()[1], [])

    def test_since_drops_older_entries_and_compactions_are_read(self):
        self.logs.write(
            "p/s1.jsonl",
            [
                assistant("2026-11-01T00:00:00Z", "old"),
                assistant("2026-11-20T10:00:00Z", "new"),
                compact("2026-11-20T10:05:00Z", 400_000),
            ],
        )
        requests, compactions = self.read("2026-11-10T00:00:00+00:00")
        self.assertEqual([r.ts.day for r in requests], [20])
        self.assertEqual(compactions[0]["pre_tokens"], 400_000)


class CommandTest(unittest.TestCase):
    def setUp(self):
        self.logs = Logs()
        self.addCleanup(self.logs.close)
        # 区切りは JST 2026-11-20 17:49 = UTC 08:49。
        self.logs.write(
            "p/s1.jsonl",
            [
                assistant("2026-11-12T00:00:00Z", "too-old", cache_read_input_tokens=900_000),
                assistant("2026-11-20T08:00:00Z", "b1", cache_read_input_tokens=500_000),
                assistant("2026-11-20T08:48:59Z", "b2", cache_read_input_tokens=100_000),
                compact("2026-11-20T08:30:00Z", 900_000),
                assistant("2026-11-20T08:49:00Z", "a1", session="s2", cache_read_input_tokens=200_000),
            ],
        )

    def test_compare_splits_at_the_cut_in_local_time(self):
        code, out = self.logs.run("compare", "--cut", "2026-11-20T17:49")
        self.assertEqual(code, 0)
        before, after = out["result"]["before"], out["result"]["after"]
        self.assertEqual(before["requests"], 2)
        self.assertEqual(before["over_400k"]["requests"], 1)
        self.assertEqual(before["compactions"]["main"], 1)
        self.assertEqual(before["compactions"]["main_per_1k"], 500.0)
        self.assertEqual(after["requests"], 1)
        self.assertEqual(after["over_400k"]["requests"], 0)
        self.assertEqual(out["prices_as_of"], usage.PRICES_AS_OF)

    def test_daily_splits_the_cut_day(self):
        _, out = self.logs.run("daily", "--since", "2026-11-15", "--cut", "2026-11-20T17:49")
        self.assertEqual([row["day"] for row in out["result"]], ["2026-11-20 after", "2026-11-20 before"])
        self.assertEqual([row["requests"] for row in out["result"]], [1, 2])


if __name__ == "__main__":
    unittest.main()
