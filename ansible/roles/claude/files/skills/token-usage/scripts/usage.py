"""Claude Code の会話記録から API リクエストごとの使用量を集め、期間を比べて JSON で出す。

compare: 区切りの時刻の前後を比べる。daily: 日ごとに並べる。費用は PRICES の定価での換算で、請求額ではない。
"""

import argparse
import json
import statistics
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

PRICES_AS_OF = "2026-11-03"
# $/MTok: (入力, 出力, キャッシュ読み取り)。キャッシュ書き込みは入力の 1.25 倍（5 分）と 2 倍（1 時間）。
PRICES = {
    "claude-opus-5-5": (4, 20, 0.20),
    "claude-opus-5": (5, 25, 0.50),
    "claude-opus-4-8": (5, 25, 0.50),
    "claude-opus-4-7": (5, 25, 0.50),
    "claude-fable-5-2": (8, 40, 0.20),
    "claude-fable-5-1": (10, 50, 0.25),
    "claude-fable-5": (10, 50, 1.00),
    "claude-sonnet-5-5": (2, 10, 0.10),
    "claude-sonnet-5": (2, 10, 0.20),
    "claude-sonnet-4-6": (3, 15, 0.30),
    "claude-haiku-5-5": (0.1, 0.5, 0.01),
    "claude-haiku-4-5": (1, 5, 0.10),
}
CONTEXT_BANDS = [
    ("<100K", 0, 100_000),
    ("100-200K", 100_000, 200_000),
    ("200-400K", 200_000, 400_000),
    ("400-700K", 400_000, 700_000),
    (">=700K", 700_000, float("inf")),
]
BIG_CONTEXT = 400_000


@dataclass
class Request:
    ts: datetime
    session: str
    sub: bool
    agent: str
    model: str
    ctx: int
    cread: int
    cwrite: int
    output: int
    cost: float
    adv_calls: int
    adv_input: int
    adv_cost: float


def normalize_model(name):
    if not name:
        return ""
    name = name.split("[")[0]
    # 長い ID から当てる。claude-opus-5 が claude-opus-5-5 を先に取らないように。
    for known in sorted(PRICES, key=len, reverse=True):
        if name.startswith(known):
            return known
    return name


def cost_of(model, usage, fast, unknown):
    price = PRICES.get(model)
    if price is None:
        unknown[model] += 1
        return 0.0
    inp, out, read = price
    created = usage.get("cache_creation") or {}
    w5m = created.get("ephemeral_5m_input_tokens")
    w1h = created.get("ephemeral_1h_input_tokens")
    if w5m is None and w1h is None:
        w5m, w1h = usage.get("cache_creation_input_tokens") or 0, 0
    dollars = (
        (usage.get("input_tokens") or 0) * inp
        + (usage.get("output_tokens") or 0) * out
        + (usage.get("cache_read_input_tokens") or 0) * read
        + (w5m or 0) * inp * 1.25
        + (w1h or 0) * inp * 2
    ) / 1e6
    # fast mode は Opus 5.5 も Fable 5.2 も標準の 2 倍。
    return dollars * 2 if fast else dollars


def parse_ts(text):
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def log_files(projects):
    files = list(projects.glob("*/*.jsonl"))
    files += projects.glob("*/*/subagents/*.jsonl")
    return files


def agent_type(path):
    meta = path.with_suffix(".meta.json")
    try:
        return json.loads(meta.read_text()).get("agentType", "")
    except (OSError, ValueError):
        return ""


def read_logs(files, since, unknown):
    """リクエストと自動圧縮の一覧を返す。since より前のものは捨てる。"""
    requests = {}
    # 再開や分岐したセッションは前の行を uuid ごと別のファイルに写すので、リクエストも圧縮もキーで 1 件にする。
    compactions = {}
    for path in files:
        sub = "/subagents/" in str(path)
        agent = agent_type(path) if sub else ""
        with open(path, errors="ignore") as fh:
            for line in fh:
                if '"usage"' not in line and "compact_boundary" not in line:
                    continue
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                if "timestamp" not in entry:
                    continue
                ts = parse_ts(entry["timestamp"])
                if ts < since:
                    continue
                if entry.get("subtype") == "compact_boundary":
                    meta = entry.get("compactMetadata") or {}
                    # 手動の /compact は設定の効き目と関係ないので数えない。
                    if meta.get("trigger", "auto") == "auto":
                        compactions[entry.get("uuid") or id(entry)] = {
                            "ts": ts,
                            "sub": sub,
                            "pre_tokens": meta.get("preTokens"),
                        }
                    continue
                request = to_request(entry, ts, sub, agent, unknown)
                if request:
                    # 1 件のリクエストは複数行に分かれ、出力が途中までの行もあるので、最後の行で上書きする。
                    msg = entry["message"]
                    requests[(msg.get("id"), entry.get("requestId"))] = request
    return list(requests.values()), list(compactions.values())


def to_request(entry, ts, sub, agent, unknown):
    if entry.get("type") != "assistant":
        return None
    msg = entry.get("message") or {}
    usage = msg.get("usage")
    model = normalize_model(msg.get("model"))
    if not usage or model == "<synthetic>":
        return None
    fast = usage.get("speed") == "fast"
    iterations = usage.get("iterations") or []
    executor = [it for it in iterations if it.get("type") != "advisor_message"] or [usage]
    advisor = [it for it in iterations if it.get("type") == "advisor_message"]
    last = executor[-1]
    total = lambda key: sum(it.get(key) or 0 for it in executor)
    return Request(
        ts=ts,
        session=entry.get("sessionId", ""),
        sub=sub or bool(entry.get("isSidechain")),
        agent=agent,
        model=model,
        ctx=sum(last.get(k) or 0 for k in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")),
        cread=total("cache_read_input_tokens"),
        cwrite=total("cache_creation_input_tokens"),
        output=total("output_tokens"),
        cost=sum(cost_of(normalize_model(it.get("model")) or model, it, fast, unknown) for it in executor),
        adv_calls=len(advisor),
        adv_input=sum(it.get("input_tokens") or 0 for it in advisor),
        # advisor はキャッシュせず、fast mode も掛からない。
        adv_cost=sum(cost_of(normalize_model(it.get("model")), it, False, unknown) for it in advisor),
    )


def percentile(values, p):
    if not values:
        return 0
    values = sorted(values)
    return values[min(len(values) - 1, int(len(values) * p))]


def per_thousand(count, base):
    return round(count * 1000 / base, 1) if base else None


def summarize(requests, compactions):
    if not requests:
        return {"requests": 0}
    main = [r for r in requests if not r.sub]
    sub = [r for r in requests if r.sub]
    ctx = [r.ctx for r in requests]
    exec_cost = sum(r.cost for r in requests)
    adv_cost = sum(r.adv_cost for r in requests)
    big = [r for r in requests if r.ctx > BIG_CONTEXT]
    # キャッシュ切れでコンテキストのほぼ全体を書き直したリクエスト。subagent の開始時の小さな書き込みは数えない。
    rewrites = [r for r in requests if r.cwrite >= 100_000 and r.cwrite >= 0.8 * r.ctx]
    main_compactions = [c for c in compactions if not c["sub"]]
    pre = [c["pre_tokens"] for c in main_compactions if c["pre_tokens"]]
    bands = {}
    for name, lo, hi in CONTEXT_BANDS:
        band = [r for r in requests if lo <= r.ctx < hi]
        bands[name] = {
            "share": round(len(band) / len(requests), 4),
            "requests": len(band),
            "cost_per_request": round(sum(r.cost for r in band) / len(band), 4) if band else None,
        }
    return {
        "first": min(r.ts for r in requests).isoformat(),
        "last": max(r.ts for r in requests).isoformat(),
        "sessions": len({r.session for r in main}),
        "requests": len(requests),
        "main_requests": len(main),
        "sub_requests": len(sub),
        "cost": round(exec_cost + adv_cost, 2),
        "cost_advisor": round(adv_cost, 2),
        "cost_per_request": round((exec_cost + adv_cost) / len(requests), 4),
        "context": {
            "mean": round(statistics.mean(ctx)),
            "p50": percentile(ctx, 0.5),
            "p90": percentile(ctx, 0.9),
            "max": max(ctx),
        },
        "over_400k": {
            "requests": len(big),
            "share": round(len(big) / len(requests), 4),
            "cost_share": round(sum(r.cost for r in big) / exec_cost, 3) if exec_cost else None,
        },
        "bands": bands,
        "advisor": {
            "calls": sum(r.adv_calls for r in requests),
            "main_calls": sum(r.adv_calls for r in main),
            "sub_calls": sum(r.adv_calls for r in sub),
            "main_per_1k": per_thousand(sum(r.adv_calls for r in main), len(main)),
            "sub_per_1k": per_thousand(sum(r.adv_calls for r in sub), len(sub)),
            "sub_cost": round(sum(r.adv_cost for r in sub), 2),
            "sub_by_agent": dict(Counter(r.agent or "?" for r in sub for _ in range(r.adv_calls))),
        },
        "compactions": {
            "main": len(main_compactions),
            "sub": len(compactions) - len(main_compactions),
            "main_per_1k": per_thousand(len(main_compactions), len(main)),
            "pre_tokens_p50": percentile(pre, 0.5) if pre else None,
        },
        "rewrites": {"requests": len(rewrites)},
        "models": {
            m: round(sum(r.cost for r in requests if r.model == m), 2) for m in sorted({r.model for r in requests})
        },
    }


def local_tz(offset_hours):
    return timezone(timedelta(hours=offset_hours))


def parse_local(text, tz):
    ts = datetime.fromisoformat(text)
    return ts.replace(tzinfo=tz) if ts.tzinfo is None else ts


def compare(requests, compactions, cut, before_days):
    start = cut - timedelta(days=before_days)
    sides = {}
    for name, keep in (("before", lambda t: start <= t < cut), ("after", lambda t: t >= cut)):
        sides[name] = summarize([r for r in requests if keep(r.ts)], [c for c in compactions if keep(c["ts"])])
    return sides


def daily(requests, tz, cut):
    groups = {}
    for r in requests:
        local = r.ts.astimezone(tz)
        key = local.date().isoformat()
        if cut and local.date() == cut.astimezone(tz).date():
            key += " after" if r.ts >= cut else " before"
        groups.setdefault(key, []).append(r)
    rows = []
    for key in sorted(groups):
        group = groups[key]
        cost = sum(r.cost + r.adv_cost for r in group)
        rows.append(
            {
                "day": key,
                "requests": len(group),
                "cost": round(cost, 2),
                "cost_per_request": round(cost / len(group), 4),
                "ctx_p90": percentile([r.ctx for r in group], 0.9),
                "advisor_calls": sum(r.adv_calls for r in group),
            }
        )
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--projects", type=Path, default=Path.home() / ".claude/projects")
    parser.add_argument("--tz", type=float, default=9, help="UTC からの時差（時間）。日付と時刻の解釈に使う")
    sub = parser.add_subparsers(dest="command", required=True)
    cmp_parser = sub.add_parser("compare")
    cmp_parser.add_argument("--cut", required=True, help="区切りの時刻（例: 2026-11-20T17:49）")
    cmp_parser.add_argument("--before-days", type=float, default=7)
    day_parser = sub.add_parser("daily")
    day_parser.add_argument("--since", required=True, help="この日付から並べる（例: 2026-11-01）")
    day_parser.add_argument("--cut", help="この時刻の日を前後に分ける")
    args = parser.parse_args(argv)

    tz = local_tz(args.tz)
    cut = parse_local(args.cut, tz) if args.cut else None
    since = cut - timedelta(days=args.before_days) if args.command == "compare" else parse_local(args.since, tz)
    unknown = Counter()
    requests, compactions = read_logs(log_files(args.projects), since, unknown)
    if args.command == "compare":
        result = compare(requests, compactions, cut, args.before_days)
    else:
        result = daily(requests, tz, cut)
    print(
        json.dumps(
            {"prices_as_of": PRICES_AS_OF, "unknown_models": dict(unknown), "result": result},
            ensure_ascii=False,
            indent=1,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
