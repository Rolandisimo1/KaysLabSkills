"""Helpers for handling tracked comments on Word manuscripts. See SKILL.md."""

import re
import zipfile

ANCHOR_PREVIEW_CHARS = 70


def plain_text(xml):
    """Visible text from a run of WordprocessingML, paragraph breaks preserved."""
    s = re.sub(r"</w:p>", "\n", xml)
    s = re.sub(r"<w:tab/>", "\t", s)
    return re.sub(r"<[^>]+>", "", s)


def docx_comments(path):
    """Return [{id, author, date, comment, anchor}] for a .docx, in document order.

    `anchor` is the text the comment was attached to, which is what makes a
    comment actionable; a comment without its anchor is often ambiguous.
    Comments whose range markers are missing get anchor=None rather than being
    dropped, so the count always matches what the user sees in Word.
    """
    z = zipfile.ZipFile(path)
    names = z.namelist()
    if "word/comments.xml" not in names:
        return []
    cx = z.read("word/comments.xml").decode("utf-8", "replace")
    doc = z.read("word/document.xml").decode("utf-8", "replace")
    out = []
    for m in re.finditer(
        r'<w:comment\b([^>]*)>(.*?)</w:comment>', cx, re.S
    ):
        attrs, body = m.group(1), m.group(2)
        cid = (re.search(r'w:id="(\d+)"', attrs) or [None, None])[1]
        author = (re.search(r'w:author="([^"]*)"', attrs) or [None, ""])[1]
        date = (re.search(r'w:date="([^"]*)"', attrs) or [None, ""])[1]
        rng = re.search(
            r'<w:commentRangeStart w:id="%s"\s*/>(.*?)<w:commentRangeEnd w:id="%s"\s*/>'
            % (cid, cid), doc, re.S)
        out.append(dict(id=cid, author=author, date=date,
                        comment=" ".join(plain_text(body).split()),
                        anchor=" ".join(plain_text(rng.group(1)).split()) if rng else None))
    out.sort(key=lambda d: int(d["id"]) if str(d["id"]).isdigit() else 0)
    return out


def comment_checklist(comments):
    """One line per comment, for pasting into a reply and ticking off."""
    rows = []
    for c in comments:
        anc = c["anchor"]
        anc = (anc[:70] + "...") if anc and len(anc) > 70 else (anc or "(no anchor)")
        rows.append(f"[{c['id']}] {c['comment']}\n      on: {anc}")
    return "\n".join(rows)


def docx_image_count(path):
    """Number of embedded images in a .docx. Assert on this before claiming
    figures were included; a marker that did not resolve leaves zero."""
    z = zipfile.ZipFile(path)
    return sum(1 for n in z.namelist() if n.startswith("word/media/"))
