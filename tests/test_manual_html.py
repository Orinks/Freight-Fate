"""The dependency-free Markdown -> HTML manual converter."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location("manual_html", ROOT / "tools" / "manual_html.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_headings_become_semantic_tags():
    body = _load().render_body("# Title\n\n## Section\n\n### Sub")
    assert "<h1>Title</h1>" in body
    assert "<h2>Section</h2>" in body
    assert "<h3>Sub</h3>" in body


def test_tables_render_with_header_cells():
    md = "| Key | Action |\n| --- | --- |\n| S | Speed limit |\n| A | Repeat |"
    body = _load().render_body(md)
    assert "<table>" in body
    assert "<th>Key</th>" in body and "<th>Action</th>" in body
    assert "<td>S</td>" in body and "<td>Speed limit</td>" in body


def test_lists_and_inline_formatting():
    mod = _load()
    assert "<ul>" in mod.render_body("- one\n- two")
    assert "<ol>" in mod.render_body("1. first\n2. second")
    assert "<strong>bold</strong>" in mod.render_body("This is **bold** text.")
    assert "<code>K_s</code>" in mod.render_body("Press `K_s` to read.")
    link = mod.render_body("See [the site](https://orinks.net).")
    assert '<a href="https://orinks.net">the site</a>' in link


def test_html_is_escaped():
    body = _load().render_body("Use a < b & c > d in text.")
    assert "&lt; b &amp; c &gt;" in body
    assert "<p>" in body


def test_full_manual_converts_to_a_document():
    mod = _load()
    manual = (ROOT / "docs" / "user-manual.md").read_text(encoding="utf-8")
    doc = mod.markdown_to_html(manual, title="Freight Fate Player Manual")
    assert doc.startswith("<!DOCTYPE html>")
    assert '<html lang="en">' in doc
    assert "<title>Freight Fate Player Manual</title>" in doc
    # Real content from the manual made it through.
    assert "<table>" in doc
    assert "Driving Controls" in doc
    assert "keypad Plus and Minus keys work too" in doc
    assert "active speed-control mode" in doc
    assert "open-road target" in doc
    # Balanced primary structure: every table is closed.
    assert doc.count("<table>") == doc.count("</table>")
