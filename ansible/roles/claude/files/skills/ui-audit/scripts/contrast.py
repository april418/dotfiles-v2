"""色の組み合わせの WCAG コントラスト比を表にする。

    python3 contrast.py --fg ink=#1a1a18 muted=#7a7a72 --bg paper=#fbfbf9 "#ffffff"

色は #rgb、#rrggbb、rgb(r g b)、oklch(l c h) で書く。名前=値 の形にすると表に名前が出る。
AA の基準は本文で 4.5:1、大きな文字（24px 以上か、18.66px 以上の太字）で 3:1 である。
https://www.w3.org/TR/WCAG22/#contrast-minimum
"""

import argparse
import math
import re


def from_oklch(lightness, chroma, hue):
    a = chroma * math.cos(math.radians(hue))
    b = chroma * math.sin(math.radians(hue))
    l_ = (lightness + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m_ = (lightness - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s_ = (lightness - 0.0894841775 * a - 1.2914855480 * b) ** 3
    linear = (
        4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_,
        -1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_,
        -0.0041960863 * l_ - 0.7034186147 * m_ + 1.7076147010 * s_,
    )

    def encode(x):
        x = max(0.0, min(1.0, x))
        return 12.92 * x if x <= 0.0031308 else 1.055 * x ** (1 / 2.4) - 0.055

    return tuple(encode(x) for x in linear)


def parse(color):
    text = color.strip().lower()
    body = text.partition("(")[2]
    numbers = [float(n) for n in re.findall(r"-?\d*\.?\d+", body)]
    if re.fullmatch(r"#[0-9a-f]{4}|#[0-9a-f]{8}", text) or "/" in body or text.startswith("rgba(") or len(numbers) > 3:
        raise SystemExit(f"透明度のある色は読めない。背景に合成してから渡す: {color}")
    if re.fullmatch(r"#[0-9a-f]{3}|#[0-9a-f]{6}", text):
        digits = text[1:]
        if len(digits) == 3:
            digits = "".join(c * 2 for c in digits)
        return tuple(int(digits[i : i + 2], 16) / 255 for i in (0, 2, 4))
    if text.startswith("rgb(") and len(numbers) == 3:
        return tuple(n / (100 if "%" in body else 255) for n in numbers)
    if text.startswith("oklch(") and len(numbers) == 3:
        lightness = numbers[0] / 100 if "%" in body else numbers[0]
        return from_oklch(lightness, numbers[1], numbers[2])
    raise SystemExit(f"色として読めない: {color}")


def luminance(rgb):
    r, g, b = (c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ratio(a, b):
    high, low = sorted((luminance(a), luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def named(value):
    name, separator, color = value.partition("=")
    return (name, color) if separator else (value, value)


def main():
    parser = argparse.ArgumentParser(description="色の組み合わせの WCAG コントラスト比を表にする")
    parser.add_argument("--fg", nargs="+", type=named, required=True, help="文字の色")
    parser.add_argument("--bg", nargs="+", type=named, required=True, help="背景の色")
    args = parser.parse_args()

    for bg_name, bg in args.bg:
        print(f"== {bg_name}")
        for fg_name, fg in args.fg:
            value = ratio(parse(fg), parse(bg))
            verdict = "本文も可" if value >= 4.5 else "大きな文字のみ可" if value >= 3 else "不足"
            print(f"{value:6.2f}  {verdict:10}  {fg_name}")


if __name__ == "__main__":
    main()
