"""
Annotated diagram of the create_strongback() input parameters.
Run:  python draw_strongback_params.py
Saves:  strongback_params.png
"""

import math
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# ── Demo values (from __main__ in components_premade_strongback.py) ───────────
total_height           = 1.242
flange_radius          = 2.684
skirt_outer_radius     = 3.030
skirt_inner_radius     = 2.243
skirt_height           = 0.436
taper_bottom_z         = 0.356
bore_radius            = 0.303
small_hole_radius      = 0.0755
small_hole_count       = 6
small_hole_placement_r = 0.900

H   = total_height
fr  = flange_radius
so  = skirt_outer_radius
si  = skirt_inner_radius
sh  = skirt_height
tb  = taper_bottom_z
br  = bore_radius
shr = small_hole_radius
shn = small_hole_count
shp = small_hole_placement_r

# ── Profile polygon (half cross-section, r horizontal, z vertical) ────────────
profile_r = [0.0, fr,  so,   so,   si,   si,  0.0]
profile_z = [H,   H,   tb,   0.0,  0.0,  sh,  sh ]

# ── Figure ────────────────────────────────────────────────────────────────────
fig, (ax, ax2) = plt.subplots(1, 2, figsize=(16, 9))
fig.suptitle("create_strongback() — input parameters", fontsize=13, fontweight="bold", y=0.98)

C_R = "#c0392b"   # radii
C_Z = "#1a5276"   # heights
C_H = "#1e8449"   # hole parameters

def arrow(a, x1, y1, x2, y2, color, lw=1.1):
    a.annotate("", xy=(x2, y2), xytext=(x1, y1),
               arrowprops=dict(arrowstyle="<->", color=color, lw=lw), zorder=5)

def lbl(a, x, y, txt, color, ha="left", va="center", fs=8.0):
    a.text(x, y, txt, ha=ha, va=va, fontsize=fs, color=color, zorder=7,
           bbox=dict(fc="white", ec="none", pad=1.5))

# ════════════════════════════════════════════════════════════════════════════════
# PANEL 1 — half cross-section
# ════════════════════════════════════════════════════════════════════════════════
ax.set_aspect("equal")
ax.set_title("Half cross-section  (revolved 360° about Z axis)", fontsize=10, pad=8)

# Solid material
ax.fill(profile_r, profile_z, color="#b0c8e8", alpha=0.85, zorder=2)
ax.plot(profile_r + [profile_r[0]], profile_z + [profile_z[0]],
        color="#2255aa", lw=1.5, zorder=3)

# Bore cut (white overlay — full height)
ax.fill([0, br, br, 0], [0, 0, H, H], color="white", zorder=4)
ax.plot([br, br], [0, H], color="#555", lw=1.0, ls="--", zorder=5)

# One small hole shown in the upper solid section
hole_zc = (sh + H) / 2
ax.add_patch(plt.Circle((shp, hole_zc), shr,
             fc="white", ec=C_H, lw=1.3, ls="--", zorder=5))

# Axis line
ax.axvline(0, color="gray", lw=0.9, ls="--", alpha=0.35, zorder=0)
ax.text(0.03, H + 0.06, "axis", fontsize=7, color="gray", va="bottom")

# ── Height ticks (left of axis) ───────────────────────────────────────────────
LX = -0.22
for z, name, color in [(H,  "total_height",   C_Z),
                        (sh, "skirt_height",   C_Z),
                        (tb, "taper_bottom_z", C_Z),
                        (0,  "z = 0",          C_Z)]:
    ax.plot([LX - 0.04, LX + 0.04], [z, z], color=color, lw=1.3, zorder=5)
    ax.plot([LX + 0.04, so + 0.05], [z, z], color=color, lw=0.5, ls=":", alpha=0.4)
    lbl(ax, LX - 0.07, z, name, color, ha="right", fs=8)

# ── Radius arrows ─────────────────────────────────────────────────────────────
# bore_radius — in the bore gap near top
z_br_arrow = H * 0.85
arrow(ax, 0, z_br_arrow, br, z_br_arrow, C_R)
lbl(ax, br / 2, z_br_arrow + 0.035, "bore_radius", C_R, ha="center", fs=7.5)

# flange_radius — above top face
z_fr = H + 0.13
arrow(ax, 0, z_fr, fr, z_fr, C_R)
lbl(ax, fr / 2, z_fr + 0.048, "flange_radius", C_R, ha="center")
ax.plot([0,  0 ], [H, z_fr], color=C_R, lw=0.5, ls=":")
ax.plot([fr, fr], [H, z_fr], color=C_R, lw=0.5, ls=":")

# skirt_outer_radius — below z=0
z_so = -0.14
arrow(ax, 0, z_so, so, z_so, C_R)
lbl(ax, so / 2, z_so - 0.068, "skirt_outer_radius", C_R, ha="center")
ax.plot([0,  0 ], [0, z_so], color=C_R, lw=0.5, ls=":")
ax.plot([so, so], [0, z_so], color=C_R, lw=0.5, ls=":")

# skirt_inner_radius — further below
z_si = -0.26
arrow(ax, 0, z_si, si, z_si, C_R)
lbl(ax, si / 2, z_si - 0.068, "skirt_inner_radius", C_R, ha="center")
ax.plot([si, si], [0, z_si], color=C_R, lw=0.5, ls=":")

# small_hole_placement_r — horizontal arrow below the hole
z_shp = hole_zc - 0.15
arrow(ax, 0, z_shp, shp, z_shp, C_H)
lbl(ax, shp / 2, z_shp - 0.068, "small_hole_placement_r", C_H, ha="center", fs=7.5)

# small_hole_radius — annotation pointing to circle edge
ax.annotate("small_hole_radius",
            xy=(shp + shr, hole_zc),
            xytext=(shp + 0.48, hole_zc + 0.18),
            fontsize=7.5, color=C_H,
            arrowprops=dict(arrowstyle="->", color=C_H, lw=0.9),
            bbox=dict(fc="white", ec="none"))

lbl(ax, shp + 0.08, hole_zc + 0.30,
    f"small_hole_count = {shn}  (equally spaced)", C_H, ha="left", fs=7.5)

ax.set_xlim(-0.72, so + 0.90)
ax.set_ylim(-0.52, H + 0.34)
ax.set_xlabel("r  [m]", fontsize=9)
ax.set_ylabel("z  [m]", fontsize=9)
ax.tick_params(labelsize=8)
ax.grid(True, ls=":", lw=0.4, alpha=0.3)

# ════════════════════════════════════════════════════════════════════════════════
# PANEL 2 — top-down view
# ════════════════════════════════════════════════════════════════════════════════
ax2.set_aspect("equal")
ax2.set_title(
    "Top-down view  (solid fill = flange face at z = total_height;  dashed = skirt extents)",
    fontsize=10, pad=8)

# Flange disk (visible at z = H)
ax2.add_patch(plt.Circle((0, 0), fr, fc="#b0c8e8", ec="#2255aa", lw=1.5, zorder=2))
ax2.add_patch(plt.Circle((0, 0), br, fc="white",   ec="#555",    lw=1.0, ls="--", zorder=4))

# Skirt extents (dashed — visible at z = 0 cross-section)
ax2.add_patch(plt.Circle((0, 0), so, fc="none", ec="#2255aa", lw=1.3, ls=":",  zorder=3))
ax2.add_patch(plt.Circle((0, 0), si, fc="none", ec="#2255aa", lw=0.9, ls="--", zorder=3))

# Small-hole pitch circle (dashed)
ax2.add_patch(plt.Circle((0, 0), shp, fc="none", ec=C_H, lw=0.9, ls=":", zorder=3))

# Small holes
for i in range(shn):
    ang = 2 * math.pi * i / shn
    ax2.add_patch(plt.Circle((shp * math.cos(ang), shp * math.sin(ang)), shr,
                              fc="white", ec=C_H, lw=1.3, zorder=5))

# Axis crosshair
ax2.plot(0, 0, "+", color="black", ms=10, mew=1.5, zorder=6)

# bore_radius → lower-right (315°)
ang_br = math.radians(315)
arrow(ax2, 0, 0, br * math.cos(ang_br), br * math.sin(ang_br), C_R)
lbl(ax2, br * 0.55 * math.cos(ang_br) + 0.07, br * 0.55 * math.sin(ang_br) - 0.12,
    "bore_radius", C_R, ha="left", fs=7.5)

# flange_radius → upper-right (45°)
ang_fr = math.radians(45)
arrow(ax2, 0, 0, fr * math.cos(ang_fr), fr * math.sin(ang_fr), C_R)
lbl(ax2, fr * 0.50 * math.cos(ang_fr) + 0.07, fr * 0.50 * math.sin(ang_fr) + 0.10,
    "flange_radius", C_R, ha="left", fs=8)

# skirt_outer_radius → upper-left (135°)
ang_so = math.radians(135)
arrow(ax2, 0, 0, so * math.cos(ang_so), so * math.sin(ang_so), C_R)
lbl(ax2, so * 0.52 * math.cos(ang_so) - 0.08, so * 0.52 * math.sin(ang_so) + 0.10,
    "skirt_outer_radius", C_R, ha="right", fs=8)

# skirt_inner_radius → lower-left (225°)
ang_si = math.radians(225)
arrow(ax2, 0, 0, si * math.cos(ang_si), si * math.sin(ang_si), C_R)
lbl(ax2, si * 0.52 * math.cos(ang_si) - 0.06, si * 0.52 * math.sin(ang_si) - 0.12,
    "skirt_inner_radius", C_R, ha="right", fs=8)

# small_hole_placement_r → downward (270°)
arrow(ax2, 0, 0, 0, -shp, C_H)
lbl(ax2, 0.08, -shp * 0.52, "small_hole_\nplacement_r", C_H, ha="left", fs=7.5)

# small_hole_radius → annotation pointing to rightmost hole
ax2.annotate("small_hole_radius",
             xy=(shp + shr, 0),
             xytext=(shp + 0.55, 0.38),
             fontsize=7.5, color=C_H,
             arrowprops=dict(arrowstyle="->", color=C_H, lw=0.9),
             bbox=dict(fc="white", ec="none"))

lbl(ax2, so * 0.65, -so * 0.94,
    f"small_hole_count = {shn}", C_H, ha="center", fs=8)

ax2.set_xlim(-so * 1.35, so * 1.35)
ax2.set_ylim(-so * 1.35, so * 1.35)
ax2.set_xlabel("x  [m]", fontsize=9)
ax2.set_ylabel("y  [m]", fontsize=9)
ax2.tick_params(labelsize=8)
ax2.grid(True, ls=":", lw=0.4, alpha=0.3)

# ── Legend ────────────────────────────────────────────────────────────────────
legend_handles = [
    mpatches.Patch(fc="#b0c8e8", ec="#2255aa", lw=1.5, label="Solid material"),
    mpatches.Patch(fc="white",   ec="#555",    lw=1.0, label="Bore / holes"),
    plt.Line2D([0], [0], color=C_R, lw=1.5, label="Radius parameters"),
    plt.Line2D([0], [0], color=C_Z, lw=1.5, label="Height parameters"),
    plt.Line2D([0], [0], color=C_H, lw=1.5, label="Hole parameters"),
]
fig.legend(handles=legend_handles, loc="lower center", ncol=5, fontsize=9,
           framealpha=0.9, edgecolor="#aaa", bbox_to_anchor=(0.5, 0.01))

plt.tight_layout(rect=[0, 0.06, 1, 0.97])
plt.savefig("strongback_params.png", dpi=170, bbox_inches="tight")
print("Saved strongback_params.png")
plt.show()
