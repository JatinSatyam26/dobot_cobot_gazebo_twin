#!/usr/bin/env python3
# Copyright (c) 2026 Jatin Satyam
# SPDX-License-Identifier: Apache-2.0
"""
The measurement catalogue for the bench cross-check (2026-09-11).

Every dimension is defined by TWO POINTS in world coordinates (metres, bench top
z = 0, x along the bench with the M1 Pro at -x, y toward the rear). Its value is
computed from those points, so the tables and the drawings cannot disagree.
Writes figures/*.png (schematics) and dims.json for the document builder.

    source /opt/ros/jazzy/setup.bash && source install/setup.bash
    python3 docs/measurement_2026-09-11/measure_dims.py
"""
import json, math, os, sys
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle, Polygon

HERE = Path(__file__).resolve().parent
FIG = HERE / 'figures'; FIG.mkdir(exist_ok=True)
sys.path.insert(0, str(HERE.parents[1] / 'install/wafer_cell_bringup/lib/wafer_cell_bringup'))
import cell_layout as cl                                   # noqa: E402

# ------------------------------------------------------------------ world boxes (from check_extents, 2026-09-11)
BX0, BX1, BY0, BY1 = -0.762, 0.762, -0.3048, 0.3048        # bench top
CV = (-0.3290, 0.3690, 0.0839, 0.2984, 0.0, 0.0626)          # conveyor frame incl. motor housing
BAND = (cl.BELT_SURFACE_Y - 0.060, cl.BELT_SURFACE_Y + 0.060)  # running surface, across
CR_A = (cl.BELT_A_X - 0.090, cl.BELT_A_X + 0.090, cl.BELT_SURFACE_Y - 0.035, cl.BELT_SURFACE_Y + 0.035)  # holder at load
CR_C = (cl.BELT_C_X - 0.090, cl.BELT_C_X + 0.090, CR_A[2], CR_A[3])
Z_BELT, Z_PLATE_TOP, Z_SEAT, Z_POST = cl.BELT_XYZ[2], cl.BELT_XYZ[2] + 0.003, cl.NEST_SEAT_Z, cl.HOLDER_POST_TOP
yx, yy = cl.NEST_YELLOW[:2]; bx, by = cl.NEST_BLUE[:2]
TY = (yx - 0.040, yx + 0.0675, yy - 0.0675, yy + 0.0675)     # yellow tower: mouth at -x, back wall at +x
TB = (bx - 0.040, bx + 0.0675, by - 0.0675, by + 0.0675)
Z_TOWER = 0.100; SLOTS = cl.SHELF_Z
M1 = (-0.7242, -0.4938, 0.1088, 0.2842)                      # M1 Pro's own base plate (vendor model)
M1_J1 = (cl.M1PRO_XYZ[0], cl.M1PRO_XYZ[1] - 0.120)           # J1 pivot axis
Z_M1_TOP = 0.6876                                            # column top (mount on the bench top since 2026-09-11)
P6 = (0.5453, 0.6595, 0.0693, 0.1787)                        # Pro 600 base footprint
P6_PLATE = (0.500, 0.700, 0.024, 0.224)
Z_P6_TOP = 0.157
WAFER_R, WAFER_T = 0.0635, cl.WAFER_THICKNESS

# heights that need FK (flange and cup at HOME)
try:
    from solve_home_poses import Chain
    chain = Chain(str(HERE.parents[1] / 'install/wafer_cell_bringup/share/wafer_cell_bringup/urdf/cell.urdf'))
    Z_M1_FLANGE_HOME = float(chain.pose('m1pro_tcp', cl.HOME)[2, 3])
    Z_P6_CUP_HOME = float(chain.pose('pro600_cup_tip', cl.HOME)[2, 3])
    Z_P6_FLANGE_HOME = float(chain.pose('pro600_link6', cl.HOME)[2, 3])
except Exception as e:                                       # noqa: BLE001
    print('FK unavailable:', e); Z_M1_FLANGE_HOME = Z_P6_CUP_HOME = Z_P6_FLANGE_HOME = float('nan')
FORK_BLADE_BELOW_FLANGE = 0.025                              # blade top is 25 mm below the M1 flange (fork_seat z -0.025)

# ------------------------------------------------------------------ the catalogue
# kind: 'x' horizontal in plan (p1,p2 differ in x, drawn at y=at), 'y' across in plan (drawn at x=at),
#       'z' height in the front elevation (drawn at x=at), 'd' diagonal (drawn between the points), 't' table only
D = []
def dim(id_, group, text, tool, tag, kind, p1=None, p2=None, at=None, fig=None, value=None, note='', side='right', ldx=0.0):
    if value is None:
        if kind == 'x': value = abs(p2 - p1)
        elif kind == 'y': value = abs(p2 - p1)
        elif kind == 'z': value = abs(p2 - p1)
        elif kind == 'd': value = math.dist(p1, p2)
    D.append(dict(id=id_, group=group, text=text, tool=tool, tag=tag, kind=kind, p1=p1, p2=p2, at=at, fig=fig,
                  value_cm=round(value * 100, 1), note=note, side=side, ldx=ldx))

G0, G1, G2, G3, G4, G5, G6, G7 = ('Bench and datum', 'Conveyor', 'Carrier (magenta holder)', 'Towers',
                                  'M1 Pro', 'Pro 600', 'Heights', 'Parts and the fork (ruler / calipers)')
dim('D1', G0, 'Bench top length, left edge to right edge', 'tape', 'ASSUMED', 'x', BX0, BX1, at=BY0 - 0.045, fig='bench')
dim('D2', G0, 'Bench top depth, front edge to rear edge', 'tape', 'ASSUMED', 'y', BY0, BY1, at=BX0 - 0.06, fig='bench')
dim('D3', G0, 'Diagonal: left-front corner to right-rear corner', 'tape', 'CHECK', 'd', (BX0, BY0), (BX1, BY1), fig='bench')
dim('D4', G0, 'Diagonal: right-front corner to left-rear corner', 'tape', 'CHECK', 'd', (BX1, BY0), (BX0, BY1), fig='bench')

dim('D5', G1, 'Left bench edge to the conveyor\'s left end', 'tape', 'TAUGHT+OWNER', 'x', BX0, CV[0], at=BY1 + 0.03, fig='conveyor')
dim('D6', G1, 'Conveyor frame length, left end to right end', 'tape', 'MESH', 'x', CV[0], CV[1], at=BY1 + 0.075, fig='conveyor')
dim('D7', G1, 'Conveyor\'s right end to the right bench edge', 'tape', 'TAUGHT+OWNER', 'x', CV[1], BX1, at=BY1 + 0.03, fig='conveyor')
dim('D8', G1, 'Rear bench edge to the conveyor\'s rear side (motor housing)', 'tape', 'TAUGHT', 'y', CV[3], BY1, at=0.60, fig='conveyor')
dim('D9', G1, 'Front bench edge to the conveyor\'s front rail', 'tape', 'TAUGHT', 'y', BY0, CV[2], at=0.20, fig='conveyor')
dim('D10', G1, 'Front bench edge to the belt band\'s front edge (the running surface)', 'tape', 'TAUGHT', 'y', BY0, BAND[0], at=0.28, fig='conveyor')
dim('D11', G1, 'Belt band width (running surface, front edge to rear edge)', 'tape', 'MESH', 'y', BAND[0], BAND[1], at=CV[1] + 0.03, fig='conveyor')
dim('D12', G1, 'Conveyor width incl. the motor housing, front rail to rear side', 'tape', 'MESH', 'y', CV[2], CV[3], at=CV[1] + 0.085, fig='conveyor')
dim('D13', G1, 'Belt surface height above the bench top', 'tape', 'MESH', 'z', 0.0, Z_BELT, at=0.30, fig='elev')

dim('D14', G2, 'Conveyor\'s left end to the holder\'s left end (holder at rest at the load station)', 'ruler', 'OWNER video', 'x', CV[0], CR_A[0], at=CR_A[3] + 0.012, fig='carrier',
    note='should be nearly flush')
dim('D15', G2, 'Left bench edge to the holder\'s left end, at the load station', 'tape', 'TAUGHT', 'x', BX0, CR_A[0], at=0.06, fig='carrier')
dim('D16', G2, 'Front bench edge to the holder\'s front edge', 'tape', 'TAUGHT', 'y', BY0, CR_A[2], at=-0.05, fig='carrier')
dim('D17', G2, 'Belt band visible in front of the holder (band front edge to holder front edge)', 'ruler', 'TAUGHT', 'y', BAND[0], CR_A[2], at=CR_A[0] - 0.035, fig='carrier', side='left',
    note='same amount behind it')
dim('D18', G2, 'Holder plate length (along the belt)', 'ruler', 'MESH', 'x', CR_A[0], CR_A[1], at=CV[3] + 0.03, fig='carrier')
dim('D19', G2, 'Holder plate width (across the belt)', 'ruler', 'MESH', 'y', CR_A[2], CR_A[3], at=CR_A[1] + 0.025, fig='carrier')
dim('D20', G2, 'Belt travel per index: holder centre at load to holder centre at unload', 'tape', 'TAUGHT prediction', 'x', cl.BELT_A_X, cl.BELT_C_X, at=CV[3] + 0.075, fig='carrier',
    note='run 5 indexes, measure the total, divide by 5')
dim('D21', G2, 'Left bench edge to the holder\'s left end, at the unload station', 'tape', 'TAUGHT', 'x', BX0, CR_C[0], at=0.015, fig='carrier')
dim('D22', G2, 'Holder\'s right end at the unload station to the right bench edge', 'tape', 'TAUGHT', 'x', CR_C[1], BX1, at=0.015, fig='carrier')
dim('D23', G2, 'Holder seat ring height above the belt surface', 'ruler', 'MESH', 'z', Z_BELT, Z_SEAT, at=CR_A[1] + 0.03, fig='elev')
dim('D24', G2, 'Holder post height above the belt surface (plate bottom to post top)', 'ruler', 'MESH', 'z', Z_BELT, Z_POST, at=CR_A[1] + 0.075, fig='elev')

dim('D25', G3, 'Front bench edge to the yellow tower\'s front outer wall', 'ruler', 'TAUGHT', 'y', BY0, TY[2], at=TY[0] - 0.03, fig='towers', side='left')
dim('D26', G3, 'Left bench edge to the yellow tower\'s mouth (open side)', 'tape', 'TAUGHT', 'x', BX0, TY[0], at=-0.25, fig='towers')
dim('D27', G3, 'Left bench edge to the yellow tower\'s back wall (closed side)', 'tape', 'TAUGHT', 'x', BX0, TY[1], at=-0.18, fig='towers')
dim('D28', G3, 'Tower depth, mouth to back wall (outside)', 'ruler', 'MESH', 'x', TY[0], TY[1], at=TY[3] + 0.03, fig='towers')
dim('D29', G3, 'Tower outer width, across', 'ruler', 'MESH', 'y', TY[2], TY[3], at=TY[1] + 0.035, fig='towers')
dim('D30', G3, 'Front bench edge to the blue tower\'s front outer wall', 'ruler', 'OWNER intent', 'y', BY0, TB[2], at=TB[1] + 0.03, fig='towers')
dim('D31', G3, 'Blue tower\'s back wall to the right bench edge', 'tape', 'FIT', 'x', TB[1], BX1, at=-0.18, fig='towers')
dim('D32', G3, 'Blue tower\'s mouth to the right bench edge', 'tape', 'FIT', 'x', TB[0], BX1, at=-0.25, fig='towers')
dim('D33', G3, 'Yellow back wall to blue back wall (equals centre to centre)', 'tape', 'FIT', 'x', TY[1], TB[1], at=-0.11, fig='towers')
dim('D34', G3, 'Gap: yellow back wall to blue mouth', 'tape', 'FIT', 'x', TY[1], TB[0], at=-0.05, fig='towers')
dim('D35', G3, 'Both towers' + "' front walls on one line: D30 minus D25", 'computed', 'OWNER intent', 't', value=abs(TB[2] - TY[2]))
dim('D36', G3, 'Tower height, bench top to the top rim', 'ruler', 'MESH', 'z', 0.0, Z_TOWER, at=yx - 0.10, fig='elev')
dim('D37', G3, 'Top slot: wafer underside height above the bench top (the slot the M1 picks from)', 'ruler', 'MESH', 'z', 0.0, SLOTS[2], at=None, fig='tower')
dim('D38', G3, 'Middle slot: wafer underside height', 'ruler', 'MESH', 'z', 0.0, SLOTS[1], at=None, fig='tower')
dim('D39', G3, 'Bottom slot: wafer underside height', 'ruler', 'MESH', 'z', 0.0, SLOTS[0], at=None, fig='tower')

dim('D40', G4, 'Left bench edge to the M1 base plate\'s left edge', 'ruler', 'TAUGHT', 'x', BX0, M1[0], at=0.03, fig='m1', ldx=0.06)
dim('D41', G4, 'M1 base plate\'s rear edge to the rear bench edge', 'ruler', 'TAUGHT', 'y', M1[3], BY1, at=M1[1] + 0.03, fig='m1')
dim('D42', G4, 'Front bench edge to the M1 base plate\'s front edge', 'tape', 'TAUGHT', 'y', BY0, M1[2], at=-0.745, fig='m1', side='left')
dim('D43', G4, 'M1 base plate length along the bench', 'ruler', 'MESH', 'x', M1[0], M1[1], at=BY1 + 0.03, fig='m1')
dim('D44', G4, 'M1 base plate width across the bench', 'ruler', 'MESH', 'y', M1[2], M1[3], at=BX0 - 0.035, fig='m1', side='left')
dim('D45', G4, 'M1 base plate\'s right edge to the yellow tower\'s back wall', 'tape', 'TAUGHT', 'x', M1[1], TY[1], at=0.045, fig='m1')
dim('D46', G4, 'M1 base plate\'s front edge to the yellow tower\'s rear outer wall', 'tape', 'TAUGHT', 'y', TY[3], M1[2], at=TY[1] + 0.04, fig='m1')
dim('D47', G4, 'M1 base plate\'s right edge to the conveyor\'s left end', 'tape', 'TAUGHT+OWNER', 'x', M1[1], CV[0], at=0.235, fig='m1')
dim('D48', G4, 'M1 base plate\'s front edge to the centre of the J1 pivot (the big arm\'s vertical axis)', 'ruler', 'MESH', 'y', M1_J1[1], M1[2], at=M1[1] + 0.045, fig='m1',
    note='J1 axis is AHEAD of the plate front edge in the model')
dim('D49', G4, 'Is there a separate mounting plate under the M1 Pro (other than its own base)? If yes, its size', 'ruler', 'QUESTION', 't', value=0.0, note='the model has none')
dim('D50', G5, 'Pro 600 base\'s right edge to the right bench edge', 'tape', 'FIT', 'x', P6[1], BX1, at=0.03, fig='p6')
dim('D51', G5, 'Pro 600 base\'s rear edge to the rear bench edge', 'tape', 'FIT', 'y', P6[3], BY1, at=P6[1] + 0.03, fig='p6')
dim('D52', G5, 'Front bench edge to the Pro 600 base\'s front edge', 'tape', 'FIT', 'y', BY0, P6[2], at=P6[1] + 0.055, fig='p6', side='left')
dim('D53', G5, 'Pro 600 base diameter (the round base; model footprint 11.4 x 10.9)', 'ruler', 'MESH', 'x', P6[0], P6[1], at=BY1 + 0.03, fig='p6')
dim('D54', G5, 'Pro 600 base\'s left edge to the blue tower\'s back wall', 'tape', 'FIT', 'x', TB[1], P6[0], at=-0.02, fig='p6')
dim('D55', G5, 'Pro 600 base\'s front edge to the blue tower\'s rear outer wall', 'tape', 'FIT', 'y', TB[3], P6[2], at=P6[0] + 0.02, fig='p6')
dim('D56', G5, 'Conveyor\'s right end to the Pro 600 base\'s left edge', 'tape', 'FIT', 'x', CV[1], P6[0], at=0.235, fig='p6')
dim('D57', G5, 'Black plate under the Pro 600, if one exists: size along x across', 'ruler', 'PHOTO', 't', value=0.200, note='model: 20.0 x 20.0')

dim('D58', G6, 'M1 Pro flange underside height above the bench top, robot at HOME', 'tape', 'MODEL', 'z', 0.0, Z_M1_FLANGE_HOME, at=-0.62, fig='elev',
    note='his HOME z = 157.12 mm from the robot base frame; this finds where that frame\'s zero is')
dim('D59', G6, 'M1 fork: flange underside to the blade\'s top surface (vertical)', 'ruler', 'MODEL', 't', value=FORK_BLADE_BELOW_FLANGE)
dim('D60', G6, 'Pro 600 cup lip height above the bench top, robot at HOME', 'tape', 'MODEL', 'z', 0.0, Z_P6_CUP_HOME, at=0.34, fig='elev',
    note='his HOME z = 261.8 mm in the robot\'s frame')
dim('D61', G6, 'Pro 600 cup: flange face to the cup lip (the suction cup\'s length)', 'ruler', 'MODEL', 't', value=Z_P6_FLANGE_HOME - Z_P6_CUP_HOME)
dim('D62', G6, 'M1 Pro column top height above the bench top', 'tape', 'MESH', 'z', 0.0, Z_M1_TOP, at=-0.76, fig='elev')
dim('D63', G6, 'Pro 600 fixed base height (bench top to the top of the non-moving base)', 'ruler', 'MESH', 'z', 0.0, Z_P6_TOP, at=0.70, fig='elev')

dim('D64', G7, 'Wafer diameter', 'calipers', 'MESH', 't', value=2 * WAFER_R)
dim('D65', G7, 'Wafer thickness', 'calipers', 'MODEL', 't', value=WAFER_T, note='the model exaggerates it for contact stability; the real value is wanted')
dim('D66', G7, 'Holder seat ring: inner diameter and outer (lip) diameter, write both', 'calipers', 'MESH', 't', value=0.115, note='model: 11.5 inner / 12.8 lip')
dim('D67', G7, 'Tower inner diameter at the slots', 'calipers', 'MESH', 't', value=0.128)
dim('D68', G7, 'Tower slot ledge width (how far the ledge sticks in)', 'calipers', 'MESH', 't', value=0.0065)
dim('D69', G7, 'Fork blade width', 'calipers', 'MESH', 't', value=0.0582)
dim('D70', G7, 'Fork: centre of the wrist (J4) shaft to the centre of a wafer resting on the fork', 'ruler', 'ASSUMED - KEY', 't', value=cl.FORK_SEAT_X,
    note='the one number the whole M1 layout depends on')
dim('D71', G7, 'Fork: centre of the wrist shaft to the blade tip', 'ruler', 'ASSUMED', 't', value=cl.FORK_SEAT_X + 0.030)
dim('D72', G7, 'Fork blade overall length', 'ruler', 'MESH', 't', value=0.1895)

# ------------------------------------------------------------------ drawing helpers
def box(ax, b, **kw): ax.add_patch(Rectangle((b[0], b[2]), b[1] - b[0], b[3] - b[2], **kw))
def tower(ax, t, color):
    # C-shape: back wall at +x, mouth at -x (open toward the left)
    x0, x1, y0, y1 = t; w = 0.012
    ax.add_patch(Rectangle((x1 - w, y0), w, y1 - y0, fc=color, ec='k', lw=0.6))
    ax.add_patch(Rectangle((x0, y0), x1 - x0, w, fc=color, ec='k', lw=0.6))
    ax.add_patch(Rectangle((x0, y1 - w), x1 - x0, w, fc=color, ec='k', lw=0.6))
    cx, cy = (x0 + 0.040 + 0.0675) / 2 if False else x0 + 0.040, (y0 + y1) / 2
    ax.add_patch(Circle((cx, cy), WAFER_R, fc='none', ec='0.4', lw=0.5, ls='--'))
def arrow_dim(ax, p1, p2, label, off=0.0, color='#c00000', fs=9, ldx=0.0):
    ax.annotate('', xy=p2, xytext=p1, arrowprops=dict(arrowstyle='<->', color=color, lw=0.9, shrinkA=0, shrinkB=0))
    mx, my = (p1[0] + p2[0]) / 2 + ldx, (p1[1] + p2[1]) / 2
    ax.text(mx, my + off, label, color=color, fontsize=fs, ha='center', va='bottom', fontweight='bold',
            bbox=dict(boxstyle='round,pad=0.15', fc='white', ec='none', alpha=0.85))
def draw_dim(ax, d, ext=True):
    lab = f"{d['id']}  {d['value_cm']:.1f}"
    k = d['kind']
    if k == 'x':
        y = d['at']; p1, p2 = (d['p1'], y), (d['p2'], y)
        if ext:
            for x in (d['p1'], d['p2']): ax.plot([x, x], [y - 0.012, y + 0.012], color='#c00000', lw=0.6)
        arrow_dim(ax, p1, p2, lab, off=0.006, ldx=d.get('ldx', 0.0))
    elif k == 'y':
        x = d['at']; p1, p2 = (x, d['p1']), (x, d['p2'])
        if ext:
            for yv in (d['p1'], d['p2']): ax.plot([x - 0.012, x + 0.012], [yv, yv], color='#c00000', lw=0.6)
        ax.annotate('', xy=p2, xytext=p1, arrowprops=dict(arrowstyle='<->', color='#c00000', lw=0.9, shrinkA=0, shrinkB=0))
        dx, ha = (0.008, 'left') if d.get('side', 'right') == 'right' else (-0.008, 'right')
        ax.text(x + dx, (d['p1'] + d['p2']) / 2, lab, color='#c00000', fontsize=9, ha=ha, va='center', fontweight='bold', rotation=90,
                bbox=dict(boxstyle='round,pad=0.15', fc='white', ec='none', alpha=0.85))
    elif k == 'd':
        arrow_dim(ax, d['p1'], d['p2'], lab, off=0.01)
    elif k == 'z':
        x = d['at']; p1, p2 = (x, d['p1']), (x, d['p2'])
        for zv in (d['p1'], d['p2']): ax.plot([x - 0.012, x + 0.012], [zv, zv], color='#c00000', lw=0.6)
        ax.annotate('', xy=p2, xytext=p1, arrowprops=dict(arrowstyle='<->', color='#c00000', lw=0.9, shrinkA=0, shrinkB=0))
        ax.text(x + 0.008, (d['p1'] + d['p2']) / 2, lab, color='#c00000', fontsize=9, ha='left', va='center', fontweight='bold', rotation=90,
                bbox=dict(boxstyle='round,pad=0.15', fc='white', ec='none', alpha=0.85))

def plan_base(ax, show_c=False, faded=()):
    ax.add_patch(Rectangle((BX0, BY0), BX1 - BX0, BY1 - BY0, fc='#f3e6cf', ec='k', lw=1.0))
    box(ax, (CV[0], CV[1], CV[2], CV[3]), fc='#9a9a9a', ec='k', lw=0.6)                       # conveyor frame
    ax.add_patch(Rectangle((CV[0] + 0.01, BAND[0]), CV[1] - CV[0] - 0.02, BAND[1] - BAND[0], fc='#5c5c5c', ec='none'))  # belt band
    box(ax, P6_PLATE, fc='#3a3a3a', ec='k', lw=0.5)
    box(ax, M1, fc='#d9d9d9', ec='k', lw=0.6); box(ax, P6, fc='#d9d9d9', ec='k', lw=0.6)
    ax.add_patch(Circle(M1_J1, 0.006, fc='k')); ax.text(M1_J1[0] - 0.012, M1_J1[1], 'J1 axis', fontsize=7.5, va='center', ha='right')
    tower(ax, TY, '#e6d400'); tower(ax, TB, '#3d7cc9')
    box(ax, CR_A, fc='#e83e8c', ec='k', lw=0.6)
    if show_c: box(ax, CR_C, fc='#f5a3c7', ec='k', lw=0.6, ls='--')
    ax.text((CR_A[0] + CR_A[1]) / 2, CR_A[3] + 0.008, 'holder (load)', fontsize=7.5, ha='center')
    if show_c: ax.text((CR_C[0] + CR_C[1]) / 2, CR_C[3] + 0.008, 'holder after one index (unload)', fontsize=7.5, ha='center')
    ax.text((M1[0] + M1[1]) / 2, (M1[2] + M1[3]) / 2, 'M1 Pro\nbase', fontsize=7.5, ha='center', va='center')
    ax.text((P6[0] + P6[1]) / 2, (P6[2] + P6[3]) / 2, 'Pro 600\nbase', fontsize=7.5, ha='center', va='center')
    ax.text(yx + 0.008, yy, 'yellow\ntower', fontsize=7, ha='center', va='center'); ax.text(bx + 0.008, by, 'blue\ntower', fontsize=7, ha='center', va='center')
    ax.text(0.0, (BAND[1] + CV[3]) / 2, 'conveyor: motor housing strip', fontsize=7.5, ha='center', va='center', color='white')
    ax.text(0.10, (BAND[0] + BAND[1]) / 2 - 0.03, 'belt band (running surface)', fontsize=7.5, ha='center', va='center', color='white')
    ax.text(0, BY0 - 0.085, 'FRONT edge of the bench (the towers\' side)', fontsize=9, ha='center', va='top')
    ax.text(0, BY1 + 0.115, 'REAR edge (the conveyor\'s side)', fontsize=9, ha='center', va='bottom')
    ax.text(BX0 - 0.02, 0, 'LEFT edge\n(M1 Pro end)', fontsize=9, ha='right', va='center')
    ax.text(BX1 + 0.02, 0, 'RIGHT edge\n(Pro 600 end)', fontsize=9, ha='left', va='center')
    ax.set_aspect('equal'); ax.set_xlim(BX0 - 0.16, BX1 + 0.16); ax.set_ylim(BY0 - 0.13, BY1 + 0.15); ax.axis('off')

def fig_plan(name, groups, show_c=False, title=''):
    fig, ax = plt.subplots(figsize=(11.5, 6.0), dpi=160); plan_base(ax, show_c=show_c)
    for d in D:
        if d['fig'] == name and d['kind'] in ('x', 'y', 'd'): draw_dim(ax, d)
    ax.set_title(title + '   (plan view, seen from above; values in cm)', fontsize=11)
    fig.savefig(FIG / f'{name}.png', bbox_inches='tight'); plt.close(fig)

fig_plan('bench', [G0], title='Bench datum: D1-D4')
fig_plan('conveyor', [G1], title='Conveyor: D5-D12')
fig_plan('carrier', [G2], show_c=True, title='Carrier at load and after one index: D14-D22')
fig_plan('towers', [G3], title='Towers: D25-D34')
fig_plan('m1', [G4], title='M1 Pro base: D40-D48')
fig_plan('p6', [G5], title='Pro 600 base: D50-D56')

# ---- front elevation (heights)
fig, ax = plt.subplots(figsize=(11.5, 4.2), dpi=160)
ax.plot([BX0 - 0.1, BX1 + 0.1], [0, 0], color='k', lw=1.2); ax.text(BX1 + 0.11, 0, 'bench top', fontsize=6, va='center')
ax.add_patch(Rectangle((BX0, -0.03), BX1 - BX0, 0.03, fc='#f3e6cf', ec='k', lw=0.6))
ax.add_patch(Rectangle((CV[0], 0), CV[1] - CV[0], Z_BELT, fc='#9a9a9a', ec='k', lw=0.6)); ax.text(0.05, Z_BELT / 2, 'conveyor', fontsize=6, ha='center', va='center')
ax.add_patch(Rectangle((CR_A[0], Z_BELT), 0.18, 0.003, fc='#e83e8c', ec='k', lw=0.4))
for px in (CR_A[0], CR_A[1] - 0.045): ax.add_patch(Rectangle((px, Z_BELT + 0.003), 0.045, Z_POST - Z_BELT - 0.003, fc='#e83e8c', ec='k', lw=0.4))
ax.plot([CR_A[0] + 0.045, CR_A[1] - 0.045], [Z_SEAT, Z_SEAT], color='#8b0040', lw=1.0, ls='--'); ax.text(cl.BELT_A_X, Z_SEAT + 0.006, 'seat ring', fontsize=5.5, ha='center')
for t, c in ((TY, '#e6d400'), (TB, '#3d7cc9')):
    ax.add_patch(Rectangle((t[0], 0), t[1] - t[0], Z_TOWER, fc=c, ec='k', lw=0.6))
    for zs in SLOTS: ax.plot([t[0] + 0.01, t[1] - 0.01], [zs, zs], color='k', lw=0.5)
ax.add_patch(Rectangle((M1[0], 0), M1[1] - M1[0], 0.06, fc='#d9d9d9', ec='k', lw=0.6))
ax.add_patch(Rectangle((cl.M1PRO_XYZ[0] - 0.075, 0.06), 0.150, Z_M1_TOP - 0.06, fc='#e8e8e8', ec='k', lw=0.6)); ax.text(cl.M1PRO_XYZ[0], 0.40, 'M1 Pro\ncolumn', fontsize=6, ha='center')
ax.plot([cl.M1PRO_XYZ[0] - 0.02, cl.M1PRO_XYZ[0] + 0.30], [Z_M1_FLANGE_HOME, Z_M1_FLANGE_HOME], color='0.3', lw=0.8, ls=':'); ax.text(cl.M1PRO_XYZ[0] + 0.31, Z_M1_FLANGE_HOME, 'M1 flange at HOME', fontsize=5.5, va='center')
ax.add_patch(Rectangle((P6[0], 0), P6[1] - P6[0], Z_P6_TOP, fc='#d9d9d9', ec='k', lw=0.6)); ax.text((P6[0] + P6[1]) / 2, Z_P6_TOP + 0.01, 'Pro 600 base', fontsize=6, ha='center')
ax.plot([0.25, 0.42], [Z_P6_CUP_HOME, Z_P6_CUP_HOME], color='0.3', lw=0.8, ls=':'); ax.text(0.43, Z_P6_CUP_HOME, 'Pro 600 cup lip at HOME', fontsize=5.5, va='center')
for d in D:
    if d['fig'] == 'elev' and d['kind'] == 'z': draw_dim(ax, d)
ax.set_aspect('equal'); ax.set_xlim(BX0 - 0.12, BX1 + 0.35); ax.set_ylim(-0.05, 0.78); ax.axis('off')
ax.set_title('Heights, front elevation (values in cm above the bench top): D13, D23, D24, D36, D58, D60, D62, D63', fontsize=9)
fig.savefig(FIG / 'elev.png', bbox_inches='tight'); plt.close(fig)

# ---- part sketches: tower section, holder, fork
fig, axs = plt.subplots(1, 3, figsize=(11.5, 3.9), dpi=160)
ax = axs[0]; ax.set_title('Tower, side section (cm)', fontsize=8)
ax.add_patch(Rectangle((-0.075, 0), 0.011, Z_TOWER, fc='#e6d400', ec='k', lw=0.6)); ax.add_patch(Rectangle((0.064, 0), 0.011, Z_TOWER, fc='#e6d400', ec='k', lw=0.6))
ax.add_patch(Rectangle((-0.075, 0), 0.150, 0.005, fc='#e6d400', ec='k', lw=0.6))
for i, zs in enumerate(SLOTS):
    ax.add_patch(Rectangle((-0.064, zs - 0.006), 0.0065, 0.006, fc='#b8a800', ec='k', lw=0.4)); ax.add_patch(Rectangle((0.0575, zs - 0.006), 0.0065, 0.006, fc='#b8a800', ec='k', lw=0.4))
    ax.plot([-0.0635, 0.0635], [zs + 0.0008, zs + 0.0008], color='0.3', lw=1.2); ax.text(0.085, zs, f"D{39 - i}  {zs*100:.1f}", fontsize=6.5, color='#c00000', va='center', fontweight='bold')
ax.annotate('', xy=(-0.064, 0.02), xytext=(0.064, 0.02), arrowprops=dict(arrowstyle='<->', color='#c00000', lw=0.8)); ax.text(0, 0.023, 'D67 12.8 inner', fontsize=6.5, ha='center', color='#c00000', fontweight='bold')
ax.annotate('', xy=(-0.11, 0), xytext=(-0.11, Z_TOWER), arrowprops=dict(arrowstyle='<->', color='#c00000', lw=0.8)); ax.text(-0.115, 0.05, 'D36 10.0', fontsize=6.5, rotation=90, ha='right', va='center', color='#c00000', fontweight='bold')
ax.text(0.0, -0.012, 'ledge D68 0.65 wide; wafer rests on the ledges', fontsize=6, ha='center'); ax.set_aspect('equal'); ax.set_xlim(-0.14, 0.15); ax.set_ylim(-0.02, 0.115); ax.axis('off')
ax = axs[1]; ax.set_title('Holder, top view (cm)', fontsize=8)
ax.add_patch(Rectangle((-0.09, -0.035), 0.18, 0.07, fc='#e83e8c', ec='k', lw=0.6))
for px in (-0.09, 0.045): ax.add_patch(Rectangle((px, -0.035), 0.045, 0.07, fc='#c2276f', ec='k', lw=0.5))
ax.add_patch(Circle((0, 0), 0.064, fc='none', ec='k', lw=0.6, ls='--')); ax.add_patch(Circle((0, 0), 0.0575, fc='none', ec='k', lw=0.6, ls=':'))
ax.annotate('', xy=(-0.09, -0.05), xytext=(0.09, -0.05), arrowprops=dict(arrowstyle='<->', color='#c00000', lw=0.8)); ax.text(0, -0.062, 'D18 18.0', fontsize=6.5, ha='center', color='#c00000', fontweight='bold')
ax.annotate('', xy=(0.105, -0.035), xytext=(0.105, 0.035), arrowprops=dict(arrowstyle='<->', color='#c00000', lw=0.8)); ax.text(0.11, 0, 'D19 7.0', fontsize=6.5, rotation=90, va='center', color='#c00000', fontweight='bold')
ax.text(0, 0.045, 'D66: seat ring 11.5 inner (dotted) / lip 12.8 (dashed)', fontsize=6, ha='center'); ax.text(0, 0, 'posts 4.5 tall (D24)\nseat ring at 4.3 (D23)', fontsize=6, ha='center', va='center')
ax.set_aspect('equal'); ax.set_xlim(-0.13, 0.14); ax.set_ylim(-0.08, 0.06); ax.axis('off')
ax = axs[2]; ax.set_title('Fork, top view (cm)', fontsize=8)
ax.add_patch(Rectangle((-0.0125, -0.0291), 0.1895, 0.0582, fc='#5aa9e6', ec='k', lw=0.6)); ax.add_patch(Rectangle((0.10, -0.012), 0.077, 0.024, fc='white', ec='none'))
ax.add_patch(Circle((0, 0), 0.008, fc='k')); ax.text(0, -0.04, 'wrist (J4)\nshaft centre', fontsize=6, ha='center', va='top')
ax.add_patch(Circle((cl.FORK_SEAT_X, 0), WAFER_R, fc='none', ec='0.3', lw=0.7, ls='--')); ax.add_patch(Circle((cl.FORK_SEAT_X, 0), 0.004, fc='0.3'))
ax.annotate('', xy=(0, 0.075), xytext=(cl.FORK_SEAT_X, 0.075), arrowprops=dict(arrowstyle='<->', color='#c00000', lw=0.8)); ax.text(cl.FORK_SEAT_X / 2, 0.079, f'D70 {cl.FORK_SEAT_X*100:.1f}  (KEY)', fontsize=6.5, ha='center', color='#c00000', fontweight='bold')
ax.annotate('', xy=(0, 0.095), xytext=(cl.FORK_SEAT_X + 0.03, 0.095), arrowprops=dict(arrowstyle='<->', color='#c00000', lw=0.8)); ax.text((cl.FORK_SEAT_X + 0.03) / 2, 0.099, f'D71 {(cl.FORK_SEAT_X+0.03)*100:.1f}', fontsize=6.5, ha='center', color='#c00000', fontweight='bold')
ax.annotate('', xy=(0.20, -0.0291), xytext=(0.20, 0.0291), arrowprops=dict(arrowstyle='<->', color='#c00000', lw=0.8)); ax.text(0.205, 0, 'D69 5.8', fontsize=6.5, rotation=90, va='center', color='#c00000', fontweight='bold')
ax.text(cl.FORK_SEAT_X, -0.075, 'wafer (D64 12.7) resting on the fork', fontsize=6, ha='center'); ax.set_aspect('equal'); ax.set_xlim(-0.09, 0.25); ax.set_ylim(-0.10, 0.11); ax.axis('off')
fig.savefig(FIG / 'parts.png', bbox_inches='tight'); plt.close(fig)

json.dump(D, open(HERE / 'dims.json', 'w'), indent=1)
print(f"{len(D)} dimensions; figures in {FIG}")
for d in D:
    if d['kind'] != 't': print(f"  {d['id']:4s} {d['value_cm']:6.1f}  {d['text'][:60]}")
    else: print(f"  {d['id']:4s} {d['value_cm']:6.1f}  {d['text'][:60]}  (table only)")
