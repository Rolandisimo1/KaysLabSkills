
# Delivering prose as .docx

Reference for kays-voice-core (formerly the kays-document-format skill).

Roland Kays wants prose deliverables as **Word .docx**, not markdown. Markdown
renders as unformatted plain text in his editing and co-author workflow, so a
`.md` deliverable means rework on his side every time.

## The rule

Any prose document the user will read, edit, circulate to co-authors, or submit
ships as `.docx`. This covers reviews, manuscripts and manuscript sections,
outlines, reports, memos, methods write-ups, and reviewer responses.

Data products keep their native formats — `.csv` for tables, `.png`/`.pdf` for
figures, `.py`/`.R` for code. Do not convert those.

When a document would previously have been saved as `.md`, save the `.docx`
instead. Keeping the `.md` alongside it is fine and often useful as the editable
source, but the `.docx` is the deliverable: lead with it when listing outputs.

## Conversion

`pandoc` is on PATH in the default `python` environment. `python-docx` is
available for validating output.

```python
import subprocess
cmd = ["pandoc", "input.md", "-o", "output.docx",
       "--from", "markdown+tex_math_dollars", "--to", "docx",
       "--metadata", "title=Document title",
       "--resource-path", ".",
       "--toc", "--toc-depth=2"]
r = subprocess.run(cmd, capture_output=True, text=True, cwd=build_dir)
assert r.returncode == 0, r.stderr
```

Notes that matter in practice:

- **Figures.** Copy referenced images into the same directory as the markdown
  and reference them by bare relative filename in the `![caption](file.png)`
  tag. `{{artifact:...}}` markers do not resolve inside pandoc — resolve them to
  real paths with `host.artifact_path(vid)` and copy the file in first.
- **Citations.** Markdown links of the form `[Author Year](https://doi.org/...)`
  become live hyperlinks in Word, which is the form to use for DOIs.
- **Table of contents.** Worth including on anything with more than about three
  sections; harmless to drop on a short memo.

## Validate before saving

```python
from docx import Document
doc = Document("output.docx")
heads = [p.text for p in doc.paragraphs if p.style.name.startswith("Heading")]
imgs  = [r for r in doc.part.rels.values() if "image" in r.reltype]
links = [r for r in doc.part.rels.values() if "hyperlink" in r.reltype]
```

Confirm the heading count matches the source, every expected figure is embedded,
and DOI hyperlinks survived. A silent pandoc success with zero images means a
figure path did not resolve.

## Google Docs

If a Google Doc is wanted rather than a file, the `google-drive` connector
uploads the `.docx` and converts it on the way in. Build the `.docx` first, then
ask whether to upload — do not assume Drive.
