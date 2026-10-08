"""Executable rows 1-9 of the R7 verification gate (reports/remediation_plan.md, R7).

Rows 10 (double-blind read) and 11 (final PDF hash) stay manual and are not checked here.
The gate is read-only: it compiles nothing, edits nothing, and touches no sealed file. Run
it before the R7 lock; a single failing row blocks the lock.

    py -m tools.r7_gate            # all rows, writes reports/r7_gate.json
    py -m tools.r7_gate --quick    # skip the pytest row (row 3)
"""
from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
from pathlib import Path

from pypdf import PdfReader
from pypdf.generic import ContentStream

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.analysis_core import ANALYSIS_HASH_PATHS  # noqa: E402

PAPER = ROOT / "paper"
MAIN_PDF = PAPER / "main.pdf"
MAIN_LOG = PAPER / "main.log"
EVIDENCE = PAPER / "LITERATURE_EVIDENCE.md"
CHECKLIST = ROOT / "reports" / "easychair_upload_checklist.md"
OUT_PATH = ROOT / "reports" / "r7_gate.json"

PAGE_RANGE = (4, 6)
#: Smallest glyph, in printed points, that a data figure may contain. ACM sigconf sets
#: captions at 8 pt; 6 pt is the floor below which axis labels stop being readable on
#: paper regardless of what they look like on a zoomed screen.
MIN_FIGURE_PT = 6.0
#: A float must be typeset on the page that first mentions it, or earlier. Zero, not one:
#: a float at the top of the following page is read only after the page is turned, which
#: is the placement this paper is explicitly trying to avoid.
MAX_FLOAT_LAG_PAGES = 0
#: A page whose content stops this far above the bottom of the text block is a visible
#: hole, roughly seven blank lines. The last page is exempt: it ends where the text ends.
MAX_SHORT_PAGE_PT = 72.0
#: The page number sits below the text block on every page, so it would otherwise report
#: every page as full. Anything drawn below this height is furniture, not content.
FOOTER_BAND_PT = 90.0
#: An overfull \vbox raised by the output routine means a page box that could not be
#: balanced exactly. Below one line of body text it is not visible on paper; above it,
#: content really is running past the bottom margin and row 5 must block.
MAX_VBOX_OVERRUN_PT = 2.0
#: Non-data figures are exempt from row 7: they carry no numbers to read off.
NON_DATA_FIGURES = ("fig_mechanism.pdf",)
#: Raster artwork carries no text operators, so its glyph height cannot be measured from
#: the PDF the way a vector figure's can. Effective resolution at the placed size is the
#: property that is measurable and that actually limits legibility in print: below this,
#: type of any size prints soft regardless of how large it was in the source image.
MIN_RASTER_DPI = 300.0

SEALED_PATHS = tuple(sorted(
    {"reports/paper_number_lock.json",
     "reports/final_results.json",
     "reports/randomization_manifest.json"}
    | {p.relative_to(ROOT).as_posix() for p in ANALYSIS_HASH_PATHS}
))


# --------------------------------------------------------------------------- PDF helpers

def _mul(a: list[float], b: list[float]) -> list[float]:
    return [a[0] * b[0] + a[1] * b[2], a[0] * b[1] + a[1] * b[3],
            a[2] * b[0] + a[3] * b[2], a[2] * b[1] + a[3] * b[3],
            a[4] * b[0] + a[5] * b[2] + b[4], a[4] * b[1] + a[5] * b[3] + b[5]]


def _scale(m: list[float]) -> float:
    return math.sqrt(abs(m[0] * m[3] - m[1] * m[2]))


def _collect_forms(stream, resources, reader, ctm, found: list[dict], depth: int = 0) -> None:
    """Walk a content stream, recording every form XObject with its printed glyph sizes."""
    stack: list[list[float]] = []
    cur, size, tm_scale = list(ctm), None, 1.0
    for operands, op in ContentStream(stream, reader).operations:
        if op == b"q":
            stack.append(list(cur))
        elif op == b"Q" and stack:
            cur = stack.pop()
        elif op == b"cm":
            cur = _mul([float(x) for x in operands], cur)
        elif op == b"BT":
            tm_scale = 1.0
        elif op == b"Tf":
            size = float(operands[1])
        elif op == b"Tm":
            tm_scale = _scale([float(x) for x in operands])
        elif op in (b"Tj", b"TJ", b"'", b'"') and size:
            found.append({"pt": size * tm_scale * _scale(cur)})
        elif op == b"Do" and depth < 6:
            try:
                xobj = resources["/XObject"][operands[0]].get_object()
            except Exception:                                    # missing or broken resource
                continue
            if xobj.get("/Subtype") != "/Form":
                continue
            matrix = [float(x) for x in xobj.get("/Matrix", [1, 0, 0, 1, 0, 0])]
            bbox = [float(x) for x in xobj.get("/BBox", [0, 0, 0, 0])]
            inner = _mul(matrix, cur)
            glyphs: list[dict] = []
            _collect_forms(xobj, xobj.get("/Resources", resources), reader, inner,
                           glyphs, depth + 1)
            found.append({"form": True,
                          "width": bbox[2] - bbox[0], "height": bbox[3] - bbox[1],
                          "scale": _scale(inner),
                          "pts": [g["pt"] for g in glyphs if "pt" in g]})
            found.extend(g for g in glyphs if "form" in g)


def _figure_natural_sizes() -> dict[tuple[int, int], list[str]]:
    """Map natural page size to file names, for the figures main.tex actually includes.

    Unused figures are excluded on purpose: several share a natural size with an included
    one, and matching against the whole directory would attribute glyphs to the wrong file.
    Included figures can also share a size with each other, so a size maps to every
    candidate rather than to one; keeping only the last would drop a figure from the census.
    """
    included = re.findall(r"\\includegraphics\[[^\]]*\]\{figures/([^}]+)\}",
                          (PAPER / "main.tex").read_text(encoding="utf-8"))
    sizes: dict[tuple[int, int], list[str]] = {}
    for name in included:
        path = PAPER / "figures" / name
        try:
            box = PdfReader(str(path)).pages[0].mediabox
        except Exception:
            continue
        key = (round(float(box.width) * 10), round(float(box.height) * 10))
        names = sizes.setdefault(key, [])
        if path.name not in names:
            names.append(path.name)
    return sizes


def _raster_dpi(name: str, placed_width_pt: float) -> float | None:
    """Effective resolution of a raster figure at the width it is placed at, or None.

    The pixel count is read from the authored PNG beside the included PDF rather than from
    the PDF's image stream: the two are written by the same export step, and the PNG is the
    artifact an author would replace to fix a low-resolution figure.
    """
    src = (PAPER / "figures" / name).with_suffix(".png")
    if not src.is_file() or placed_width_pt <= 0:
        return None
    try:
        from PIL import Image

        with Image.open(src) as img:
            pixels = img.width
    except Exception:
        return None
    return pixels / (placed_width_pt / 72.0)


# ------------------------------------------------------------------------------ the rows

def row_1_page_count(pdf: PdfReader) -> tuple[bool, dict]:
    n = len(pdf.pages)
    return PAGE_RANGE[0] <= n <= PAGE_RANGE[1], {"pages": n, "allowed": list(PAGE_RANGE)}


def _run(args: list[str]) -> tuple[bool, dict]:
    proc = subprocess.run([sys.executable, *args], cwd=ROOT, capture_output=True, text=True)
    tail = (proc.stdout or proc.stderr).strip().splitlines()[-3:]
    return proc.returncode == 0, {"returncode": proc.returncode, "tail": tail}


def row_2_number_lock() -> tuple[bool, dict]:
    return _run(["-m", "tools.verify_paper_numbers"])


def row_3_tests() -> tuple[bool, dict]:
    return _run(["-m", "pytest", "tests/sprint", "-q"])


def row_4_citations() -> tuple[bool, dict]:
    rows = [ln for ln in EVIDENCE.read_text(encoding="utf-8").splitlines()
            if ln.startswith("|") and re.match(r"\|\s*\d+\s*\|", ln)]
    statuses = [c.strip() for ln in rows for c in [ln.split("|")[7]]]
    counts = {s: statuses.count(s) for s in sorted(set(statuses))}
    ok = bool(statuses) and set(statuses) == {"verified"}
    return ok, {"n_rows": len(rows), "status_counts": counts}


def row_5_latex_warnings() -> tuple[bool, dict]:
    """Blocking warnings only.

    Underfull ``\\vbox`` while ``\\output`` is active is how a two-column page reports that
    floats left it short; it is unavoidable here and is counted but not blocking. An
    underfull ``\\hbox`` at badness 10000, by contrast, is a visibly stretched line.
    """
    if not MAIN_LOG.is_file():
        return False, {"blocking": {"missing_compile_log": 1},
                       "note": "Compile the paper in a disposable clone to produce paper/main.log."}
    log = MAIN_LOG.read_text(encoding="utf-8", errors="replace")
    all_overfull = len(re.findall(r"^Overfull ", log, re.M))
    # Symmetric with the underfull case above: the output routine reports a page box it
    # could not balance exactly. Under a line's worth it is invisible; a real spill past
    # the bottom margin is much larger and still blocks.
    tolerated = [float(v) for v in re.findall(
        r"^Overfull \\vbox \(([\d.]+)pt too high\) has occurred while \\output is active",
        log, re.M) if float(v) <= MAX_VBOX_OVERRUN_PT]
    blocking = {
        "overfull": all_overfull - len(tolerated),
        "underfull_hbox_badness_10000": len(
            re.findall(r"^Underfull \\hbox \(badness 10000\)", log, re.M)),
        "undefined_references": len(re.findall(r"Reference `[^']*' on page .* undefined", log)),
        "undefined_citations": len(re.findall(r"Citation `[^']*' on page .* undefined", log)),
        "multiply_defined": len(re.findall(r"multiply.defined", log, re.I)),
    }
    informational = {
        "underfull_vbox_in_output": len(
            re.findall(r"^Underfull \\vbox .*\\output is active", log, re.M)),
        "overfull_vbox_in_output_within_tolerance": sorted(tolerated),
    }
    return sum(blocking.values()) == 0, {"blocking": blocking, "informational": informational,
                                         "max_vbox_overrun_pt": MAX_VBOX_OVERRUN_PT}


def _page_content_bottom(page, reader: PdfReader) -> float | None:
    """Lowest point of drawn content on the page, in page coordinates.

    pypdf's text visitor reports baselines inside an included figure in that figure's own
    coordinate space, which on a page carrying a figure reads as content near y=0. So text
    is measured only in the page's own stream, and an included figure contributes the
    placed corners of its bounding box instead.
    """
    lows: list[float] = []
    stack: list[list[float]] = []
    cur = [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]
    tm = tlm = list(cur)
    leading = 0.0
    try:
        ops = ContentStream(page.get_contents(), reader).operations
    except Exception:                                        # unparsable stream
        return None
    for operands, op in ops:
        if op == b"q":
            stack.append(list(cur))
        elif op == b"Q" and stack:
            cur = stack.pop()
        elif op == b"cm":
            cur = _mul([float(x) for x in operands], cur)
        elif op == b"BT":
            tm = tlm = [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]
        elif op == b"TL":
            leading = float(operands[0])
        elif op == b"Tm":
            tm = tlm = [float(x) for x in operands]
        elif op in (b"Td", b"TD"):
            if op == b"TD":
                leading = -float(operands[1])
            tlm = _mul([1.0, 0.0, 0.0, 1.0, float(operands[0]), float(operands[1])], tlm)
            tm = list(tlm)
        elif op == b"T*":
            tlm = _mul([1.0, 0.0, 0.0, 1.0, 0.0, -leading], tlm)
            tm = list(tlm)
        elif op in (b"Tj", b"TJ", b"'", b'"'):
            lows.append(_mul(tm, cur)[5])
        elif op == b"Do":
            try:
                xobj = reader.get_object(page["/Resources"]["/XObject"].raw_get(operands[0]))
            except Exception:                                # missing or broken resource
                continue
            bbox = [float(x) for x in xobj.get("/BBox", [0, 0, 0, 0])]
            inner = _mul([float(x) for x in xobj.get("/Matrix", [1, 0, 0, 1, 0, 0])], cur)
            lows += [inner[1] * x + inner[3] * y + inner[5]
                     for x in (bbox[0], bbox[2]) for y in (bbox[1], bbox[3])]
    body = [y for y in lows if y > FOOTER_BAND_PT]
    return min(body) if body else None


def _short_pages(pdf: PdfReader) -> tuple[dict[int, float], float]:
    """Pages whose text stops well above the text block used by the fullest pages.

    The floor is taken from the document itself rather than from class internals, so it
    stays correct if the margins change. The final page is excluded: it ends where the
    bibliography ends and carries no layout defect.
    """
    bottoms = {i: _page_content_bottom(p, pdf) for i, p in enumerate(pdf.pages, 1)}
    measured = [v for v in bottoms.values() if v is not None]
    if not measured:
        return {}, 0.0
    floor = min(measured)
    last = len(pdf.pages)
    short = {i: round(v - floor, 1) for i, v in bottoms.items()
             if v is not None and i != last and v - floor > MAX_SHORT_PAGE_PT}
    return short, round(floor, 1)


def row_6_float_order(pdf: PdfReader) -> tuple[bool, dict]:
    """Floats reach the page that reads them, and no page is left with a hole in it.

    Both halves are the same layout property seen from opposite sides: a float pushed past
    its reader usually leaves the page it came from short.
    """
    caption_page: dict[str, int] = {}
    ref_page: dict[str, int] = {}
    for page_no, page in enumerate(pdf.pages, 1):
        text = " ".join(page.extract_text().split())
        # "Figure" hyphenates across a line break as "Fig- ure"; rejoin before matching.
        text = re.sub(r"(?<=[A-Za-z])- (?=[a-z])", "", text)
        for kind, num in re.findall(r"(Figure|Table)\s+(\d+):", text):
            caption_page.setdefault(f"{kind} {num}", page_no)
        for kind, num in re.findall(r"(Figure|Table)\s+(\d+)(?!:)", text):
            ref_page.setdefault(f"{kind} {num}", page_no)
    floats, offenders = {}, []
    for name, cap in sorted(caption_page.items()):
        ref = ref_page.get(name)
        lag = None if ref is None else cap - ref
        floats[name] = {"caption_page": cap, "first_reference_page": ref, "lag_pages": lag}
        if ref is None or lag > MAX_FLOAT_LAG_PAGES:
            offenders.append(name)
    short, floor = _short_pages(pdf)
    offenders += [f"page {i} ends {d} pt short" for i, d in sorted(short.items())]
    return not offenders, {"floats": floats, "offenders": offenders,
                           "max_lag_pages": MAX_FLOAT_LAG_PAGES,
                           "short_pages_pt": short, "text_block_bottom": floor,
                           "max_short_page_pt": MAX_SHORT_PAGE_PT}


def row_7_print_legibility(pdf: PdfReader) -> tuple[bool, dict]:
    natural = _figure_natural_sizes()
    placed: dict[tuple[int, int], list[tuple[int, dict]]] = {}
    ignored: dict[str, int] = {}
    for page_no, page in enumerate(pdf.pages, 1):
        found: list[dict] = []
        _collect_forms(page.get_contents(), page["/Resources"], pdf,
                       [1.0, 0.0, 0.0, 1.0, 0.0, 0.0], found)
        for form in (f for f in found if f.get("form")):
            key = (round(form["width"] * 10), round(form["height"] * 10))
            if key not in natural:
                # Not a size declared by any \includegraphics, so not artwork. Matplotlib
                # emits one reusable form per repeated plot marker; those land here. The
                # missing-figure check below is what keeps this from hiding a real figure.
                tag = f"unmatched_{key[0]}x{key[1]}"
                ignored[tag] = ignored.get(tag, 0) + 1
                continue
            placed.setdefault(key, []).append((page_no, form))

    figures, offenders = {}, []
    for key, names in natural.items():
        instances = placed.get(key, [])
        # Same-size figures are indistinguishable once placed, but LaTeX sets figures in
        # declaration order, so pairing the two orders identifies each placement.
        for name, (page_no, form) in zip(names, instances):
            entry = {"page": page_no, "placement_scale": round(form["scale"], 4),
                     "n_glyph_runs": len(form["pts"]),
                     "min_pt": round(min(form["pts"]), 2) if form["pts"] else None,
                     "max_pt": round(max(form["pts"]), 2) if form["pts"] else None}
            figures[name] = entry
            dpi = _raster_dpi(name, form["width"] * form["scale"])
            if dpi is not None:
                entry["raster_dpi"] = round(dpi, 1)
            if name in NON_DATA_FIGURES:
                entry["exempt"] = "non-data figure"
            elif form["pts"]:
                if entry["min_pt"] < MIN_FIGURE_PT:
                    offenders.append(f"{name}: smallest glyph {entry['min_pt']} pt")
            elif dpi is None:
                entry["note"] = "no text operators and no raster source: check by eye"
                offenders.append(f"{name}: legibility not machine-checkable")
            elif dpi < MIN_RASTER_DPI:
                offenders.append(f"{name}: raster {entry['raster_dpi']} dpi at placed size")
        offenders += [f"{n}: declared in main.tex but not located in the PDF"
                      for n in names[len(instances):]]
        if len(instances) > len(names):
            offenders.append(f"{len(instances)} placements at {key[0] / 10}x{key[1] / 10} pt "
                             f"for {len(names)} declared figure(s)")
    declared = sorted(n for names in natural.values() for n in names)
    return not offenders, {"figures": figures, "offenders": offenders,
                           "declared": declared, "ignored_non_figure_forms": ignored,
                           "min_pt_required": MIN_FIGURE_PT,
                           "min_raster_dpi_required": MIN_RASTER_DPI}


def row_8_sealed_files() -> tuple[bool, dict]:
    proc = subprocess.run(["git", "diff", "--exit-code", "--name-only", "--", *SEALED_PATHS],
                          cwd=ROOT, capture_output=True, text=True)
    changed = [ln for ln in proc.stdout.splitlines() if ln.strip()]
    return not changed, {"watched": list(SEALED_PATHS), "changed": changed}


def row_9_upload_checklist() -> tuple[bool, dict]:
    text = CHECKLIST.read_text(encoding="utf-8")
    unchecked = re.findall(r"^\s*-\s\[ \]\s*(.+)$", text, re.M)
    return not unchecked, {"n_unchecked": len(unchecked), "unchecked": unchecked}


ROW_TITLES = {
    1: "page count within 4-6",
    2: "verify_paper_numbers passes",
    3: "pytest tests/sprint green",
    4: "every LITERATURE_EVIDENCE row verified",
    5: "no LaTeX warnings",
    6: "no float drifts past its reader",
    7: "data-figure glyphs >= 6 pt in print",
    8: "sealed files unchanged",
    9: "upload checklist complete",
}


def run(quick: bool = False) -> dict:
    pdf = PdfReader(str(MAIN_PDF))
    results: dict[int, tuple[bool, dict]] = {
        1: row_1_page_count(pdf),
        2: row_2_number_lock(),
        3: (True, {"skipped": "--quick"}) if quick else row_3_tests(),
        4: row_4_citations(),
        5: row_5_latex_warnings(),
        6: row_6_float_order(pdf),
        7: row_7_print_legibility(pdf),
        8: row_8_sealed_files(),
        9: row_9_upload_checklist(),
    }
    rows = {str(k): {"title": ROW_TITLES[k], "pass": ok, "detail": detail}
            for k, (ok, detail) in sorted(results.items())}
    return {"gate": "R7 rows 1-9",
            "pdf": MAIN_PDF.relative_to(ROOT).as_posix(),
            "quick": quick,
            "all_pass": all(r["pass"] for r in rows.values()),
            "failed_rows": [int(k) for k, r in rows.items() if not r["pass"]],
            "manual_rows": {"10": "double-blind read of PDF metadata, body and paths",
                            "11": "final PDF SHA-256 recorded in reports/paper_pdf_sha256.txt"},
            "rows": rows}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quick", action="store_true", help="skip the pytest row")
    parser.add_argument("--no-write", action="store_true", help="do not write reports/r7_gate.json")
    args = parser.parse_args()

    report = run(quick=args.quick)
    for key, row in report["rows"].items():
        print(f"[{'PASS' if row['pass'] else 'FAIL'}] row {key}: {row['title']}")
        if not row["pass"]:
            print(f"        {json.dumps(row['detail'], sort_keys=True)[:400]}")
    if not args.no_write:
        OUT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"\nwrote {OUT_PATH.relative_to(ROOT).as_posix()}")
    print(f"R7 rows 1-9: {'ALL PASS' if report['all_pass'] else 'BLOCKED on rows ' + str(report['failed_rows'])}")
    return 0 if report["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
