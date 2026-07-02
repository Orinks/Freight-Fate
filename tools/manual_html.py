"""Minimal, dependency-free Markdown -> HTML converter for the player manual.

The player manual (``docs/user-manual.md``) uses a small, fixed subset of
Markdown: ATX headings, ordered and unordered lists, pipe tables, and inline
bold, code, and links. Rather than pull in a Markdown dependency just for the
build, this renders that subset to clean, accessible HTML5 (semantic headings,
real ``<table>`` with ``<th>`` headers) so screen-reader users get a properly
structured document in a browser.

It is intentionally not a general Markdown engine; it handles exactly what the
manual uses.
"""

from __future__ import annotations

import html
import re

_HEADING = re.compile(r"(#{1,6})\s+(.*)")
_ORDERED = re.compile(r"\d+\.\s+(.*)")
_UNORDERED = re.compile(r"-\s+(.*)")
_TABLE_SEP = re.compile(r"\|?[\s:|-]*-[\s:|-]*\|?\s*$")
_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_CODE = re.compile(r"`([^`]+)`")
_BOLD = re.compile(r"\*\*([^*]+)\*\*")


def _inline(text: str) -> str:
    """Escape HTML, then apply inline code, bold, and links."""
    text = html.escape(text, quote=False)
    text = _CODE.sub(r"<code>\1</code>", text)
    text = _BOLD.sub(r"<strong>\1</strong>", text)
    text = _LINK.sub(
        lambda m: f'<a href="{html.escape(m.group(2), quote=True)}">{m.group(1)}</a>', text
    )
    return text


def _split_row(row: str) -> list[str]:
    row = row.strip()
    if row.startswith("|"):
        row = row[1:]
    if row.endswith("|"):
        row = row[:-1]
    return [cell.strip() for cell in row.split("|")]


def _render_table(lines: list[str], i: int) -> tuple[int, str]:
    header = _split_row(lines[i])
    i += 2  # header row plus the separator row
    body: list[list[str]] = []
    while i < len(lines) and lines[i].strip().startswith("|"):
        body.append(_split_row(lines[i]))
        i += 1
    out = ["<table>", "<thead><tr>"]
    out += [f"<th>{_inline(c)}</th>" for c in header]
    out += ["</tr></thead>", "<tbody>"]
    for row in body:
        out.append("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in row) + "</tr>")
    out += ["</tbody>", "</table>"]
    return i, "\n".join(out)


def _render_list(lines: list[str], i: int, ordered: bool) -> tuple[int, str]:
    tag = "ol" if ordered else "ul"
    pattern = _ORDERED if ordered else _UNORDERED
    items = []
    while i < len(lines):
        match = pattern.fullmatch(lines[i].strip())
        if not match:
            break
        items.append(f"<li>{_inline(match.group(1))}</li>")
        i += 1
    return i, f"<{tag}>\n" + "\n".join(items) + f"\n</{tag}>"


def _is_table_start(lines: list[str], i: int) -> bool:
    return (
        lines[i].strip().startswith("|")
        and i + 1 < len(lines)
        and bool(_TABLE_SEP.fullmatch(lines[i + 1].strip()))
    )


def render_body(md_text: str) -> str:
    """Render the Markdown body (no surrounding HTML document)."""
    lines = md_text.split("\n")
    out: list[str] = []
    para: list[str] = []
    i = 0

    def flush() -> None:
        if para:
            out.append("<p>" + _inline(" ".join(para)) + "</p>")
            para.clear()

    while i < len(lines):
        stripped = lines[i].strip()
        heading = _HEADING.fullmatch(stripped)
        if heading:
            flush()
            level = len(heading.group(1))
            out.append(f"<h{level}>{_inline(heading.group(2))}</h{level}>")
            i += 1
        elif _is_table_start(lines, i):
            flush()
            i, table = _render_table(lines, i)
            out.append(table)
        elif _UNORDERED.fullmatch(stripped):
            flush()
            i, block = _render_list(lines, i, ordered=False)
            out.append(block)
        elif _ORDERED.fullmatch(stripped):
            flush()
            i, block = _render_list(lines, i, ordered=True)
            out.append(block)
        elif not stripped:
            flush()
            i += 1
        else:
            para.append(stripped)
            i += 1
    flush()
    return "\n".join(out)


_STYLE = """
body { font-family: system-ui, -apple-system, sans-serif; line-height: 1.5;
       max-width: 52rem; margin: 2rem auto; padding: 0 1rem; }
h1, h2, h3 { line-height: 1.25; }
table { border-collapse: collapse; width: 100%; margin: 1rem 0; }
th, td { border: 1px solid #999; padding: 0.4rem 0.6rem; text-align: left;
         vertical-align: top; }
th { background: #f0f0f0; }
code { background: #f4f4f4; padding: 0.1rem 0.3rem; border-radius: 3px; }
""".strip()


def markdown_to_html(md_text: str, title: str = "Freight Fate Player Manual") -> str:
    """Render the manual Markdown to a complete, accessible HTML5 document."""
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n<head>\n'
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{html.escape(title)}</title>\n"
        f"<style>\n{_STYLE}\n</style>\n"
        "</head>\n<body>\n"
        f"{render_body(md_text)}\n"
        "</body>\n</html>\n"
    )
