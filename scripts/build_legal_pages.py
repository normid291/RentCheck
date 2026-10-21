"""Render the legal documents into the pages the app serves.

`docs/legal/*.md` is the single source of truth. This script writes
`app/static/privacy.html` and `app/static/terms.html` from it. Do not edit the
generated HTML by hand — edit the Markdown and re-run:

    python scripts/build_legal_pages.py

Only the Markdown subset actually used by docs/legal is supported: headings,
paragraphs, bulleted and numbered lists, tables, blockquotes, horizontal rules,
and inline bold / code / links. That is deliberate — a small, readable renderer
beats a dependency, and the documents are the only input.
"""
from __future__ import annotations

import html
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LEGAL_DIR = os.path.join(ROOT, "docs", "legal")
STATIC_DIR = os.path.join(ROOT, "app", "static")

# Same mark as app/static/index.html, so the pages share a favicon.
ICON = (
    "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'"
    " fill='none' stroke='%230e7a52' stroke-width='2.2' stroke-linecap='round'"
    " stroke-linejoin='round'%3E%3Cpath d='M12 3l7 3v5c0 4.4-3 8-7 10-4-2-7-5.6-7-10V6z'/%3E"
    "%3Cpath d='M9 12l2 2 4-4'/%3E%3C/svg%3E"
)

PAGES = [
    {
        "md": "privacy-policy.md",
        "out": "privacy.html",
        "title": "Privacy Policy",
        "desc": (
            "What Tenura does with the tenancy agreement you submit, who else "
            "sees it, and what you can ask us to do about it."
        ),
    },
    {
        "md": "terms-of-service.md",
        "out": "terms.html",
        "title": "Terms of Service",
        "desc": (
            "The terms that govern your use of Tenura, including what it is "
            "not: legal advice."
        ),
    },
]

SHELL = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>__TITLE__ — Tenura</title>
  <meta name="description" content="__DESC__" />
  <meta name="theme-color" content="#0e7a52" />
  <link rel="icon" href="__ICON__" />
  <link rel="stylesheet" href="/styles.css" />
</head>
<body>
  <header class="nav">
    <div class="wrap nav-inner">
      <a class="brand" href="/">
        <span class="brand-mark" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l7 3v5c0 4.4-3 8-7 10-4-2-7-5.6-7-10V6z"/><path d="M9 12l2 2 4-4"/></svg>
        </span>
        Tenura
      </a>
      <span class="nav-spacer"></span>
      <nav class="nav-links">
        <a href="/privacy">Privacy</a>
        <a href="/terms">Terms</a>
        <a href="/">Analyse an agreement</a>
      </nav>
      <div class="auth-slot" id="authSlot"></div>
    </div>
  </header>

  <main class="wrap legal">
    <article>
__BODY__
    </article>
  </main>

  <footer class="footer">
    <div class="wrap">
      <div class="disclaimer">
        <strong>Not legal advice.</strong> Tenura provides general information about
        common rental practices to help you read an agreement. It is not a substitute
        for advice from a qualified lawyer.
      </div>
      <div class="footer-row">
        <span>Tenura — built for the Devcenter Hacktober sprint.</span>
        <span class="footer-links">
          <a href="/privacy">Privacy Policy</a>
          <a href="/terms">Terms of Service</a>
        </span>
      </div>
    </div>
  </footer>
  <script src="/common.js"></script>
</body>
</html>
"""


def inline(text: str) -> str:
    """Escape, then apply the inline spans we use: links, bold, code."""
    out = html.escape(text, quote=True)
    out = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', out)
    out = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", out)
    out = re.sub(r"`([^`]+)`", r"<code>\1</code>", out)
    return out


def slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9\s-]", "", text.lower())
    return re.sub(r"[\s-]+", "-", s).strip("-")


_TABLE_SEP = re.compile(r"^\|[\s:|-]+\|$")

_BLOCK_START = re.compile(r"^(#{1,4}\s|[-*]\s|\d+[.)]\s|\||>|-{3,}$)")


def _items(lines: list[str], i: int, marker: str) -> tuple[list[str], int]:
    """Collect a list's items, joining indented continuation lines.

    A continuation must be indented, so a normal unindented paragraph directly
    after a list is not swallowed into the last item.
    """
    items: list[str] = []
    current: str | None = None
    while i < len(lines):
        raw = lines[i]
        stripped = raw.strip()
        if not stripped:
            break
        if re.match(marker, stripped):
            if current is not None:
                items.append(current)
            current = re.sub(marker, "", stripped)
            i += 1
            continue
        if current is not None and raw[:1] in (" ", "\t") and not _BLOCK_START.match(stripped):
            current += " " + stripped
            i += 1
            continue
        break
    if current is not None:
        items.append(current)
    return items, i


def render(md: str) -> str:
    """Markdown -> HTML for the subset we use."""
    lines = md.replace("\r\n", "\n").split("\n")
    out: list[str] = []
    para: list[str] = []
    i = 0

    def flush_para() -> None:
        if para:
            out.append("<p>" + inline(" ".join(para)) + "</p>")
            para.clear()

    while i < len(lines):
        stripped = lines[i].strip()

        if not stripped:
            flush_para()
            i += 1
            continue

        # -- table: a pipe row followed by a |---|---| separator
        if stripped.startswith("|") and i + 1 < len(lines) and _TABLE_SEP.match(lines[i + 1].strip()):
            flush_para()
            header = [c.strip() for c in stripped.strip("|").split("|")]
            i += 2
            rows: list[list[str]] = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            width = len(header)
            out.append('<div class="legal-table"><table>')
            if any(header):  # skip an empty header row (used as a plain key/value table)
                out.append(
                    "<thead><tr>"
                    + "".join(f"<th>{inline(c)}</th>" for c in header)
                    + "</tr></thead>"
                )
            out.append("<tbody>")
            for row in rows:
                row = (row + [""] * width)[:width]
                out.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in row) + "</tr>")
            out.append("</tbody></table></div>")
            continue

        # -- heading
        m = re.match(r"^(#{1,4})\s+(.*)$", stripped)
        if m:
            flush_para()
            level = len(m.group(1))
            text = m.group(2).strip()
            out.append(f'<h{level} id="{slug(text)}">{inline(text)}</h{level}>')
            i += 1
            continue

        # -- horizontal rule
        if re.match(r"^-{3,}$", stripped):
            flush_para()
            out.append("<hr />")
            i += 1
            continue

        # -- blockquote
        if stripped.startswith(">"):
            flush_para()
            buf: list[str] = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip().lstrip(">").strip())
                i += 1
            out.append("<blockquote>" + inline(" ".join(buf)) + "</blockquote>")
            continue

        # -- unordered list
        if re.match(r"^[-*]\s+", stripped):
            flush_para()
            items, i = _items(lines, i, r"^[-*]\s+")
            out.append("<ul>" + "".join(f"<li>{inline(x)}</li>" for x in items) + "</ul>")
            continue

        # -- ordered list
        if re.match(r"^\d+[.)]\s+", stripped):
            flush_para()
            items, i = _items(lines, i, r"^\d+[.)]\s+")
            out.append("<ol>" + "".join(f"<li>{inline(x)}</li>" for x in items) + "</ol>")
            continue

        para.append(stripped)
        i += 1

    flush_para()
    return "\n".join("      " + line for line in out)


def build(page: dict) -> str:
    md_path = os.path.join(LEGAL_DIR, page["md"])
    with open(md_path, encoding="utf-8") as fh:
        body = render(fh.read())

    out = SHELL
    out = out.replace("__TITLE__", html.escape(page["title"], quote=True))
    out = out.replace("__DESC__", html.escape(page["desc"], quote=True))
    out = out.replace("__ICON__", ICON)
    out = out.replace("__BODY__", body)

    out_path = os.path.join(STATIC_DIR, page["out"])
    with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(out)
    return out_path


def main() -> int:
    for page in PAGES:
        path = build(page)
        print(f"wrote {os.path.relpath(path, ROOT)} ({os.path.getsize(path):,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
