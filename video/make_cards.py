import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

W, H, DPI = 1080, 1920, 120
BG, FG, MUTED, RED, GREEN = "#0f1412", "#f4f1ea", "#9aa39e", "#e0533d", "#3fbf7f"

def canvas():
    fig = plt.figure(figsize=(W / DPI, H / DPI), dpi=DPI, facecolor=BG)
    return fig

# 1) benchmark card (numbers from README / results/, held-out set, 2026-11-02 real run)
conds = ["clean", "phone", "20 dB", "10 dB", "5 dB", "0 dB"]
v25 = [10, 9, 9, 9, 9, 6]
v3c = [10, 10, 10, 10, 10, 10]
fig = canvas()
fig.text(0.5, 0.90, "Noisy phone-line test", ha="center", color=FG, fontsize=34, weight="bold")
fig.text(0.5, 0.86, "Telugu questions, 8 kHz phone audio + noise", ha="center", color=MUTED, fontsize=19)
ax = fig.add_axes([0.12, 0.30, 0.80, 0.48], facecolor=BG)
import numpy as np
x = np.arange(len(conds)); w = 0.38
ax.bar(x - w / 2, v25, w, color=RED, label="Prisma v2.5")
ax.bar(x + w / 2, v3c, w, color=GREEN, label="Prisma v3.0 + keyterms")
for i in range(len(conds)):
    ax.text(x[i] - w / 2, v25[i] + 0.15, str(v25[i]), ha="center", color=FG, fontsize=15)
    ax.text(x[i] + w / 2, v3c[i] + 0.15, str(v3c[i]), ha="center", color=FG, fontsize=15, weight="bold")
ax.set_xticks(x, conds, color=FG, fontsize=17)
ax.set_ylim(0, 11.5); ax.set_yticks([0, 5, 10]); ax.tick_params(colors=MUTED, labelsize=15)
for s in ax.spines.values(): s.set_visible(False)
ax.set_ylabel("questions answered right (of 10)", color=MUTED, fontsize=16)
ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.09), ncol=1, frameon=False, labelcolor=FG, fontsize=19)
fig.text(0.5, 0.15, "At 0 dB: 6/10 → 10/10", ha="center", color=GREEN, fontsize=38, weight="bold")
fig.text(0.5, 0.10, "10 held-out questions · real Gnani API run, 2 Nov 2026", ha="center", color=MUTED, fontsize=16)
fig.savefig("card_benchmark.png", facecolor=BG); plt.close(fig)

# 2) end card
fig = canvas()
fig.text(0.5, 0.64, "Rythu Vaani", ha="center", color=FG, fontsize=64, weight="bold")
fig.text(0.5, 0.58, "Telugu voice helpline for farmers", ha="center", color=MUTED, fontsize=24)
fig.text(0.5, 0.48, "Gnani Prisma STT  +  Timbre TTS", ha="center", color=GREEN, fontsize=28, weight="bold")
fig.text(0.5, 0.40, "github.com/vivekyarra/rythu-vaani", ha="center", color=FG, fontsize=24)
fig.text(0.5, 0.34, "Built solo in Guntur · synthetic data only", ha="center", color=MUTED, fontsize=20)
fig.text(0.5, 0.24, "#GreatIndianAIInternshipChallenge  #GnaniAI", ha="center", color=FG, fontsize=20)
fig.savefig("card_end.png", facecolor=BG); plt.close(fig)
print("ok")
