#!/usr/bin/env python3
# Copyright (c) 2026 Jatin Satyam
# SPDX-License-Identifier: Apache-2.0
"""Build the bench measurement sheet (.docx) from dims.json and figures/.  Needs python-docx."""
import json, subprocess
from pathlib import Path
from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

HERE = Path(__file__).resolve().parent; FIG = HERE / 'figures'
D = json.load(open(HERE / 'dims.json'))
try: COMMIT = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], capture_output=True, text=True, cwd=HERE).stdout.strip()
except Exception: COMMIT = '?'

doc = Document()
sec = doc.sections[0]; sec.orientation = WD_ORIENT.LANDSCAPE; sec.page_width, sec.page_height = Cm(29.7), Cm(21.0)
for m in ('left_margin', 'right_margin'): setattr(sec, m, Cm(1.5))
sec.top_margin = sec.bottom_margin = Cm(1.4)
st = doc.styles['Normal']; st.font.name = 'Calibri'; st.font.size = Pt(10.5)
USABLE = 26.7

def shade(cell, hex_):
    tcPr = cell._tc.get_or_add_tcPr(); shd = OxmlElement('w:shd'); shd.set(qn('w:val'), 'clear'); shd.set(qn('w:color'), 'auto'); shd.set(qn('w:fill'), hex_); tcPr.append(shd)
def para(text, bold=False, size=None, italic=False, color=None, after=4, align=None):
    p = doc.add_paragraph(); r = p.add_run(text); r.bold = bold; r.italic = italic
    if size: r.font.size = Pt(size)
    if color: r.font.color.rgb = RGBColor.from_string(color)
    p.paragraph_format.space_after = Pt(after)
    if align: p.alignment = align
    return p
def bullet(text):
    p = doc.add_paragraph(style='List Bullet'); p.add_run(text); p.paragraph_format.space_after = Pt(2); return p
def heading(text, level=1): return doc.add_heading(text, level=level)
def figure(name, width_cm=25.5, caption=None):
    f = FIG / name
    if not f.exists(): para(f'[missing figure {name}]', color='C00000'); return
    doc.add_picture(str(f), width=Cm(width_cm)); doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    if caption: para(caption, italic=True, size=9, after=8, align=WD_ALIGN_PARAGRAPH.CENTER)
def table(headers, rows, widths, font=9, header_fill='D9E2F3', fill_col=None):
    t = doc.add_table(rows=1, cols=len(headers)); t.style = 'Table Grid'; t.alignment = WD_TABLE_ALIGNMENT.CENTER; t.autofit = False
    for i, h in enumerate(headers):
        c = t.rows[0].cells[i]; c.width = Cm(widths[i]); c.text = ''; r = c.paragraphs[0].add_run(h); r.bold = True; r.font.size = Pt(font); shade(c, header_fill)
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].width = Cm(widths[i]); cells[i].text = ''; r = cells[i].paragraphs[0].add_run(str(v)); r.font.size = Pt(font)
            if fill_col is not None and i in fill_col: shade(cells[i], 'FFF2CC')
            cells[i].paragraphs[0].paragraph_format.space_after = Pt(0)
    # repeat the header row on each page
    trPr = t.rows[0]._tr.get_or_add_trPr(); h = OxmlElement('w:tblHeader'); h.set(qn('w:val'), 'true'); trPr.append(h)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return t

DIM_HEADERS = ['ID', 'What to measure (from → to)', 'Tool', 'Sim (cm)', 'Tag', 'Real (cm)', 'Notes / photo no.']
DIM_W = [1.2, 10.4, 1.7, 1.7, 2.4, 2.2, 7.1]
def dim_rows(group):
    return [[d['id'], d['text'] + (f"  [{d['note']}]" if d.get('note') else ''), d['tool'], f"{d['value_cm']:.1f}" if d['id'] not in ('D49', 'D35') else ('0.0' if d['id'] == 'D35' else '—'), d['tag'], '', ''] for d in D if d['group'] == group]

# ---------------------------------------------------------------- title
para('Wafer-handling cell — bench measurement sheet', bold=True, size=20, after=2)
para('Cross-check of the Gazebo digital twin against the real bench, with a tape measure, ruler and calipers.', size=12, after=2)
para(f'Prepared 2026-09-11 from the simulation at commit {COMMIT} (taught-pose layout, uncommitted working tree). Values are in centimetres, one decimal.', size=9.5, italic=True, after=10)

heading('1. Purpose and the rule of sources', 1)
para('The simulation was placed from photographs (±2 cm) and then from the taught robot poses. This sheet lists every distance in the model that a person can '
     'measure on the bench, so the model can be corrected once, from real numbers, instead of assumption by assumption. Fill the yellow "Real (cm)" column, add a '
     'note or a photo number where anything was unclear, and return the document. Leave a cell blank rather than guess; write why in Notes.')
para('Rule of sources after the sheet comes back:', bold=True, after=2)
bullet('The tape measurements in this sheet are the only source for where things sit on the bench: conveyor, towers, robot bases, carrier stations, heights.')
bullet('The taught robot poses (from the pendant, ±0.1 mm) remain the source for how each arm reaches those things. The model must satisfy both.')
bullet('Where the two disagree by more than a tape can explain, the disagreement is reported and hunted (the fork\'s seat offset, D70, is the first suspect), never silently overruled.')

heading('2. How to measure', 1)
para('Conventions', bold=True, after=2)
bullet('LEFT = the M1 Pro end of the bench, RIGHT = the Pro 600 end, FRONT = the side with the two towers, REAR = the conveyor side. Every figure is labelled this way.')
bullet('Distances are from the EDGE OF THE BENCH TOP SURFACE (not a frame, lip or leg). Heights are from the bench top surface. Tape flat on the bench, square to the edge.')
bullet('"Mouth" of a tower = its open side; "back wall" = the closed side. "Holder" = the magenta carrier that rides the belt. "Belt band" = the black running surface; "front rail" = the conveyor frame\'s front edge.')
para('Conditions during measuring', bold=True, after=2)
bullet('Cell powered off. Both robots at their HOME (rest) pose — needed for D58, D60, D62 only.')
bullet('Carrier at its load position exactly as the operator normally places it. One wafer in the yellow tower\'s top slot.')
para('Tools and accuracy', bold=True, after=2)
bullet('Tape (±0.2 cm) for the bench layout. Steel ruler or calipers (±0.05 cm) for anything under 20 cm: the fork, wafer, holder and tower slots. The nests have half a millimetre of clearance, so the small parts need the better tool.')
bullet('Take a photo of each measurement with the tape in view and write the photo number in the Notes column. It settles "which edge did you mean" later without a second session.')
bullet('Measure each row once; for the rows in section 12 (angle checks) measure at BOTH ends as asked.')
para('Tags in the Sim column', bold=True, after=2)
table(['Tag', 'Meaning'], [
    ['TAUGHT', 'Derived from Alonso\'s taught poses. Should match within ~0.5 cm if the fork\'s seat offset (D70) is right.'],
    ['TAUGHT+OWNER', 'Taught data plus your instruction (carrier flush with the belt end, kept at its 09-04 place on the belt).'],
    ['MESH', 'The part\'s own dimensions from its 3D file. Should match the real part; if not, the file is not what was printed or bought.'],
    ['FIT', 'His three Pro 600 distances fitted to the photo. May be off by a few cm.'],
    ['OWNER intent', 'Your instruction that both towers stand on one line. Not measured.'],
    ['MODEL', 'A modelling value (rest pose, fork, cup) that no measurement has confirmed.'],
    ['ASSUMED / ASSUMED - KEY', 'Never measured. KEY = the whole M1 layout depends on it.'],
    ['CHECK / QUESTION', 'Consistency checks and questions rather than model values.'],
], [4.0, 22.7], font=9)

GROUPS = [
    ('3. Bench and datum', 'Bench and datum', ['bench.png', 'render_bench.png'],
     'Measure the four sides and both diagonals. If D3 and D4 differ by more than 0.3 cm the bench top is not square and every edge-based number inherits that skew; write both values anyway.'),
    ('4. Conveyor', 'Conveyor', ['conveyor.png', 'render_conveyor.png'],
     'The conveyor frame includes the motor housing on the rear side; the belt band is the narrower running surface inside it. D8 is expected to be tiny (the model puts the housing 0.6 cm from the rear edge).'),
    ('5. Carrier (magenta holder)', 'Carrier (magenta holder)', ['carrier.png', 'render_carrier.png', 'detail_belt_cam.png'],
     'D14–D19 with the holder at its load position as the operator places it. D20–D22 after ONE belt index: run the belt once, then measure. For D20 run five indexes in a row, measure the total and divide by five; write the total and the count in Notes. The last picture is the holder at the load station seen from the rear.'),
    ('6. Towers', 'Towers', ['towers.png', 'render_towers.png', 'detail_yellow_cam.png'],
     'Both towers are identical prints; D28, D29, D36–D39 need measuring on one of them only. D35 is not measured: it is D30 minus D25.'),
    ('7. M1 Pro', 'M1 Pro', ['m1.png', 'render_m1.png'],
     'The "base plate" is the robot\'s own base (the black plate under the column). D48 asks where the big arm\'s vertical pivot (J1) is relative to the plate\'s front edge; in the model it is 2.5 cm AHEAD of the plate. If there is a separate mounting plate under the robot, describe it in D49.'),
    ('8. Pro 600', 'Pro 600', ['p6.png', 'render_p6.png', 'detail_blue_cam.png'],
     'Measure to the robot\'s own round base, not to the mounting plate; describe the plate in D57. The blue tower close-up shows the base plate behind the tower.'),
    ('9. Heights', 'Heights', ['elev.png', 'render_heights.png'],
     'All heights from the bench top surface. D58 and D60 need the robots at HOME; they tie the pendant\'s z values to the bench (his HOME is z = 157.12 mm for the M1 and 261.8 mm for the Pro 600 in the robots\' own frames).'),
    ('10. Parts and the fork (ruler / calipers)', 'Parts and the fork (ruler / calipers)', ['parts.png', 'detail_beltc_cam_C.png'],
     'D70 is the single most important number on this sheet: the distance from the centre of the M1\'s wrist shaft (J4) to the centre of a wafer resting on the fork. Measure it with the wafer on the fork. The last picture is the holder at the unload station.'),
]
for title, group, figs, intro in GROUPS:
    heading(title, 1); para(intro, after=6)
    for f in figs:
        figure(f, width_cm=25.5 if not f.startswith('detail') else 12.0)
    table(DIM_HEADERS, dim_rows(group), DIM_W, font=9, fill_col={5, 6})

heading('11. Sum checks (fill from your own numbers; they catch misreads)', 1)
para('Each line must add up. If it does not, one of its terms was misread; re-measure those before sending the sheet back.', after=4)
def val(i): return next(d['value_cm'] for d in D if d['id'] == i)
sums = [
    ['SC1', 'D5 + D6 + D7 = D1  (left edge → conveyor → right edge)', f"{val('D5')} + {val('D6')} + {val('D7')} = {val('D5')+val('D6')+val('D7'):.1f}  (D1 {val('D1')})", ''],
    ['SC2', 'D26 + D28 = D27  (yellow mouth + tower depth = back wall)', f"{val('D26')} + {val('D28')} = {val('D26')+val('D28'):.1f}  (D27 {val('D27')})", ''],
    ['SC3', 'D32 − D31 = D28  (blue mouth − back wall = tower depth)', f"{val('D32')} − {val('D31')} = {val('D32')-val('D31'):.1f}  (D28 {val('D28')})", ''],
    ['SC4', 'D9 + D12 + D8 = D2  (front edge → conveyor → rear edge)', f"{val('D9')} + {val('D12')} + {val('D8')} = {val('D9')+val('D12')+val('D8'):.1f}  (D2 {val('D2')})", ''],
    ['SC5', 'D40 + D43 + D45 = D27  (left edge → M1 base → yellow back wall)', f"{val('D40')} + {val('D43')} + {val('D45')} = {val('D40')+val('D43')+val('D45'):.1f}  (D27 {val('D27')})", ''],
    ['SC6', 'D42 + D44 + D41 = D2  (front edge → M1 base → rear edge)', f"{val('D42')} + {val('D44')} + {val('D41')} = {val('D42')+val('D44')+val('D41'):.1f}  (D2 {val('D2')})", ''],
    ['SC7', 'D52 + D53(across) + D51 = D2  (front edge → Pro 600 base → rear edge)', f"{val('D52')} + 10.9 + {val('D51')} = {val('D52')+10.9+val('D51'):.1f}  (D2 {val('D2')})", ''],
    ['SC8', 'D33 = D34 + D28  (back wall to back wall = gap + tower depth)', f"{val('D34')} + {val('D28')} = {val('D34')+val('D28'):.1f}  (D33 {val('D33')})", ''],
]
table(['ID', 'Check', 'In the model', 'Your numbers'], sums, [1.2, 9.5, 9.0, 7.0], font=9, fill_col={3})

heading('12. Angle checks: measure at both ends', 1)
para('A single distance cannot show whether an object is turned. For each row measure the same thing at the two ends named; the difference is the object\'s rotation. In the model all differences are 0.0 because everything is drawn square to the bench.', after=4)
angles = [
    ['A1', 'Front bench edge → conveyor front rail, at the conveyor\'s LEFT end and at its RIGHT end (D9 at both ends)', '38.9 / 38.9', '', '', ''],
    ['A2', 'Front bench edge → M1 base plate\'s front edge, at the plate\'s LEFT corner and RIGHT corner (D42 at both corners)', '41.4 / 41.4', '', '', ''],
    ['A3', 'Rear bench edge → Pro 600 mounting plate\'s rear edge, at its LEFT and RIGHT corners', '8.1 / 8.1', '', '', ''],
    ['A4', 'Front bench edge → the two tips of the yellow tower\'s mouth (front tip and rear tip of the C opening)', '0.7 / 14.2', '', '', ''],
    ['A5', 'Front bench edge → the two tips of the blue tower\'s mouth', '0.7 / 14.2', '', '', ''],
    ['A6', 'Left bench edge → the holder\'s left end, at the holder\'s FRONT corner and REAR corner (is the holder square on the belt?)', '44.2 / 44.2', '', '', ''],
]
table(['ID', 'What to measure', 'Model (first / second)', 'Real first', 'Real second', 'Notes'], angles, [1.2, 12.3, 3.6, 2.4, 2.4, 4.8], font=9, fill_col={3, 4, 5})

heading('13. Questions about how the cell is operated', 1)
qs = [
    ['Q1', 'When the operator puts the carrier back at the load station, is there a stop, a mark or a guide, or is it placed by eye? If by eye, roughly how much does the position vary from cycle to cycle (cm)?', ''],
    ['Q2', 'Which tower slot does the wafer start in (top / middle / bottom), and which slot of the blue tower does the Pro 600 place into?', ''],
    ['Q3', 'How is the carrier returned after a cycle (by hand along the belt, lifted off and put back)? Is the belt ever run backwards?', ''],
    ['Q4', 'The belt index: how many millimetres does the carrier travel per PLC move? (D20: five indexes, total ÷ 5.) Direction: towards the Pro 600?', ''],
    ['Q5', 'Belt drive: pulley pitch diameter, and is there a gearbox between motor and pulley (ratio)? Alonso\'s motion configuration units are 1.0 per revolution and 200 pulses per revolution.', ''],
    ['Q6', 'Is the bench top exactly 152.4 × 61.0 cm (60 × 24 inches)? If it is a different size, D1–D4 will show it; note the nominal size here.', ''],
    ['Q7', 'Is there anything on the bench the model does not show (the laser engraver, a PC, cable trays, stops) that an arm could touch?', ''],
]
table(['ID', 'Question', 'Answer'], qs, [1.2, 15.5, 10.0], font=9, fill_col={2})

heading('14. What happens after the sheet comes back', 1)
bullet('The layout is re-derived from all the real numbers at once (one least-squares pass), not row by row.')
bullet('Every disagreement between the tape and the taught poses is listed with its size, and the suspected cause named.')
bullet('The cycle and the Level 1 shadow are re-run headless and in the GUI, the six-camera recording is remade, and only then is the change committed.')
para('Generated by docs/measurement_2026-09-11/make_measurement_docx.py from dims.json; the figures come from measure_dims.py (schematics) and measure_overlay.py (camera renders with projected dimension lines).', size=8.5, italic=True, after=0)

out = HERE / 'cell_measurement_sheet.docx'; doc.save(out); print('wrote', out)
