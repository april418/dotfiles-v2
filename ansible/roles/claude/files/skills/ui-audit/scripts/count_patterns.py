"""ソースの CSS とマークアップで、見た目の型と残骸の出現数を数える。

    python3 count_patterns.py <ソースのディレクトリ>... [--exclude <ディレクトリ名>]...

数が多いことは欠陥の証明にならない。どこに偏っているかを見て、実画面で確かめる材料にする。
0 件も型が無いことの証明にならない。CSS-in-JS の値や、ビルドで生成するクラスは数えられない。
"""

import argparse
import re
from collections import Counter
from pathlib import Path

TEMPLATE_SUFFIXES = {".vue", ".svelte", ".astro", ".html", ".erb", ".php", ".hbs", ".ejs"}
STYLE_SUFFIXES = {".css", ".scss", ".sass", ".less", ".pcss"} | TEMPLATE_SUFFIXES
MARKUP_SUFFIXES = {".tsx", ".jsx", ".ts", ".js", ".mjs", ".cjs", ".mdx", ".pug"} | TEMPLATE_SUFFIXES
SKIPPED_DIRS = {"node_modules", "dist", "build", "out", "coverage", "vendor", "__tests__", ".next", ".nuxt", ".git"}

CSS_PATTERNS = {
    "background-clip: text": r"background-clip:\s*text",
    "backdrop-filter": r"backdrop-filter:",
    "box-shadow": r"box-shadow:",
    "text-transform: uppercase": r"text-transform:\s*uppercase",
    "gradient()": r"(linear|radial|conic)-gradient\(",
    "transition: all": r"transition:\s*all",
    "outline: none / 0 / transparent": r"outline:\s*(none|0\b|[^;}]*transparent)",
    ":focus-visible": r":focus-visible",
    ":focus": r":focus\b(?!-)",
    ":hover": r":hover",
    "@keyframes": r"@keyframes",
    "animation:": r"(?<![-\w])animation:",
    "prefers-reduced-motion": r"prefers-reduced-motion",
    "片側だけの太い枠": r"border-(left|right|top|bottom|inline-start|inline-end|block-start|block-end)(-width)?:\s*([3-9]|\d{2,})px",
    "hover で浮く": r":hover[^{}]*\{[^{}]*(translate(Y|3d)?\([^)]*|translate:[^;}]*)-(?!50%)[.\d]",
    "hover で拡大する": r":hover[^{}]*\{[^{}]*scale(\(|:\s*)1\.\d",
    "負の letter-spacing": r"letter-spacing:\s*-",
    "1 未満の line-height": r"line-height:\s*(0?\.\d+|\d{1,2}%)\s*(!important\s*)?[;}]",
    "palt": r"[\"']palt[\"']",
    "word-break: auto-phrase": r"word-break:\s*auto-phrase",
}
# 接頭辞付きと無しを並べて書くのが普通なので、二重に数えないよう多いほうを取る。
PREFIXED = {"background-clip: text", "backdrop-filter"}

TAILWIND_PATTERNS = {
    "bg-gradient / bg-linear": r"\bbg-(gradient|linear)-to-",
    "紫〜青の色止め": r"\b(from|via|to)-(purple|violet|indigo|fuchsia)-\d",
    "bg-clip-text": r"\bbg-clip-text\b",
    "backdrop-blur": r"\bbackdrop-blur",
    "rounded-full": r"\brounded-full\b",
    "hover:-translate-y": r"hover:-translate-y",
    "hover:scale": r"hover:scale-",
    "uppercase + tracking": r"""["'`](?=[^"'`]*\buppercase\b)(?=[^"'`]*\btracking-)""",
    "片側だけの太い枠": r"\bborder-[lrse]-(2|4|8)\b",
    "animate-": r"\banimate-[a-z]",
}

LEFTOVER_PATTERNS = {
    'href="#"': r"""href=(["'])#?\1|href=\{(["'])#?\2\}""",
    "空の onClick": r"onClick=\{\(\)\s*=>\s*\{\s*\}\}",
    "readOnly": r"(?i)\breadonly\b",
    "準備中の表記": r"(?i)coming soon|準備中|近日公開",
    "ダミーの語": r"(?i)lorem|dummy|ダミー|架空|fictional|sample data",
    "試作の版表記": r"(?i)\bv\s?0\.\d+\b|\bhi-fi\b|\bwireframe\b",
    "定型の英語": r"(?i)(?<![.\w])(streamlin|empower|supercharg|unlock|seamless)\w*(?!\w*\s*\()|\b(world-class|get started|learn more)\b",
}

# 矢印、技術記号、図形、その他の記号、装飾記号、絵文字の範囲である。
EMOJI = re.compile("[←-⇿⌀-⏿■-◿☀-➿⬀-⯿\U0001f300-\U0001faff]")
COMMENT_PREFIXES = ("//", "*", "/*", "{/*", "<!--")
SHOWN_HITS = 40


def collect(roots, skipped):
    for root in roots:
        for path in sorted(root.rglob("*")):
            if path.is_file() and not skipped.intersection(path.relative_to(root).parts):
                yield path


def read(path):
    return path.read_text(encoding="utf-8", errors="replace")


def code_lines(path):
    for number, line in enumerate(read(path).splitlines(), 1):
        if not line.strip().startswith(COMMENT_PREFIXES):
            yield number, line


def count_in(name, pattern, text):
    if name in PREFIXED:
        return max(len(re.findall(rf"(?<!-webkit-){pattern}", text)), len(re.findall(rf"-webkit-{pattern}", text)))
    return len(re.findall(pattern, text))


def print_counts(title, patterns, files):
    print(f"\n== {title}")
    for name, pattern in patterns.items():
        per_file = [count_in(name, pattern, read(path)) for path in files]
        print(f"{sum(per_file):6} 件 / {sum(1 for n in per_file if n):4} ファイル  {name}")


def print_scale(styles):
    sizes = Counter()
    radii = Counter()
    for path in styles:
        text = read(path)
        sizes.update(float(m) for m in re.findall(r"font-size:\s*([0-9.]+)px", text))
        sizes.update(float(m) * 16 for m in re.findall(r"font-size:\s*([0-9.]+)rem", text))
        radii.update(re.findall(r"border-radius:\s*([0-9.]+(?:px|rem|%))", text))
    print("\n== font-size（px、rem は 16 倍）")
    for size in sorted(sizes):
        print(f"{size:6g} {sizes[size]}")
    under_14 = sum(n for size, n in sizes.items() if size < 14)
    under_12 = sum(n for size, n in sizes.items() if size < 12)
    at_most_10 = sum(n for size, n in sizes.items() if size <= 10)
    print(f"合計 {sum(sizes.values())}、14 未満 {under_14}、12 未満 {under_12}、10 以下 {at_most_10}")
    print("\n== border-radius の上位")
    for radius, n in radii.most_common(8):
        print(f"{radius:>8} {n}")


def print_hits(markup):
    print("\n== 残骸の候補（1 件ずつ実画面で確かめる）")
    for name, pattern in LEFTOVER_PATTERNS.items():
        regex = re.compile(pattern)
        hits = [f"{path}:{n}" for path in markup for n, line in code_lines(path) if regex.search(line)]
        rest = f"  他 {len(hits) - SHOWN_HITS} 件" if len(hits) > SHOWN_HITS else ""
        print(f"{len(hits):6} 件  {name}  {hits[:SHOWN_HITS]}{rest}")

    print("\n== 絵文字と文字記号（アイコンの代わりになっていないかを見る）")
    found = Counter()
    where = {}
    for path in markup:
        for n, line in code_lines(path):
            for char in EMOJI.findall(line):
                found[char] += 1
                where.setdefault(char, []).append(f"{path}:{n}")
    for char, n in found.most_common():
        print(f"{n:6} 件  {char}  {where[char][:4]}")


def main():
    parser = argparse.ArgumentParser(description="ソースの見た目の型と残骸の出現数を数える")
    parser.add_argument("roots", nargs="+", type=Path, help="ソースのディレクトリ")
    parser.add_argument("--exclude", action="append", default=[], help="除くディレクトリ名（開発用の画面など）")
    args = parser.parse_args()

    for root in args.roots:
        if not root.is_dir():
            parser.error(f"ディレクトリが無い: {root}")
    for name in args.exclude:
        if "/" in name:
            parser.error(f"--exclude にはパスではなくディレクトリ名を渡す: {name}")

    files = list(collect(args.roots, SKIPPED_DIRS | set(args.exclude)))
    styles = [path for path in files if path.suffix in STYLE_SUFFIXES]
    markup = [path for path in files if path.suffix in MARKUP_SUFFIXES]

    print(f"スタイル {len(styles)} ファイル、マークアップ {len(markup)} ファイル")
    print_counts("CSS", CSS_PATTERNS, styles)
    print_counts("Tailwind のクラス", TAILWIND_PATTERNS, markup)
    print_scale(styles)
    print_hits(markup)


if __name__ == "__main__":
    main()
