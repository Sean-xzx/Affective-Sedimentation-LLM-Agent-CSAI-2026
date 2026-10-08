"""The R7 gate must fail loudly on the conditions it exists to catch."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from tools import r7_gate

ROOT = Path(__file__).resolve().parents[2]
needs_pdf = pytest.mark.skipif(not r7_gate.MAIN_PDF.is_file(), reason="paper/main.pdf absent")


def test_row_4_fails_while_any_citation_is_only_retrieved(monkeypatch, tmp_path):
    table = ("| # | key | claim | citation | url | pages | Status | notes |\n"
             "|---|---|---|---|---|---|---|---|\n"
             "| 1 | a2020 | x | y | z | p1 | verified | - |\n"
             "| 2 | b2021 | x | y | z | p2 | retrieved | - |\n")
    path = tmp_path / "LITERATURE_EVIDENCE.md"
    path.write_text(table, encoding="utf-8")
    monkeypatch.setattr(r7_gate, "EVIDENCE", path)
    ok, detail = r7_gate.row_4_citations()
    assert ok is False
    assert detail == {"n_rows": 2, "status_counts": {"retrieved": 1, "verified": 1}}

    path.write_text(table.replace("retrieved", "verified"), encoding="utf-8")
    ok, detail = r7_gate.row_4_citations()
    assert ok is True and detail["status_counts"] == {"verified": 2}


def test_row_5_reports_missing_compile_log(monkeypatch, tmp_path):
    monkeypatch.setattr(r7_gate, "MAIN_LOG", tmp_path / "missing.log")
    ok, detail = r7_gate.row_5_latex_warnings()
    assert ok is False
    assert detail["blocking"]["missing_compile_log"] == 1


def test_row_5_blocks_on_overfull_but_not_on_output_vboxes(monkeypatch, tmp_path):
    log = tmp_path / "main.log"
    monkeypatch.setattr(r7_gate, "MAIN_LOG", log)

    log.write_text("Underfull \\vbox (badness 10000) has occurred while \\output is active []\n",
                   encoding="utf-8")
    ok, detail = r7_gate.row_5_latex_warnings()
    assert ok is True and detail["informational"]["underfull_vbox_in_output"] == 1

    # A page box off by a fraction of a line is invisible; a real spill still blocks.
    log.write_text("Overfull \\vbox (1.11pt too high) has occurred while \\output is active []\n",
                   encoding="utf-8")
    ok, detail = r7_gate.row_5_latex_warnings()
    assert ok is True and detail["blocking"]["overfull"] == 0
    log.write_text("Overfull \\vbox (18.4pt too high) has occurred while \\output is active []\n",
                   encoding="utf-8")
    ok, detail = r7_gate.row_5_latex_warnings()
    assert ok is False and detail["blocking"]["overfull"] == 1

    for line, field in (
        ("Overfull \\hbox (41.73pt too wide) in paragraph at lines 1--2\n", "overfull"),
        ("Underfull \\hbox (badness 10000) in paragraph at lines 3--4\n",
         "underfull_hbox_badness_10000"),
        ("LaTeX Warning: Reference `fig:x' on page 2 undefined on input line 9.\n",
         "undefined_references"),
        ("LaTeX Warning: Citation `foo2020' on page 3 undefined on input line 9.\n",
         "undefined_citations"),
        ("LaTeX Warning: Label `tab:y' multiply defined.\n", "multiply_defined"),
    ):
        log.write_text(line, encoding="utf-8")
        ok, detail = r7_gate.row_5_latex_warnings()
        assert ok is False, field
        assert detail["blocking"][field] == 1


def test_row_6_flags_a_float_that_drifts_past_its_reader(monkeypatch):
    """Any positive lag offends: a float on the next page is read after a page turn."""
    class FakePage:
        def __init__(self, text: str) -> None:
            self._text = text

        def extract_text(self) -> str:
            return self._text

    class FakePdf:
        pages = [FakePage("we discuss Table 1, Table 2 and Table 3 here. Table 1: caption"),
                 FakePage("Table 2: caption"),
                 FakePage("filler"),
                 FakePage("Table 3: caption")]

    ok, detail = r7_gate.row_6_float_order(FakePdf())
    assert ok is False
    # Table 1 shares the page with its reader and passes; one page late already fails.
    assert detail["offenders"] == ["Table 2", "Table 3"]
    assert detail["floats"]["Table 1"]["lag_pages"] == 0
    assert detail["floats"]["Table 2"]["lag_pages"] == 1
    assert detail["floats"]["Table 3"]["lag_pages"] == 3


@needs_pdf
def test_row_6_measures_page_content_bottom_below_the_footer():
    """The page number sits under the text block; it must not mask a short page."""
    from pypdf import PdfReader
    pdf = PdfReader(str(r7_gate.MAIN_PDF))
    bottoms = [r7_gate._page_content_bottom(p, pdf) for p in pdf.pages]
    assert all(b is not None and b > r7_gate.FOOTER_BAND_PT for b in bottoms)
    _, detail = r7_gate.row_6_float_order(pdf)
    assert detail["text_block_bottom"] > r7_gate.FOOTER_BAND_PT


def test_row_6_flags_a_float_that_is_never_referenced(monkeypatch):
    class FakePage:
        def extract_text(self) -> str:
            return "Figure 1: an orphan caption"

    class FakePdf:
        pages = [FakePage()]

    ok, detail = r7_gate.row_6_float_order(FakePdf())
    assert ok is False and detail["offenders"] == ["Figure 1"]
    assert detail["floats"]["Figure 1"]["first_reference_page"] is None


def test_row_9_fails_while_the_upload_checklist_has_open_boxes(monkeypatch, tmp_path):
    path = tmp_path / "checklist.md"
    monkeypatch.setattr(r7_gate, "CHECKLIST", path)
    path.write_text("- [x] done\n- [ ] confirm the abstract\n", encoding="utf-8")
    ok, detail = r7_gate.row_9_upload_checklist()
    assert ok is False and detail["unchecked"] == ["confirm the abstract"]

    path.write_text("- [x] done\n- [x] confirm the abstract\n", encoding="utf-8")
    assert r7_gate.row_9_upload_checklist()[0] is True


def test_sealed_paths_cover_the_analysis_hash_set():
    from tools.analysis_core import ANALYSIS_HASH_PATHS
    watched = set(r7_gate.SEALED_PATHS)
    assert {p.relative_to(ROOT).as_posix() for p in ANALYSIS_HASH_PATHS} <= watched
    assert "reports/paper_number_lock.json" in watched


@needs_pdf
def test_row_7_locates_every_declared_figure_and_judges_it_by_the_right_measure():
    """Vector artwork is judged on glyph height, raster artwork on effective resolution.

    Neither measure substitutes for the other: a raster has no text operators to measure,
    and a vector figure has no pixel grid, so the row has to pick per figure.
    """
    from pypdf import PdfReader
    ok, detail = r7_gate.row_7_print_legibility(PdfReader(str(r7_gate.MAIN_PDF)))
    measured = detail["figures"]
    assert measured, "no included figure was located in the compiled PDF"
    # every figure named by \includegraphics must be found and attributed to its own file
    assert set(detail["declared"]) == set(measured)
    for name, entry in measured.items():
        # Each canvas is exported at the width it is placed at, so it is not resampled.
        assert 0.5 <= entry["placement_scale"] <= 1.3
        if name in r7_gate.NON_DATA_FIGURES:
            continue
        assert entry["min_pt"] is not None or entry.get("raster_dpi") is not None, (
            f"{name} is neither measurable as vector text nor as a raster"
        )
        if entry["min_pt"] is not None:
            assert entry["min_pt"] >= r7_gate.MIN_FIGURE_PT
    assert ok == (not detail["offenders"])


@needs_pdf
def test_row_7_blocks_on_an_underresolved_raster(monkeypatch):
    """A raster placed wider than its pixel count supports must fail, not pass silently."""
    from pypdf import PdfReader
    monkeypatch.setattr(r7_gate, "_raster_dpi", lambda name, w: 90.0)
    ok, detail = r7_gate.row_7_print_legibility(PdfReader(str(r7_gate.MAIN_PDF)))
    assert not ok
    assert any("90.0 dpi" in o for o in detail["offenders"])
    # the non-data schematic is exempt and must not be among them
    assert not any(n in o for o in detail["offenders"] for n in r7_gate.NON_DATA_FIGURES)


@needs_pdf
def test_row_7_fails_when_a_declared_figure_is_missing_from_the_pdf(monkeypatch):
    real = r7_gate._figure_natural_sizes()
    monkeypatch.setattr(r7_gate, "_figure_natural_sizes", lambda: {**real, (1, 1): ["ghost.pdf"]})
    from pypdf import PdfReader
    ok, det = r7_gate.row_7_print_legibility(PdfReader(str(r7_gate.MAIN_PDF)))
    assert not ok and any("ghost.pdf" in o for o in det["offenders"])
    assert not any(o.startswith("unmatched_") for o in det["offenders"])


@needs_pdf
def test_row_7_censuses_every_declared_figure_even_at_a_shared_size():
    """Sizes must key to lists, so two figures on one canvas size cannot collapse.

    Asserted against every figure main.tex includes rather than against a pair that
    happens to share a size today, so removing a figure cannot retire the guard: if
    a size mapped to one name, a twinned figure would go missing from the census.
    """
    sizes = r7_gate._figure_natural_sizes()
    assert all(isinstance(v, list) for v in sizes.values())

    censused = [name for names in sizes.values() for name in names]
    assert len(censused) == len(set(censused)), censused

    declared = set(re.findall(
        r"\\includegraphics\[[^\]]*\]\{figures/([^}]+)\}",
        (r7_gate.PAPER / "main.tex").read_text(encoding="utf-8"),
    ))
    assert set(censused) == declared


@needs_pdf
def test_the_gate_reports_all_nine_rows():
    report = r7_gate.run(quick=True)
    assert sorted(report["rows"]) == [str(i) for i in range(1, 10)]
    assert report["rows"]["3"]["detail"] == {"skipped": "--quick"}
    assert report["all_pass"] == (not report["failed_rows"])
