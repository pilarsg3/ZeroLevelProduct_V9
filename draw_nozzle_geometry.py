"""
Annotated diagram of the primary pump nozzle geometry.
Run standalone: python draw_nozzle_geometry.py
"""
import math
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import Arc, FancyArrowPatch, Wedge
from matplotlib.path import Path

# ── Demo parameters ─────────────────────────────────────────────────────
arc_deg    = 105.0
R_bend     = 0.460
L_inlet    = 0.20        # exaggerated for visual clarity (actual 0.05 m)
L_leg      = 0.600
r_pipe     = 0.460 / 2   # 0.230 m
wall_t     = 0.025
barrel_r   = 1.350 / 2   # 0.675 m
barrel_h   = 12.0
nozzle_z   = 0.450
barrel_wt  = 0.040

arc_rad = math.radians(arc_deg)

# ── Nozzle centerline (local path frame) ────────────────────────────────
#   Inlet goes in local +Y from (0,0).  Arc bends toward +X.
#   After _place_right_nozzle the local +Y maps to world +X (radially out).

arc_cx, arc_cy = R_bend, L_inlet
n_arc = 200
angles = np.linspace(math.pi, math.pi - arc_rad, n_arc)
arc_x  = arc_cx + R_bend * np.cos(angles)
arc_y  = arc_cy + R_bend * np.sin(angles)

P_arc_end = (arc_x[-1], arc_y[-1])
tan_x = math.sin(arc_rad)
tan_y = math.cos(arc_rad)          # negative → outlet tilts back slightly

P_leg_end = (P_arc_end[0] + L_leg * tan_x,
             P_arc_end[1] + L_leg * tan_y)

cl_x = np.concatenate([[0], [0],      arc_x, [P_leg_end[0]]])
cl_y = np.concatenate([[0], [L_inlet], arc_y, [P_leg_end[1]]])

# ── Pipe wall offset ─────────────────────────────────────────────────────
def pipe_offsets(xs, ys, r):
    dx = np.gradient(xs); dy = np.gradient(ys)
    ln = np.hypot(dx, dy) + 1e-15
    nx = -dy / ln; ny = dx / ln
    return (xs + r * nx, ys + r * ny), (xs - r * nx, ys - r * ny)

(out_x, out_y), (in_x, in_y) = pipe_offsets(cl_x, cl_y, r_pipe)
(out_xi, out_yi), (in_xi, in_yi) = pipe_offsets(cl_x, cl_y, r_pipe - wall_t)

# Filled pipe annulus polygon
outer_verts = np.column_stack([out_x,   out_y])
inner_verts = np.column_stack([in_x[::-1], in_y[::-1]])
pipe_poly = mpatches.Polygon(
    np.vstack([outer_verts, inner_verts]),
    closed=True, fc='#b8d8f8', ec='#2266aa', lw=1.8, zorder=3)

inner_bore_verts = np.column_stack([out_xi, out_yi])
inner_bore_revt  = np.column_stack([in_xi[::-1], in_yi[::-1]])
bore_poly = mpatches.Polygon(
    np.vstack([inner_bore_verts, inner_bore_revt]),
    closed=True, fc='white', ec='none', zorder=4)

# ── Figure layout ────────────────────────────────────────────────────────
fig = plt.figure(figsize=(17, 9), facecolor='white')
fig.suptitle('Primary Pump — Nozzle Geometry & Parameters', fontsize=15,
             fontweight='bold', y=0.97)

ax  = fig.add_axes([0.04, 0.06, 0.60, 0.86])   # main plan view
ax2 = fig.add_axes([0.68, 0.52, 0.30, 0.40])   # pipe cross-section
ax3 = fig.add_axes([0.68, 0.06, 0.30, 0.38])   # barrel side view

RED   = '#c0392b'
GREEN = '#1a7a3a'
BLUE  = '#1a4fa0'
ANNO  = dict(fontsize=9.5, fontweight='bold', ha='center', va='center',
             bbox=dict(fc='white', ec='none', pad=1.5))

# ════════════════════════════════════════════════════════════════════════
# Panel 1 – Plan view (top-down, local frame)
# ════════════════════════════════════════════════════════════════════════
ax.set_aspect('equal')
ax.axis('off')
ax.set_title('Nozzle Plan View  (top-down, local path frame)\n'
             'Local +Y  →  World +X  (radially outward from barrel)',
             fontsize=10, pad=6)

# Barrel wall strip (left side)
bw = 0.12
barrel_patch = mpatches.FancyBboxPatch(
    (-bw - r_pipe, -0.05), bw, P_leg_end[1] + r_pipe + 0.25,
    boxstyle='square,pad=0', fc='#d0d0d0', ec='#555', lw=1.5, zorder=1)
ax.add_patch(barrel_patch)
ax.text(-bw / 2 - r_pipe, (P_leg_end[1]) / 2, 'barrel\nwall',
        fontsize=8, ha='center', va='center', color='#444',
        rotation=90)

# Barrel inner surface (dashed)
ax.axvline(0, color='#777', lw=1.2, ls='--', zorder=2)
ax.text(0.01, -0.04, 'barrel inner surface  (x=0)', fontsize=8,
        color='#777', va='top')

# Pipe solid
ax.add_patch(pipe_poly)
ax.add_patch(bore_poly)

# Centerline
ax.plot(cl_x, cl_y, color='#555', lw=1, ls=':', zorder=5, alpha=0.7)

# ── Arc center dot ──
ax.plot(arc_cx, arc_cy, 'o', color=RED, ms=5, zorder=6)

# ─── L_inlet annotation ──────────────────────────────────────────────
x_ann = r_pipe + 0.07
ax.annotate('', xy=(x_ann, L_inlet), xytext=(x_ann, 0),
            arrowprops=dict(arrowstyle='<->', color=RED, lw=1.6), zorder=7)
ax.text(x_ann + 0.10, L_inlet / 2,
        'L_inlet\n(straight\ninlet leg)', color=RED, fontsize=9,
        fontweight='bold', va='center')
# tick marks
for yy in [0, L_inlet]:
    ax.plot([x_ann - 0.02, x_ann + 0.02], [yy, yy], color=RED, lw=1.2, zorder=7)

# ─── R_bend annotation ───────────────────────────────────────────────
# Dashed radius line from arc center to mid-arc point
mid_a  = math.pi - arc_rad / 2
rx = arc_cx + R_bend * math.cos(mid_a)
ry = arc_cy + R_bend * math.sin(mid_a)
ax.plot([arc_cx, rx], [arc_cy, ry], '--', color=BLUE, lw=1.5, zorder=6)
ax.text((arc_cx + rx) / 2 - 0.03, (arc_cy + ry) / 2 + 0.04,
        'R_bend', color=BLUE, fontsize=9.5, fontweight='bold',
        ha='right', va='bottom',
        bbox=dict(fc='white', ec='none', pad=1))

# ─── arc_deg annotation ──────────────────────────────────────────────
theta2_deg = 180.0
theta1_deg = 180.0 - arc_deg
ann_r = R_bend * 0.48
wedge = Wedge((arc_cx, arc_cy), ann_r, theta1_deg, theta2_deg,
              fc='#ffe0b2', ec=GREEN, lw=1.4, alpha=0.7, zorder=5)
ax.add_patch(wedge)
mid_angle_deg = (theta1_deg + theta2_deg) / 2
mid_a2 = math.radians(mid_angle_deg)
lbl_x = arc_cx + (ann_r + 0.08) * math.cos(mid_a2)
lbl_y = arc_cy + (ann_r + 0.08) * math.sin(mid_a2)
ax.text(lbl_x, lbl_y, f'arc_deg\n({arc_deg:.0f}°)', color=GREEN,
        fontsize=9, fontweight='bold', ha='left', va='center',
        bbox=dict(fc='white', ec='none', pad=1))

# ─── L_leg annotation ────────────────────────────────────────────────
leg_nx = -tan_y        # normal to outlet leg
leg_ny =  tan_x
off = r_pipe + 0.09
lx1 = P_arc_end[0] + off * leg_nx
ly1 = P_arc_end[1] + off * leg_ny
lx2 = P_leg_end[0] + off * leg_nx
ly2 = P_leg_end[1] + off * leg_ny
ax.annotate('', xy=(lx2, ly2), xytext=(lx1, ly1),
            arrowprops=dict(arrowstyle='<->', color=RED, lw=1.6), zorder=7)
mid_lx = (lx1 + lx2) / 2 + 0.09 * leg_nx
mid_ly = (ly1 + ly2) / 2 + 0.09 * leg_ny
ax.text(mid_lx, mid_ly, 'L_leg\n(outlet leg)', color=RED,
        fontsize=9, fontweight='bold', ha='center', va='center',
        bbox=dict(fc='white', ec='none', pad=1.5))
for pt in [(lx1, ly1), (lx2, ly2)]:
    perp_x = -leg_ny * 0.025
    perp_y =  leg_nx * 0.025
    ax.plot([pt[0]-perp_x, pt[0]+perp_x],
            [pt[1]-perp_y, pt[1]+perp_y], color=RED, lw=1.2, zorder=7)

# ─── r_pipe label on pipe wall ───────────────────────────────────────
# Arrow from centerline to pipe outer wall at inlet midpoint
mid_y_inlet = L_inlet * 0.5
ax.annotate('', xy=(-r_pipe, mid_y_inlet), xytext=(0, mid_y_inlet),
            arrowprops=dict(arrowstyle='->', color='#880088', lw=1.5), zorder=7)
ax.text(-r_pipe * 0.5, mid_y_inlet + 0.04, 'r_pipe',
        color='#880088', fontsize=9, fontweight='bold', ha='center')

# ─── wall_t label ────────────────────────────────────────────────────
wt_y = mid_y_inlet - 0.07
ax.annotate('', xy=(-r_pipe, wt_y), xytext=(-(r_pipe - wall_t), wt_y),
            arrowprops=dict(arrowstyle='<->', color='darkorange', lw=1.5), zorder=7)
ax.text(-r_pipe + wall_t * 0.5, wt_y - 0.05, 'wall_t',
        color='darkorange', fontsize=9, fontweight='bold', ha='center')

# ─── outlet direction label ──────────────────────────────────────────
ax.annotate('', xy=(P_leg_end[0] + 0.15 * tan_x, P_leg_end[1] + 0.15 * tan_y),
            xytext=P_leg_end,
            arrowprops=dict(arrowstyle='->', color='#555', lw=1.5, mutation_scale=14))
ax.text(P_leg_end[0] + 0.22 * tan_x, P_leg_end[1] + 0.22 * tan_y,
        'outlet\ndirection', fontsize=8, color='#555', ha='center', va='center',
        bbox=dict(fc='white', ec='none', pad=1))

ax.set_xlim(-bw - r_pipe - 0.05, P_leg_end[0] + r_pipe + 0.45)
ax.set_ylim(-0.12, P_leg_end[1] + r_pipe + 0.25)

# ════════════════════════════════════════════════════════════════════════
# Panel 2 – Pipe cross-section
# ════════════════════════════════════════════════════════════════════════
ax2.set_aspect('equal')
ax2.axis('off')
ax2.set_title('Pipe Cross-Section\n(perpendicular to centerline)', fontsize=10)

outer = plt.Circle((0, 0), r_pipe,          fc='#b8d8f8', ec='#2266aa', lw=2.0)
inner = plt.Circle((0, 0), r_pipe - wall_t, fc='white',   ec='#2266aa', lw=1.5)
ax2.add_patch(outer)
ax2.add_patch(inner)

# r_pipe arrow
ax2.annotate('', xy=(r_pipe, 0), xytext=(0, 0),
             arrowprops=dict(arrowstyle='->', color='#880088', lw=1.8))
ax2.text(r_pipe * 0.52, 0.018, 'r_pipe', color='#880088',
         fontsize=10, fontweight='bold', ha='center', va='bottom')

# wall_t arrow (on upper-right quadrant)
ang = math.radians(50)
ax2.annotate('', xy=(r_pipe * math.cos(ang), r_pipe * math.sin(ang)),
             xytext=((r_pipe - wall_t) * math.cos(ang), (r_pipe - wall_t) * math.sin(ang)),
             arrowprops=dict(arrowstyle='<->', color='darkorange', lw=1.8))
mid_r = r_pipe - wall_t / 2
ax2.text(mid_r * math.cos(ang) + 0.015, mid_r * math.sin(ang) + 0.012,
         'wall_t', color='darkorange', fontsize=10, fontweight='bold',
         ha='left', va='bottom')

# Center cross
ax2.plot(0, 0, '+', color='black', ms=8, mew=1.5)

ax2.set_xlim(-r_pipe * 1.6, r_pipe * 1.6)
ax2.set_ylim(-r_pipe * 1.6, r_pipe * 1.6)

# ════════════════════════════════════════════════════════════════════════
# Panel 3 – Barrel side view (shows nozzle_z)
# ════════════════════════════════════════════════════════════════════════
ax3.set_aspect('equal')
ax3.axis('off')
ax3.set_title('Barrel Side View\n(shows nozzle_z placement)', fontsize=10)

draw_h  = 3.5    # scaled barrel height for display
draw_r  = 0.7
scale   = draw_h / barrel_h
nz_draw = nozzle_z * scale

# Barrel rectangle
barrel_rect2 = mpatches.FancyBboxPatch(
    (-draw_r, 0), draw_r * 2, draw_h,
    boxstyle='square,pad=0', fc='#e8e8e8', ec='#444', lw=1.8)
ax3.add_patch(barrel_rect2)

# Nozzle horizontal lines (right side)
nozzle_w = draw_r * 0.55
for dy in [-r_pipe * scale * 6, r_pipe * scale * 6]:
    ax3.plot([draw_r, draw_r + nozzle_w],
             [nz_draw + dy, nz_draw + dy], color='#2266aa', lw=1.8)
ax3.plot([draw_r + nozzle_w, draw_r + nozzle_w],
         [nz_draw - r_pipe * scale * 6, nz_draw + r_pipe * scale * 6],
         color='#2266aa', lw=1.8)
# nozzle_z arrow
ax3.annotate('', xy=(draw_r * 1.8, nz_draw), xytext=(draw_r * 1.8, 0),
             arrowprops=dict(arrowstyle='<->', color=RED, lw=1.5))
ax3.text(draw_r * 2.1, nz_draw / 2, 'nozzle_z', color=RED,
         fontsize=9, fontweight='bold', va='center')
# tick marks for nozzle_z
ax3.plot([draw_r * 1.7, draw_r * 1.9], [0,       0],       color=RED, lw=1.2)
ax3.plot([draw_r * 1.7, draw_r * 1.9], [nz_draw, nz_draw], color=RED, lw=1.2)

# Centerline dashed
ax3.axhline(nz_draw, xmin=0.1, xmax=0.9, color='gray', lw=1, ls='--')

ax3.set_xlim(-draw_r * 1.2, draw_r * 2.8)
ax3.set_ylim(-0.15, draw_h + 0.2)

# ── Legend / parameter key ───────────────────────────────────────────────
legend_lines = [
    mpatches.Patch(fc='#b8d8f8', ec='#2266aa', lw=1.5, label='Pipe wall'),
    plt.Line2D([0], [0], color='#555', ls=':', lw=1.5, label='Centerline'),
    plt.Line2D([0], [0], color=RED,   lw=1.5, label='L_inlet / L_leg / nozzle_z'),
    plt.Line2D([0], [0], color=BLUE,  lw=1.5, ls='--', label='R_bend'),
    mpatches.Patch(fc='#ffe0b2', ec=GREEN, lw=1.4, label='arc_deg'),
    plt.Line2D([0], [0], color='#880088', lw=1.5, label='r_pipe'),
    plt.Line2D([0], [0], color='darkorange', lw=1.5, label='wall_t'),
]
fig.legend(handles=legend_lines, loc='lower left', bbox_to_anchor=(0.04, 0.01),
           ncol=4, fontsize=8.5, framealpha=0.9, edgecolor='#aaa')

plt.savefig('nozzle_geometry.png', dpi=160, bbox_inches='tight',
            facecolor='white')
print("Saved → nozzle_geometry.png")
plt.show()
