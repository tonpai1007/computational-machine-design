#!/usr/bin/env python3
"""
Render every ```mermaid block in a Markdown file to SVG (and optionally PNG).

Why this exists
---------------
The reports are Markdown, so Mermaid blocks render as source unless the viewer
supports Mermaid. This extracts each block, writes it to a ``.mmd`` file, and
shells out to ``@mermaid-js/mermaid-cli`` (``mmdc``) to produce images.

Chrome reuse
------------
``mmdc`` normally downloads its own Chromium via Puppeteer, which is slow and
often fails behind a proxy. This script passes ``PUPPETEER_EXECUTABLE_PATH`` so
mmdc uses a Chrome/Edge already on the machine. Override with
``--chrome <path>`` if needed.

Usage
-----
    # list blocks, write .mmd files, render to SVG next to the report
    python -m drafting.render_mermaid

    # PNG instead of SVG, custom output dir
    python -m drafting.render_mermaid --format png --outdir build/diagrams

    # render without writing the intermediate .mmd files
    python -m drafting.render_mermaid --no-keep-source

First run installs mermaid-cli into a cache dir (~/.cache/mdie-mermaid).
Pass --setup to force that install, or run:
    npx --yes @mermaid-js/mermaid-cli --version
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
from collections.abc import Sequence
from pathlib import Path

DEFAULT_REPORT = Path("Project/chair/chair_design_report.md")
CACHE_DIR = Path(os.environ.get("USERPROFILE", Path.home())) / ".cache" / "mdie-mermaid"

# Common Windows install locations for Chrome/Edge, in preference order.
CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
]

MERMAID_RE = re.compile(r"```mermaid\n(.*?)```", re.DOTALL)


def force_utf8() -> None:
    for s in (sys.stdout, sys.stderr):
        try:
            # reconfigure() exists only on TextIOWrapper, not every stream.
            reconfigure = getattr(s, "reconfigure", None)
            if reconfigure is not None:
                reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass


def find_chrome(explicit: str | None = None) -> str | None:
    """Locate a Chrome/Chromium binary for Puppeteer to reuse."""
    if explicit:
        return explicit if Path(explicit).exists() else None
    for c in CHROME_CANDIDATES:
        if Path(c).exists():
            return c
    return None


def ensure_mmdc(setup: bool = False) -> list[str]:
    """
    Return a command that runs mmdc. Prefer a local cache install, then any
    mmdc already on PATH, then npx (which may download on first use).
    """
    if setup:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        print(f"[setup] installing @mermaid-js/mermaid-cli into {CACHE_DIR} ...")
        subprocess.run(
            [
                "npm",
                "install",
                "@mermaid-js/mermaid-cli",
                "--no-audit",
                "--no-fund",
                "--prefix",
                str(CACHE_DIR),
            ],
            check=True,
        )
    local = CACHE_DIR / "node_modules" / ".bin" / ("mmdc.cmd" if os.name == "nt" else "mmdc")
    if local.exists():
        return [str(local)]
    found = shutil.which("mmdc")
    if found:
        return [found]
    # Fall back to npx (may download on first use). Resolve it explicitly since
    # a bare "npx" is not always on PATH for child processes on Windows.
    npx = shutil.which("npx.cmd" if os.name == "nt" else "npx")
    if npx:
        return [npx, "--yes", "@mermaid-js/mermaid-cli"]
    raise SystemExit(
        "mermaid-cli not found. Install it with:\n"
        "    npx --yes @mermaid-js/mermaid-cli --version\n"
        f"or run this script with --setup to install into {CACHE_DIR}"
    )


def extract_blocks(md_path: Path) -> list[tuple[int, str]]:
    """Return (1-based index, block source) for every mermaid block."""
    text = md_path.read_text(encoding="utf-8")
    blocks = [(i, m.group(1)) for i, m in enumerate(MERMAID_RE.finditer(text), 1)]
    if not blocks:
        print(f"no mermaid blocks found in {md_path}")
    return blocks


def slug(block: str, index: int) -> str:
    """Derive a stable, readable filename from the block's title or first label."""
    m = re.search(r'title\s+"([^"]+)"', block)
    if m:
        s = m.group(1)
    else:
        # flowcharts have no title; use the beam/support label instead.
        m2 = re.search(r'subgraph\s+\w+\["([^"]+)"\]', block)
        if not m2:
            m2 = re.search(r'^\s*(\w+)\["([^"]+)"\]', block, re.M)
            s = m2.group(2) if m2 else ""
        else:
            s = m2.group(1)
    # Keep letters/digits from any script plus Thai combining marks (vowels and
    # tone marks), which \w alone drops and which would corrupt the filename.
    s = unicodedata.normalize("NFC", s)
    s = "".join(ch for ch in s if ch.isalnum() or ch in "-_" or unicodedata.category(ch) == "Mn")
    s = re.sub(r"_+", "_", s).strip("_")
    return f"{index:02d}_{s[:48]}" if s else f"block{index:02d}"


def render_one(
    mmdc_cmd: list[str], src: Path, out: Path, fmt: str, chrome: str | None, scale: float, bg: str
) -> bool:
    env = dict(os.environ)
    if chrome:
        env["PUPPETEER_EXECUTABLE_PATH"] = chrome
    cmd = list(mmdc_cmd)
    cmd += [
        "-i",
        str(src),
        "-o",
        str(out),
        "-b",
        bg,
        "-s",
        str(scale),
    ]
    try:
        r = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=300)
    except FileNotFoundError:
        print(f"  [fail] command not found: {cmd[0]}")
        return False
    except subprocess.TimeoutExpired:
        print(f"  [fail] timeout rendering {src.name} (first npx run downloads Chromium)")
        return False
    if r.returncode != 0 or not out.exists():
        err = (r.stderr or r.stdout or "").strip().splitlines()
        print(f"  [fail] {src.name}: {' | '.join(err[:3])}")
        return False
    print(f"  [ok]   {out.name}  ({out.stat().st_size} bytes)")
    return True


def main(argv: Sequence[str] | None = None) -> int:
    force_utf8()
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "report",
        nargs="?",
        type=Path,
        default=DEFAULT_REPORT,
        help=f"Markdown file to scan (default: {DEFAULT_REPORT})",
    )
    ap.add_argument(
        "--format", choices=("svg", "png"), default="svg", help="output image format (default: svg)"
    )
    ap.add_argument(
        "--outdir",
        type=Path,
        default=None,
        help="output directory (default: <report_dir>/diagrams)",
    )
    ap.add_argument("--scale", type=float, default=2.0, help="render scale (default 2)")
    ap.add_argument("--bg", default="white", help="background color (default white)")
    ap.add_argument("--chrome", default=None, help="explicit Chrome/Chromium path")
    ap.add_argument(
        "--no-keep-source",
        action="store_true",
        help="delete the intermediate .mmd files after rendering",
    )
    ap.add_argument(
        "--setup", action="store_true", help="install mermaid-cli into the cache dir first"
    )
    ap.add_argument(
        "--list", action="store_true", help="list the mermaid blocks and exit without rendering"
    )
    args = ap.parse_args(argv)

    if not args.report.exists():
        print(f"report not found: {args.report}")
        return 2

    blocks = extract_blocks(args.report)
    if not blocks:
        return 0

    print(f"{len(blocks)} mermaid block(s) in {args.report}")
    for i, b in blocks:
        kind = re.search(r"(\w[\w-]*)", b.strip().splitlines()[0])
        print(f"  {i:02d}  {kind.group(1) if kind else '?':<14} {slug(b, i)}")

    if args.list:
        return 0

    chrome = find_chrome(args.chrome)
    if chrome:
        print(f"[chrome] using {chrome}")
    else:
        print("[chrome] none found; mmdc will try to download its own (may be slow)")

    mmdc_cmd = ensure_mmdc(args.setup)
    outdir = args.outdir or (args.report.parent / "diagrams")
    outdir.mkdir(parents=True, exist_ok=True)

    tmpdir = Path(tempfile.mkdtemp(prefix="mermaid_"))
    ok = fail = 0
    for i, b in blocks:
        name = slug(b, i)
        src = tmpdir / f"{name}.mmd"
        src.write_text(b, encoding="utf-8")
        out = outdir / f"{name}.{args.format}"
        print(f"[{i:02d}/{len(blocks)}] {name}")
        if render_one(mmdc_cmd, src, out, args.format, chrome, args.scale, args.bg):
            ok += 1
        else:
            fail += 1

    if not args.no_keep_source:
        print(f"intermediate .mmd kept in {tmpdir}")

    print(f"\ndone: {ok} ok, {fail} failed  ->  {outdir}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
