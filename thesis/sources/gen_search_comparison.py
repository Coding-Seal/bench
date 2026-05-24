import sys
import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# Reproducibility
rng = np.random.default_rng(42)

# --- objective landscape (2-D toy) ---
x = np.linspace(0, 1, 200)
y = np.linspace(0, 1, 200)
X, Y = np.meshgrid(x, y)
# Two peaks; true optimum at ~(0.72, 0.63)
Z = np.exp(-((X - 0.72) ** 2 + (Y - 0.63) ** 2) / 0.02) + 0.6 * np.exp(
    -((X - 0.25) ** 2 + (Y - 0.30) ** 2) / 0.03
)

OPT_X, OPT_Y = 0.72, 0.63
N = 25  # evaluation budget shown

fig, axes = plt.subplots(1, 3, figsize=(11, 3.5))
fig.subplots_adjust(left=0.06, right=0.97, bottom=0.15, top=0.88, wspace=0.35)

kw_contour = dict(levels=16, cmap="Blues", alpha=0.55)
kw_scatter = dict(zorder=4, edgecolors="#222", linewidths=0.4)
marker_kw = dict(marker="o", s=32)

# ── 1. Grid search ──────────────────────────────────────────────────────────
ax = axes[0]
ax.contourf(X, Y, Z, **kw_contour)
g = np.linspace(0.0, 1.0, 5)
GX, GY = np.meshgrid(g, g)
pts_x, pts_y = GX.flatten(), GY.flatten()
vals = np.exp(-((pts_x - OPT_X) ** 2 + (pts_y - OPT_Y) ** 2) / 0.02) + 0.6 * np.exp(
    -((pts_x - 0.25) ** 2 + (pts_y - 0.30) ** 2) / 0.03
)
ax.scatter(pts_x, pts_y, c=vals, cmap="autumn_r", vmin=0, vmax=1, **kw_scatter, **marker_kw)
ax.set_title("Поиск по сетке\n(grid search)", fontsize=10, pad=4)
ax.set_xlabel("Параметр 1", fontsize=8)
ax.set_ylabel("Параметр 2", fontsize=8)
ax.tick_params(labelsize=7)
ax.set_xlim(0, 1)
ax.set_ylim(0, 1)
ax.text(
    0.02,
    0.02,
    f"25 испытаний, равномерная сетка",
    transform=ax.transAxes,
    fontsize=7,
    color="#333",
    bbox=dict(boxstyle="round,pad=0.2", fc="white", alpha=0.7),
)

# ── 2. Random search ────────────────────────────────────────────────────────
ax = axes[1]
ax.contourf(X, Y, Z, **kw_contour)
rx = rng.uniform(0, 1, N)
ry = rng.uniform(0, 1, N)
rvals = np.exp(-((rx - OPT_X) ** 2 + (ry - OPT_Y) ** 2) / 0.02) + 0.6 * np.exp(
    -((rx - 0.25) ** 2 + (ry - 0.30) ** 2) / 0.03
)
ax.scatter(rx, ry, c=rvals, cmap="autumn_r", vmin=0, vmax=1, **kw_scatter, **marker_kw)
ax.set_title("Случайный поиск\n(random search)", fontsize=10, pad=4)
ax.set_xlabel("Параметр 1", fontsize=8)
ax.tick_params(labelsize=7)
ax.set_xlim(0, 1)
ax.set_ylim(0, 1)
ax.text(
    0.02,
    0.02,
    f"25 испытаний, равномерно случайные",
    transform=ax.transAxes,
    fontsize=7,
    color="#333",
    bbox=dict(boxstyle="round,pad=0.2", fc="white", alpha=0.7),
)

# ── 3. Bayesian optimisation (simulated) ────────────────────────────────────
ax = axes[2]
ax.contourf(X, Y, Z, **kw_contour)

n_init = 5
init_x = rng.uniform(0, 1, n_init)
init_y = rng.uniform(0, 1, n_init)

# Simulate BO trajectory: after init, points migrate toward optimum
n_bo = N - n_init
t = np.linspace(0, 1, n_bo)
noise_scale = 0.18 * (1 - t)  # decreasing exploration noise
bo_x = np.clip(OPT_X + rng.normal(0, noise_scale), 0, 1)
bo_y = np.clip(OPT_Y + rng.normal(0, noise_scale), 0, 1)

all_x = np.concatenate([init_x, bo_x])
all_y = np.concatenate([init_y, bo_y])
all_v = np.exp(-((all_x - OPT_X) ** 2 + (all_y - OPT_Y) ** 2) / 0.02) + 0.6 * np.exp(
    -((all_x - 0.25) ** 2 + (all_y - 0.30) ** 2) / 0.03
)

# Draw arrows showing sequential decisions
for i in range(n_init, N - 1):
    ax.annotate(
        "",
        xy=(all_x[i + 1], all_y[i + 1]),
        xytext=(all_x[i], all_y[i]),
        arrowprops=dict(arrowstyle="->", color="#555", lw=0.6),
    )

ax.scatter(init_x, init_y, c="#aaaaaa", **kw_scatter, **marker_kw, label="нач. выборка")
ax.scatter(
    bo_x,
    bo_y,
    c=all_v[n_init:],
    cmap="autumn_r",
    vmin=0,
    vmax=1,
    **kw_scatter,
    **marker_kw,
    label="Байес. шаги",
)
ax.set_title("Байесовская оптимизация\n(Bayesian optimisation)", fontsize=10, pad=4)
ax.set_xlabel("Параметр 1", fontsize=8)
ax.tick_params(labelsize=7)
ax.set_xlim(0, 1)
ax.set_ylim(0, 1)
legend = ax.legend(fontsize=7, loc="upper left", framealpha=0.8, handletextpad=0.4)

ax.text(
    0.02,
    0.02,
    f"25 испытаний, направленный поиск",
    transform=ax.transAxes,
    fontsize=7,
    color="#333",
    bbox=dict(boxstyle="round,pad=0.2", fc="white", alpha=0.7),
)


out = "/home/coding-seal/uni/dipl/bench/thesis/sources/search_comparison.svg"
plt.savefig(out, format="svg", bbox_inches="tight")
print(f"Saved {out}")
