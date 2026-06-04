"""
Annotated diagram of the create_redan() input parameters.
Run:  python draw_redan_params.py
Saves:  redan_params.png
"""

import math
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# ── demo values ───────────────────────────────────────────────────────────────
r_top      = 2.36
z_top      = 5.50
r_lower    = 1.50
z_knee     = 1.60
z_bottom   = -0.10
z_shoulder = 3.00
thickness  = 0.12   # exaggerated for visibility

# ── outer profile (with shoulder) ────────────────────────────────────────────
outer = [
    (r_top,   z_top),
    (r_top,   z_shoulder),
    (r_lower, z_knee),
    (r_lower, z_bottom),
]

# ── mitre inner offset (inward, i.e. thickness_side="in") ────────────────────
def mitre_inner(pts, t):
    result = []
    for i, (r, z) in enumerate(pts):
        if i == 0:
            result.append((r - t, z))
        elif i == len(pts) - 1:
            result.append((r, z + t))
        else:
            pr, pz = pts[i-1]; nr, nz = pts[i+1]
            d1 = (r-pr, z-pz); L1 = math.hypot(*d1); d1 = (d1[0]/L1, d1[1]/L1)
            d2 = (nr-r, nz-z); L2 = math.hypot(*d2); d2 = (d2[0]/L2, d2[1]/L2)
            n1 = ( d1[1], -d1[0])
            n2 = ( d2[1], -d2[0])
            p1 = (r + t*n1[0], z + t*n1[1])
            p2 = (r + t*n2[0], z + t*n2[1])
            a, b = d1[0], -d2[0]; c, d = d1[1], -d2[1]
            det = a*d - b*c
            if abs(det) < 1e-12:
                result.append(((p1[0]+p2[0])/2, (p1[1]+p2[1])/2))
            else:
                rx, rz = p2[0]-p1[0], p2[1]-p1[1]
                s = (rx*d - b*rz)/det
                result.append((p1[0]+s*d1[0], p1[1]+s*d1[1]))
    return result

inner = mitre_inner(outer, thickness)

ring_r = [p[0] for p in outer] + [p[0] for p in reversed(inner)]
ring_z = [p[1] for p in outer] + [p[1] for p in reversed(inner)]

# ─────────────────────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(10, 11))
ax.set_aspect("equal")

# ── wall fill ─────────────────────────────────────────────────────────────────
ax.fill(ring_r, ring_z, color="#b0c8e8", alpha=0.85, zorder=2)
ax.plot(ring_r + [ring_r[0]], ring_z + [ring_z[0]],
        color="#2255aa", lw=1.5, zorder=3)

# ── Z axis ────────────────────────────────────────────────────────────────────
ax.axvline(0, color="black", lw=0.9, ls="--", alpha=0.35, zorder=0)
ax.text(0.04, z_top + 0.22, "axis of revolution", fontsize=7, color="gray", va="bottom")

# ─── colours ─────────────────────────────────────────────────────────────────
C_R   = "#c0392b"   # radii
C_Z   = "#1a5276"   # heights
C_T   = "#6c3483"   # thickness
C_P   = "#1e8449"   # penetration
C_DIM = "#555555"   # generic dim lines

# ─── helpers ─────────────────────────────────────────────────────────────────
def arrow(ax, x1, y1, x2, y2, color, lw=1.1):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="<->", color=color, lw=lw), zorder=5)

def dotted(ax, x1, y1, x2, y2, color="gray", lw=0.8, ls=":"):
    ax.plot([x1, x2], [y1, y2], color=color, lw=lw, ls=ls, zorder=1)

def label(ax, x, y, txt, color, ha="left", va="center", fs=8.5, bg=True):
    kw = dict(ha=ha, va=va, fontsize=fs, color=color, zorder=7)
    if bg:
        kw["bbox"] = dict(fc="white", ec="none", pad=1.5)
    ax.text(x, y, txt, **kw)

# ══════════════════════════════════════════════════════════════════════════════
#  RADII  — horizontal arrows from axis to each anchor, staggered heights
# ══════════════════════════════════════════════════════════════════════════════

# Each radius arrow is drawn at a slightly different z so they don't overlap.
# We draw them between the axis (r=0) and the outer wall surface.

r_arrows = [
    # (r_value, z_draw, label_text)
    (r_top,      z_top      + 0.00, "r_top"),
    (r_top,      z_shoulder + 0.00, "r_top"),   # same value, shoulder row
    (r_lower,    z_knee     + 0.00, "r_lower"),
    (r_lower,    z_bottom   + 0.00, "r_lower"),
]

# Offset each arrow below its anchor so they're readable
r_arrow_offsets = [-0.18, -0.18, -0.18, 0.18]
r_arrow_data = [
    (r_top,   z_top      + r_arrow_offsets[0], "r_top",   "A"),
    (r_top,   z_shoulder + r_arrow_offsets[1], "r_top",   "shoulder"),
    (r_lower, z_knee     + r_arrow_offsets[2], "r_lower", "B"),
    (r_lower, z_bottom   + r_arrow_offsets[3], "r_lower", "C"),
]

for (r, za, r_lbl, pt_lbl) in r_arrow_data:
    arrow(ax, 0, za, r, za, C_R, lw=1.0)
    ax.text(r/2, za + 0.06, r_lbl, ha="center", va="bottom",
            fontsize=8, color=C_R,
            bbox=dict(fc="white", ec="none", pad=1))

# ══════════════════════════════════════════════════════════════════════════════
#  HEIGHTS — vertical markers on the left of the axis
# ══════════════════════════════════════════════════════════════════════════════

LEFT = -0.18   # x position of the height tick line

heights = [
    (z_top,      "z_top",              True),
    (z_shoulder, "z_shoulder\n(optional)", True),
    (z_knee,     "z_knee",             True),
    (z_bottom,   "z_bottom",           True),
]

for (z, lbl, show_dot) in heights:
    # short tick on the axis line
    ax.plot([LEFT - 0.04, LEFT + 0.04], [z, z], color=C_Z, lw=1.2, zorder=5)
    # dotted guide to the wall
    ax.plot([LEFT + 0.04, r_top + 0.05], [z, z],
            color=C_Z, lw=0.6, ls=":", alpha=0.5, zorder=1)
    # label to the left
    ax.text(LEFT - 0.07, z, lbl, ha="right", va="center",
            fontsize=8, color=C_Z,
            bbox=dict(fc="white", ec="none", pad=1))

# Vertical span arrows on the axis showing the four heights
# We'll draw them as a stacked set of <-> arrows sharing the same x
X_SPAN = LEFT - 0.02

# z_top → 0 (just a reference bar)
# It's cleaner to just leave the ticks; add one collective bracket
for (za, zb) in [(z_bottom, z_knee), (z_knee, z_shoulder), (z_shoulder, z_top)]:
    ax.plot([X_SPAN]*2, [za, zb], color=C_Z, lw=1.0, zorder=4)
    ax.plot([X_SPAN - 0.025, X_SPAN + 0.025], [za, za], color=C_Z, lw=1.0, zorder=4)
    ax.plot([X_SPAN - 0.025, X_SPAN + 0.025], [zb, zb], color=C_Z, lw=1.0, zorder=4)

# ══════════════════════════════════════════════════════════════════════════════
#  ANCHOR POINTS  A, shoulder, B, C
# ══════════════════════════════════════════════════════════════════════════════
anchors = [
    ("A",        r_top,   z_top),
    ("shoulder", r_top,   z_shoulder),
    ("B",        r_lower, z_knee),
    ("C",        r_lower, z_bottom),
]
for (lbl, r, z) in anchors:
    ax.scatter([r], [z], s=50, color="#cc2222", zorder=6)
    ax.text(r + 0.07, z, lbl, fontsize=9.5, fontweight="bold",
            color="#cc2222", va="center", zorder=7,
            bbox=dict(fc="white", ec="none", pad=1))

# ══════════════════════════════════════════════════════════════════════════════
#  THICKNESS  — perpendicular arrow on the taper section
# ══════════════════════════════════════════════════════════════════════════════
ro = (r_top + r_lower) / 2
zo = (z_shoulder + z_knee) / 2
dr = r_lower - r_top; dz = z_knee - z_shoulder
L  = math.hypot(dr, dz); dr /= L; dz /= L
nx, nz = dz, -dr   # inward normal

pr1, pz1 = ro, zo
pr2, pz2 = ro + thickness * nx, zo + thickness * nz

arrow(ax, pr1, pz1, pr2, pz2, C_T, lw=1.4)
ax.text((pr1+pr2)/2 - 0.18, (pz1+pz2)/2 + 0.12,
        "thickness", ha="center", va="bottom",
        fontsize=8.5, color=C_T,
        bbox=dict(fc="white", ec=C_T, lw=0.6, pad=2))

# ══════════════════════════════════════════════════════════════════════════════
#  PENETRATION schematic
# ══════════════════════════════════════════════════════════════════════════════
pen_r  = (r_top + r_lower) / 2 + 0.06
pen_z  = (z_shoulder + z_knee) / 2 + 0.40
pen_rd = 0.13
circle = plt.Circle((pen_r, pen_z), pen_rd, fill=False,
                     edgecolor=C_P, lw=1.3, ls="--", zorder=5)
ax.add_patch(circle)
ax.annotate("penetration\n(x, y, r)",
            xy=(pen_r + pen_rd, pen_z),
            xytext=(pen_r + 0.35, pen_z + 0.38),
            fontsize=7.5, color=C_P,
            arrowprops=dict(arrowstyle="->", color=C_P, lw=0.9),
            bbox=dict(fc="white", ec="none"))

# ══════════════════════════════════════════════════════════════════════════════
#  NOTES — thickness_side & z_offset
# ══════════════════════════════════════════════════════════════════════════════
ax.text(0.55, 4.70,
        'thickness_side = "in"\n(wall grows toward axis;\nA–B–C is the outer surface)',
        fontsize=7.5, color="#7d3c98",
        bbox=dict(fc="#f5eef8", ec="#7d3c98", lw=0.7, pad=4))

ax.annotate("z_offset — rigid\nvertical shift applied\nto the whole solid",
            xy=(0.15, z_bottom + 0.05),
            xytext=(0.10, z_bottom - 0.55),
            fontsize=7.5, color=C_DIM,
            arrowprops=dict(arrowstyle="->", color=C_DIM, lw=0.9),
            bbox=dict(fc="white", ec="none"))

# ══════════════════════════════════════════════════════════════════════════════
#  AXES & TITLE
# ══════════════════════════════════════════════════════════════════════════════
ax.set_xlim(-0.55, r_top + 0.65)
ax.set_ylim(z_bottom - 0.90, z_top + 0.60)
ax.set_xlabel("r  [m]", fontsize=9)
ax.set_ylabel("z  [m]", fontsize=9)
ax.set_title("create_redan() — input parameters\n"
             "(half cross-section, revolved 360° about Z axis)",
             fontsize=11, fontweight="bold", pad=10)
ax.tick_params(labelsize=8)
ax.grid(True, ls=":", lw=0.4, alpha=0.35)

plt.tight_layout()
plt.savefig("redan_params.png", dpi=170, bbox_inches="tight")
print("Saved redan_params.png")
plt.show()
