# Digital Shadow bring-up — what to ask the bench team

Handouts for the conversation with the PLC programmer. Written 2026-09-09.

> **Historical — superseded (note added 2026-09-19).** The answers came back
> 2026-09-10/09-11: the PLC route became Modbus TCP read-only, and the Pro 600
> arrives as a UDP JSON broadcast rather than a direct socket. Both arms were
> then mirrored live on the bench 2026-09-17. The PLC leg is still verified
> only against `fake_plc.py`. See `PROJECT_CONTEXT.md` §10 for the routes as
> built.

At the time of writing, the shadow package (`src/wafer_cell_shadow/`) ran
against fake devices and everything network-side was ⛔ pending the answers
below.

| File | What it is |
|---|---|
| `cell_shadow_data_request.docx` | **The main one.** Full request list — a paste-ready message, the seven PLC asks (1.1–1.7), the robots, the network, a twenty-minute joint session, an answer sheet, and the seven plain-English questions with type-in boxes. |
| `seven_questions.docx` | Just the seven questions, as a one-page form to fill in digitally. |
| `seven_questions.pdf` | The same seven questions, one A4 page, for printing and answering by hand. |
| `seven_questions.html` | Source of the PDF. |
| `make_seven_questions_docx.py` | Generates `seven_questions.docx`; also holds the question list and the shared docx helpers. |
| `make_request_docx.py` | Generates `cell_shadow_data_request.docx` (imports the above). |

## The two things that matter most

1. **Only Global Variables are readable.** The PLC is programmed in Connected
   Components Workbench, which means the Micro800 family. On those
   controllers a variable that lives inside a program cannot be read over the
   network. If the belt and vacuum flags are local, the programmer has to add
   Global Variables that mirror them — a small change, but it needs notice.
   `pycomm3` itself is fine: it detects the family by catalog prefix `2080`
   and drops the CIP features those controllers don't support (✅ verified in
   the installed copy, 1.2.16).
2. **Three answers change the design**, not just the configuration: what
   drives the vacuum (PLC or the Pro 600's own outputs), whether the three
   devices talk to each other or are joined by plain wires, and whether any
   sensors exist. They are marked in magenta in both documents.

## Regenerating

The Word files need `python-docx`, which is not a project dependency — use a
throwaway venv:

```bash
python3 -m venv --system-site-packages /tmp/docxenv && /tmp/docxenv/bin/pip install python-docx
```

```bash
cd docs/shadow_bringup && /tmp/docxenv/bin/python make_request_docx.py cell_shadow_data_request.docx
```

The PDF is rendered from the HTML with headless Chrome — there is no
LibreOffice, pandoc or reportlab on this machine:

```bash
google-chrome --headless=new --disable-gpu --no-sandbox --no-pdf-header-footer --virtual-time-budget=8000 --print-to-pdf=seven_questions.pdf file://$PWD/seven_questions.html
```

## Verification status

* PDF ✅ rasterised with `gs` and checked by eye: one A4 page, all seven
  questions, footer inside the margin.
* Both `.docx` ✅ pass OOXML schema validation and were read back to confirm
  every section, box and table survived. ⛔ **Not** visually rendered — this
  machine has neither Word nor LibreOffice, so the page layout in Word is
  unverified. If something looks wrong when opened, fix the generator rather
  than the `.docx`.

**Trap found while building these:** OOXML enforces the order of child
elements inside `w:pPr`, `w:tblPr`, `w:tcPr` and `w:rPr`. Appending borders or
shading with `element.append(...)` produces a file that opens but fails schema
validation; use `insert_element_before(el, *successors)` instead. The ordering
tuples are at the top of `make_seven_questions_docx.py`. `python-docx`'s own
default template also ships a `w:zoom` with no `w:percent`, which fails
validation — both generators patch it before saving.
