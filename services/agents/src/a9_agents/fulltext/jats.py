"""JATS XML (PubMed Central, Europe PMC) -> ParsedDocument.

Sections, paragraphs, tables and figure captions keep their structure; inline citation markers
(bibr xrefs) and MathML noise are dropped from paragraph text; the licence is read from the article's
own permissions block.
"""

from __future__ import annotations

from xml.etree.ElementTree import Element

from defusedxml import ElementTree

from a9_agents.fulltext.document import DocBuilder, ParsedDocument, collapse

PARSER_VERSION = "jats-v1"
XLINK = "{http://www.w3.org/1999/xlink}"
ALI = "{http://www.niso.org/schemas/ali/1.0/}"
SKIP_TAGS = {"xref-bibr"}


def _is_mathml(el: Element) -> bool:
    return el.tag.startswith("{http://www.w3.org/1998/Math/MathML}")


def inline_text(el: Element) -> str:
    """Text of an element without citation markers or MathML."""
    parts: list[str] = [el.text or ""]
    for child in el:
        if _is_mathml(child) or (child.tag == "xref" and child.get("ref-type") == "bibr"):
            pass
        elif child.tag in ("table-wrap", "fig", "disp-formula"):
            pass  # handled as their own blocks
        else:
            parts.append(inline_text(child))
        parts.append(child.tail or "")
    return "".join(parts)


def _title(el: Element | None) -> str:
    return collapse(inline_text(el)) if el is not None else ""


def _licence(root: Element) -> str | None:
    perms = root.find(".//article-meta/permissions")
    if perms is None:
        return None
    for lic in perms.iter("license"):
        href = lic.get(f"{XLINK}href") or lic.get("href")
        if href:
            return href
        for ref in lic.iter(f"{ALI}license_ref"):
            if ref.text and ref.text.strip():
                return ref.text.strip()
        text = collapse(" ".join(lic.itertext()))
        if text:
            return text
    return None


def _table_rows(table: Element) -> list[list[str]]:
    rows = []
    for tr in table.iter("tr"):
        cells = [collapse(" ".join(c.itertext())) for c in tr if c.tag in ("th", "td")]
        if any(cells):
            rows.append(cells)
    return rows


def parse_jats(xml: bytes) -> ParsedDocument:
    root = ElementTree.fromstring(xml)
    article = root if root.tag == "article" else root.find(".//article")
    if article is None:
        raise ValueError("no <article> element in JATS document")
    b = DocBuilder(PARSER_VERSION)
    warnings: list[str] = []

    title = _title(article.find(".//article-meta/title-group/article-title"))
    ids = {
        i.get("pub-id-type", ""): collapse("".join(i.itertext()))
        for i in article.findall(".//article-meta/article-id")
    }

    abstract = article.find(".//article-meta/abstract")
    if abstract is not None and abstract.get("abstract-type") is None:
        for sec in abstract.findall("sec") or [abstract]:
            label = _title(sec.find("title")) if sec is not abstract else ""
            for p in sec.findall("p"):
                text = collapse(inline_text(p))
                b.add("abstract", f"{label}: {text}" if label else text, ["Abstract"])

    def add_float(el: Element, path: list[str]) -> None:
        label, caption = _title(el.find("label")), el.find("caption")
        cap_text = (
            collapse(" ".join(inline_text(p) for p in caption.iter("p")))
            if caption is not None
            else ""
        )
        cap_title = _title(caption.find("title")) if caption is not None else ""
        header = " ".join(x for x in (label, cap_title) if x)
        full_caption = (
            f"{header}. {cap_text}".strip(". ") if cap_text and header else (header or cap_text)
        )
        if el.tag == "fig":
            b.add("figure_caption", full_caption, path)
            return
        table = el.find(".//table")
        rows = _table_rows(table) if table is not None else []
        if rows:
            grid = "\\n".join("\t".join(r) for r in rows)
            text = (full_caption + "\n" if full_caption else "") + grid.replace("\\n", "\n")
            b.add("table", text, path, rows=rows)
        elif full_caption:
            b.add("figure_caption", full_caption, path)
            warnings.append(f"table without parsable rows: {label or full_caption[:40]}")

    def walk(sec: Element, path: list[str]) -> None:
        for child in sec:
            if child.tag == "sec":
                heading = _title(child.find("title")) or "Untitled section"
                walk(child, [*path, heading])
            elif child.tag == "p":
                b.add("body", collapse(inline_text(child)), path or ["Body"])
                for float_el in child.iter():
                    if float_el.tag in ("table-wrap", "fig"):
                        add_float(float_el, path or ["Body"])
            elif child.tag in ("table-wrap", "fig"):
                add_float(child, path or ["Body"])

    body = article.find("body")
    if body is not None:
        walk(body, [])
    else:
        warnings.append("no <body>: abstract-only")

    for ref in article.findall(".//back/ref-list/ref"):
        b.add("references", collapse(" ".join(ref.itertext())), ["References"])

    return b.build(title=title or None, licence_raw=_licence(root), ids=ids, warnings=warnings)
