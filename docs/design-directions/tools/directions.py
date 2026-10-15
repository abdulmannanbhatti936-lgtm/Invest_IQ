"""Colour directions for the UI round (Step 1B): the token sets, their WCAG contrast ratios and a
colour-blindness check of gains vs losses. Run: python docs/design-directions/tools/directions.py
It writes directions.json and contrast.md next to the README; nothing in the app reads them.
"""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent

# Token names follow Design.md §2, plus the extras the UI round needs (tints, strong border,
# focus ring, chart series, landing gradient stops).
DIRECTIONS = {
    "truck-art": {
        "name": "Truck Art",
        "idea": "Magenta and marigold from Pakistani truck art on warm paper; loud on the landing page, quiet on data screens.",
        "primary_mode": "light",
        "light": {
            "primary": "#B0105C",
            "primary-dark": "#8C0A49",
            "primary-tint": "#FCE7F1",
            "secondary": "#F2A900",
            "success": "#0D6644",
            "success-tint": "#E3F4E8",
            "danger": "#CC3A10",
            "danger-tint": "#FEF4F0",
            "warning": "#8A5300",
            "warning-tint": "#FFF3D6",
            "neutral": "#5C5650",
            "background": "#FAF7F2",
            "surface": "#FFFFFF",
            "surface-sunken": "#F3EEE7",
            "border": "#E6DED3",
            "border-strong": "#8F857A",
            "text-primary": "#1E1A17",
            "text-secondary": "#5C5650",
            "text-inverse": "#FFFFFF",
            "focus-ring": "#B0105C",
            "chart-portfolio": "#B0105C",
            "chart-rules": "#0F7C86",
            "chart-benchmark": "#6F675F",
            "chart-forecast": "#B9650F",
            "gradient-1": "#B0105C",
            "gradient-2": "#F2A900",
            "gradient-3": "#13A3AE",
        },
        "dark": {
            "primary": "#FF6BAA",
            "primary-dark": "#FF8CBD",
            "primary-tint": "#3A1428",
            "secondary": "#FFC233",
            "success": "#86E6BA",
            "success-tint": "#123222",
            "danger": "#EE6236",
            "danger-tint": "#3A1A13",
            "warning": "#F8C24A",
            "warning-tint": "#33270C",
            "neutral": "#BEB3B9",
            "background": "#160E13",
            "surface": "#21171D",
            "surface-sunken": "#1B1218",
            "border": "#3A2C34",
            "border-strong": "#7D6C76",
            "text-primary": "#F6EFEA",
            "text-secondary": "#BEB3B9",
            "text-inverse": "#1A0A12",
            "focus-ring": "#FF6BAA",
            "chart-portfolio": "#FF6BAA",
            "chart-rules": "#3CCFD9",
            "chart-benchmark": "#A99DA4",
            "chart-forecast": "#FFB45E",
            "gradient-1": "#FF3D8B",
            "gradient-2": "#FFC233",
            "gradient-3": "#25C6D2",
        },
    },
    "indus-night": {
        "name": "Indus Night",
        "idea": "A deep river-teal night with a cyan current and a coral spark; dark by default, calm and focused.",
        "primary_mode": "dark",
        "light": {
            "primary": "#0A6E80",
            "primary-dark": "#08596A",
            "primary-tint": "#E0F3F6",
            "secondary": "#E8603F",
            "success": "#0D6644",
            "success-tint": "#E2F4E8",
            "danger": "#CC3A10",
            "danger-tint": "#FEF4F0",
            "warning": "#875700",
            "warning-tint": "#FFF3D9",
            "neutral": "#4B6168",
            "background": "#F3F7F8",
            "surface": "#FFFFFF",
            "surface-sunken": "#EAF1F2",
            "border": "#D4E1E3",
            "border-strong": "#7E9399",
            "text-primary": "#0B1D23",
            "text-secondary": "#4B6168",
            "text-inverse": "#FFFFFF",
            "focus-ring": "#0A6E80",
            "chart-portfolio": "#0A6E80",
            "chart-rules": "#B45309",
            "chart-benchmark": "#6B7F85",
            "chart-forecast": "#E8603F",
            "gradient-1": "#0A8EA3",
            "gradient-2": "#2CC5D8",
            "gradient-3": "#FF8466",
        },
        "dark": {
            "primary": "#33C9DB",
            "primary-dark": "#5FD6E4",
            "primary-tint": "#0F3640",
            "secondary": "#FF8466",
            "success": "#86E6BA",
            "success-tint": "#113524",
            "danger": "#EE6236",
            "danger-tint": "#3D1A1C",
            "warning": "#F5BC4A",
            "warning-tint": "#34290F",
            "neutral": "#9DB6BC",
            "background": "#07131A",
            "surface": "#0E1F27",
            "surface-sunken": "#0A1920",
            "border": "#1F3A44",
            "border-strong": "#5E7D86",
            "text-primary": "#E8F3F4",
            "text-secondary": "#9DB6BC",
            "text-inverse": "#04161B",
            "focus-ring": "#33C9DB",
            "chart-portfolio": "#33C9DB",
            "chart-rules": "#F5BC4A",
            "chart-benchmark": "#8AA3AA",
            "chart-forecast": "#FF8466",
            "gradient-1": "#33C9DB",
            "gradient-2": "#7BE0C3",
            "gradient-3": "#FF8466",
        },
    },
    "ink-lime": {
        "name": "Ink & Lime",
        "idea": "Near-black ink on clean paper with one electric lime accent; editorial, confident, almost no colour on data screens.",
        "primary_mode": "light",
        "light": {
            "primary": "#141413",
            "primary-dark": "#33332F",
            "primary-tint": "#EEF9CC",
            "secondary": "#C8F03C",
            "success": "#0D6644",
            "success-tint": "#E2F3E7",
            "danger": "#CC3A10",
            "danger-tint": "#FEF4F0",
            "warning": "#875600",
            "warning-tint": "#FFF2D6",
            "neutral": "#5A5A55",
            "background": "#F5F5F1",
            "surface": "#FFFFFF",
            "surface-sunken": "#EFEFEA",
            "border": "#E2E2DC",
            "border-strong": "#85857E",
            "text-primary": "#141413",
            "text-secondary": "#5A5A55",
            "text-inverse": "#FFFFFF",
            "focus-ring": "#141413",
            "chart-portfolio": "#141413",
            "chart-rules": "#0E7C66",
            "chart-benchmark": "#8A8A83",
            "chart-forecast": "#5F7D00",
            "gradient-1": "#C8F03C",
            "gradient-2": "#4FE0A6",
            "gradient-3": "#E8F7FF",
        },
        "dark": {
            "primary": "#C8F03C",
            "primary-dark": "#D8F772",
            "primary-tint": "#2A3310",
            "secondary": "#4FE0A6",
            "success": "#86E6BA",
            "success-tint": "#123321",
            "danger": "#EE6236",
            "danger-tint": "#3D171D",
            "warning": "#F2C14E",
            "warning-tint": "#33290E",
            "neutral": "#A6A69F",
            "background": "#0D0D0C",
            "surface": "#181816",
            "surface-sunken": "#121211",
            "border": "#2D2D2A",
            "border-strong": "#6E6E68",
            "text-primary": "#F2F2EE",
            "text-secondary": "#A6A69F",
            "text-inverse": "#141413",
            "focus-ring": "#C8F03C",
            "chart-portfolio": "#C8F03C",
            "chart-rules": "#4FE0A6",
            "chart-benchmark": "#8F8F88",
            "chart-forecast": "#F2C14E",
            "gradient-1": "#C8F03C",
            "gradient-2": "#4FE0A6",
            "gradient-3": "#E8F7FF",
        },
    },
}

# (foreground, background, minimum): 4.5 for text, 3.0 for non-text UI (WCAG 1.4.11) and for
# large display figures. Every pair the components actually draw.
PAIRS = [
    ("text-primary", "background", 4.5),
    ("text-primary", "surface", 4.5),
    ("text-primary", "surface-sunken", 4.5),
    ("text-secondary", "background", 4.5),
    ("text-secondary", "surface", 4.5),
    ("text-secondary", "surface-sunken", 4.5),
    ("text-inverse", "primary", 4.5),
    ("text-inverse", "primary-dark", 4.5),
    ("primary", "surface", 4.5),
    ("primary", "background", 4.5),
    ("primary", "primary-tint", 4.5),
    ("success", "surface", 4.5),
    ("success", "success-tint", 4.5),
    ("danger", "surface", 4.5),
    ("danger", "danger-tint", 4.5),
    ("warning", "surface", 4.5),
    ("warning", "warning-tint", 4.5),
    ("text-primary", "warning-tint", 4.5),
    ("neutral", "surface", 4.5),
    ("border-strong", "surface", 3.0),
    ("focus-ring", "surface", 3.0),
    ("focus-ring", "background", 3.0),
    ("chart-portfolio", "surface", 3.0),
    ("chart-rules", "surface", 3.0),
    ("chart-benchmark", "surface", 3.0),
    ("chart-forecast", "surface", 3.0),
]


def _lin(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def rgb(hex_: str) -> tuple[float, float, float]:
    h = hex_.lstrip("#")
    return tuple(int(h[i : i + 2], 16) / 255 for i in (0, 2, 4))


def luminance(hex_: str) -> float:
    r, g, b = (_lin(c) for c in rgb(hex_))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


# Machado, Oliveira & Fernandes (2009) full-severity matrices, applied in linear RGB
CVD = {
    "protanopia": [
        [0.152286, 1.052583, -0.204868],
        [0.114503, 0.786281, 0.099216],
        [-0.003882, -0.048116, 1.051998],
    ],
    "deuteranopia": [
        [0.367322, 0.860646, -0.227968],
        [0.280085, 0.672501, 0.047413],
        [-0.011820, 0.042940, 0.968881],
    ],
    "tritanopia": [
        [1.255528, -0.076749, -0.178779],
        [-0.078411, 0.930809, 0.147602],
        [0.004733, 0.691367, 0.303900],
    ],
}


def _lab(lin_rgb: tuple[float, float, float]) -> tuple[float, float, float]:
    r, g, b = (min(max(c, 0.0), 1.0) for c in lin_rgb)
    x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883

    def f(t: float) -> float:
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116

    return 116 * f(y) - 16, 500 * (f(x) - f(y)), 200 * (f(y) - f(z))


def delta_e(a: str, b: str, kind: str | None) -> float:
    def sim(h: str):
        lin = tuple(_lin(c) for c in rgb(h))
        if kind is None:
            return lin
        m = CVD[kind]
        return tuple(sum(m[i][j] * lin[j] for j in range(3)) for i in range(3))

    la, lb = _lab(sim(a)), _lab(sim(b))
    return sum((x - y) ** 2 for x, y in zip(la, lb)) ** 0.5


def report() -> str:
    lines = [
        "# Contrast and colour-blindness check",
        "",
        "Generated by `tools/directions.py`. WCAG 2.2 contrast ratio; minimum 4.5:1 for text and",
        "3:1 for input borders, focus rings and chart lines (WCAG 1.4.11). Colour-blind check:",
        "gain vs loss colour difference (CIE76 ΔE) after simulating full protanopia, deuteranopia",
        "and tritanopia (Machado 2009). Above about 20 the two read as clearly different colours;",
        "▲/▼/— is always shown with them anyway (Design §5, §6.3).",
        "",
    ]
    failures = 0
    for d in DIRECTIONS.values():
        for mode in ("light", "dark"):
            t = d[mode]
            primary = " (primary)" if d["primary_mode"] == mode else " (fallback)"
            lines += [
                f"## {d['name']}, {mode}{primary}",
                "",
                "| Pair | Ratio | Min | |",
                "|---|---:|---:|---|",
            ]
            for fg, bg, minimum in PAIRS:
                r = contrast(t[fg], t[bg])
                ok = r >= minimum
                failures += not ok
                lines.append(
                    f"| `{fg}` on `{bg}` | {r:.2f} | {minimum} | {'pass' if ok else 'FAIL'} |"
                )
            lines += [
                "",
                "| Gain vs loss ΔE | Normal | Protanopia | Deuteranopia | Tritanopia |",
                "|---|---:|---:|---:|---:|",
            ]
            row = [
                f"{delta_e(t['success'], t['danger'], k):.1f}"
                for k in (None, "protanopia", "deuteranopia", "tritanopia")
            ]
            lines.append(f"| `success` vs `danger` | {' | '.join(row)} |")
            row = [
                f"{delta_e(t['chart-portfolio'], t['chart-benchmark'], k):.1f}"
                for k in (None, "protanopia", "deuteranopia", "tritanopia")
            ]
            lines.append(f"| chart portfolio vs benchmark | {' | '.join(row)} |")
            lines.append("")
    lines.insert(8, f"**Failures: {failures}.**\n")
    return "\n".join(lines)


if __name__ == "__main__":
    (HERE / "directions.json").write_text(
        json.dumps(DIRECTIONS, indent=2) + "\n", encoding="utf-8"
    )
    (HERE / "contrast.md").write_text(report() + "\n", encoding="utf-8")
    print(report().split("\n")[8])
