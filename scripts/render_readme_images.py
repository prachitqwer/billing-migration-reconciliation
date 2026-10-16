"""Render the pictures used on the README from the run results.

    python scripts/render_readme_images.py

Needs matplotlib. The workbook picture also needs LibreOffice (soffice) and
pdftoppm on the PATH; it is skipped if they are missing.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
IMG = ROOT / "docs" / "images"

LEVELS = [("L1", "L1 Completeness"), ("L2", "L2 Control totals"), ("L3", "L3 Field level"),
          ("RI", "Integrity"), ("L4", "L4 Finance views")]
THEMES = {
    "light": {"surface": "#fcfcfb", "text": "#0b0b0b", "muted": "#52514e", "grid": "#e4e3df",
              "mock1": "#eb6834", "mock2": "#2a78d6"},
    "dark": {"surface": "#1a1a19", "text": "#f0efec", "muted": "#c3c2b7", "grid": "#3a3936",
             "mock1": "#d95926", "mock2": "#3987e5"},
}


def checks_chart(theme: str) -> Path:
    t = THEMES[theme]
    m1 = json.loads((ROOT / "results" / "mock1" / "summary.json").read_text())
    m2 = json.loads((ROOT / "results" / "mock2" / "summary.json").read_text())
    fig, ax = plt.subplots(figsize=(8.6, 4.2), dpi=150)
    fig.patch.set_facecolor(t["surface"])
    ax.set_facecolor(t["surface"])
    h = 0.32
    for i, (key, label) in enumerate(LEVELS):
        t1, t2 = m1["by_level"][key]["total"], m2["by_level"][key]["total"]
        y = len(LEVELS) - 1 - i
        ax.barh(y + h / 2 + 0.02, t1, height=h, color=t["grid"], zorder=1)
        ax.barh(y - h / 2 - 0.02, t2, height=h, color=t["grid"], zorder=1)
        p1, p2 = m1["by_level"][key]["passed"], m2["by_level"][key]["passed"]
        ax.barh(y + h / 2 + 0.02, p1, height=h, color=t["mock1"], zorder=2)
        ax.barh(y - h / 2 - 0.02, p2, height=h, color=t["mock2"], zorder=2)
        ax.text(t1 + 0.25, y + h / 2 + 0.02, f"{p1} of {t1}", va="center", fontsize=9, color=t["muted"])
        ax.text(t2 + 0.25, y - h / 2 - 0.02, f"{p2} of {t2}", va="center", fontsize=9, color=t["text"])
    ax.set_yticks(range(len(LEVELS)))
    ax.set_yticklabels([lbl for _, lbl in reversed(LEVELS)], fontsize=10, color=t["text"])
    ax.set_xlim(0, 13.5)
    ax.set_xticks([])
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(left=False)
    fig.text(0.02, 0.94, "Reconciliation checks passed, by level", fontsize=13, weight="bold", color=t["text"])
    fig.text(0.02, 0.875, f"Mock 1, build 1.0: {m1['checks_passed']} of {m1['checks_total']}      "
                          f"Mock 2, build 1.1: {m2['checks_passed']} of {m2['checks_total']}",
             fontsize=10, color=t["muted"])
    handles = [plt.Rectangle((0, 0), 1, 1, color=t["mock1"]), plt.Rectangle((0, 0), 1, 1, color=t["mock2"]),
               plt.Rectangle((0, 0), 1, 1, color=t["grid"])]
    leg = fig.legend(handles, ["Mock 1 passed", "Mock 2 passed", "Checks at that level"], loc="lower left",
                     bbox_to_anchor=(0.02, 0.0), ncol=3, frameon=False, fontsize=9)
    for txt in leg.get_texts():
        txt.set_color(t["text"])
    fig.subplots_adjust(left=0.2, right=0.97, top=0.82, bottom=0.14)
    IMG.mkdir(parents=True, exist_ok=True)
    out = IMG / f"checks_by_level{'' if theme == 'light' else '_dark'}.png"
    fig.savefig(out, facecolor=t["surface"])
    plt.close(fig)
    return out


def workbook_picture() -> Path | None:
    soffice, pdftoppm = shutil.which("soffice"), shutil.which("pdftoppm")
    if not soffice or not pdftoppm:
        print("soffice or pdftoppm not found; workbook picture skipped")
        return None
    from PIL import Image

    src = ROOT / "results" / "mock2" / "Northstar_BPM_Reconciliation_Mock2.xlsx"
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run([soffice, "--headless", "--convert-to", "pdf", "--outdir", tmp, str(src)],
                       check=True, capture_output=True, timeout=180)
        pdf = Path(tmp) / (src.stem + ".pdf")
        subprocess.run([pdftoppm, "-f", "1", "-l", "1", "-r", "140", "-png", str(pdf), str(Path(tmp) / "p")],
                       check=True, capture_output=True)
        page = next(Path(tmp).glob("p*.png"))
        img = Image.open(page).convert("RGB")
        w, h = img.size
        img = img.crop((int(w * 0.055), int(h * 0.11), int(w * 0.93), int(h * 0.80)))
        out = IMG / "workbook_mock2_summary.png"
        img.save(out, optimize=True)
    return out


def main() -> None:
    for theme in THEMES:
        print(checks_chart(theme).relative_to(ROOT))
    pic = workbook_picture()
    if pic:
        print(pic.relative_to(ROOT))


if __name__ == "__main__":
    main()
