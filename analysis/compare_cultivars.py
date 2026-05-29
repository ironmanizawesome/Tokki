"""
품종 비교 분석 (LONG/MEDIUM/SHORT)
- 품종별 지도
- 위도별 우승 품종
- 셀별 winner
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap

CSV_DIR = Path("/home/ironm/codebase/Tokki/res/result")
OUT_DIR = Path("/home/ironm/codebase/Tokki/analysis/out")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# 최신 파일 자동 선택
csv_files = sorted(CSV_DIR.glob("tokki_combinedOutput_*.csv"))
CSV = csv_files[-1]
print(f"[load] {CSV.name} ({CSV.stat().st_size/1e6:.1f} MB)")

# 콘솔 + 파일 동시 출력
class _Tee:
    def __init__(self, *streams): self._streams = streams
    def write(self, s):
        for st in self._streams: st.write(s)
    def flush(self):
        for st in self._streams: st.flush()

_log = open(OUT_DIR / "cultivar_comparison.txt", "w")
sys.stdout = _Tee(sys.__stdout__, _log)

NA = [-99, -99.0]
df = pd.read_csv(CSV,
                 usecols=["LAT", "LONG", "CultivarCode", "WYEAR",
                          "HWAM", "NDCH", "PRCM", "TMAXA"],
                 na_values=NA, index_col=False)
df = df.rename(columns={"LONG": "lon", "LAT": "lat"})

for c in ("lat", "lon"):
    df[c] = pd.to_numeric(df[c].astype(str).str.strip(), errors="coerce")

CULTIVAR_LABEL = {"MZ990001": "LONG", "MZ990002": "MEDIUM", "MZ990003": "SHORT"}
df["cultivar"] = df["CultivarCode"].map(CULTIVAR_LABEL)
print(f"[load] rows={len(df):,}, cells={df.groupby(['lat','lon']).ngroups:,}")

# === 1. 품종 × 위도밴드 평균 ===
print("\n[1] 위도밴드(2°)별 평균 수확량 (kg/ha)")
df["lat_band"] = (df["lat"] // 2 * 2).astype(int)
pivot = (df.groupby(["lat_band", "cultivar"])["HWAM"]
           .mean().unstack().round(0))
pivot["winner"] = pivot.idxmax(axis=1)
pivot["max"] = pivot[["LONG", "MEDIUM", "SHORT"]].max(axis=1).round(0)
print(pivot.to_string())

# === 2. 셀별 winner cultivar ===
print("\n[2] 셀별 5년 평균 후 winner 결정")
cell_avg = (df.groupby(["lat", "lon", "cultivar"])["HWAM"]
              .mean().unstack())
cell_avg["winner"] = cell_avg[["LONG", "MEDIUM", "SHORT"]].idxmax(axis=1)
winner_counts = cell_avg["winner"].value_counts()
print(f"Winner 셀 수: {winner_counts.to_dict()}")
print(f"비율: {(winner_counts / len(cell_avg) * 100).round(1).to_dict()}%")

# === 3. 셀별 winner 지도 ===
print("\n[3] Winner 분포 지도 그리는 중...")
winner_color = {"LONG": "#1f77b4", "MEDIUM": "#2ca02c", "SHORT": "#d62728"}
fig, ax = plt.subplots(figsize=(13, 7.5))
for label, color in winner_color.items():
    sub = cell_avg[cell_avg["winner"] == label].reset_index()
    ax.scatter(sub["lon"], sub["lat"], c=color, s=4, alpha=0.85,
               linewidths=0, label=f"{label} ({len(sub):,})")
ax.set_xlabel("Longitude")
ax.set_ylabel("Latitude")
ax.set_title("Best Cultivar per Cell (5-year mean)")
ax.set_aspect("equal")
ax.grid(True, alpha=0.3)
ax.legend(markerscale=3, loc="lower left")
plt.tight_layout()
plt.savefig(OUT_DIR / "map_cultivar_winner.png", dpi=130)
plt.close()
print(f"  saved: map_cultivar_winner.png")

# === 4. 품종별 yield map (3개 패널) ===
print("\n[4] 품종별 수확량 지도 (3 패널)...")
fig, axes = plt.subplots(1, 3, figsize=(20, 6.5))
vmin, vmax = (df["HWAM"].quantile(0.05), df["HWAM"].quantile(0.95))
for ax, (cv, lbl) in zip(axes, [("MZ990001", "LONG"),
                                 ("MZ990002", "MEDIUM"),
                                 ("MZ990003", "SHORT")]):
    sub = (df[df["CultivarCode"] == cv]
             .groupby(["lat", "lon"])["HWAM"].mean().reset_index())
    sc = ax.scatter(sub["lon"], sub["lat"], c=sub["HWAM"],
                    s=3, cmap="RdYlGn", vmin=vmin, vmax=vmax,
                    alpha=0.85, linewidths=0)
    ax.set_title(f"{lbl}  (mean={sub['HWAM'].mean():.0f} kg/ha)")
    ax.set_xlabel("Longitude")
    ax.set_aspect("equal")
    ax.grid(True, alpha=0.3)
axes[0].set_ylabel("Latitude")
fig.colorbar(sc, ax=axes, shrink=0.7, label="kg/ha")
fig.suptitle("US Maize Yield by Cultivar (HWAM, 5-year mean)", fontsize=13)
plt.savefig(OUT_DIR / "map_yield_by_cultivar.png", dpi=130, bbox_inches="tight")
plt.close()
print(f"  saved: map_yield_by_cultivar.png")

# === 5. 위도별 line chart ===
print("\n[5] 위도별 평균 수확량 line chart...")
fig, ax = plt.subplots(figsize=(10, 5.5))
for cv, lbl in [("MZ990001", "LONG"), ("MZ990002", "MEDIUM"), ("MZ990003", "SHORT")]:
    sub = df[df["CultivarCode"] == cv]
    s = sub.groupby("lat_band")["HWAM"].mean()
    ax.plot(s.index, s.values, marker="o", label=lbl, color=winner_color[lbl])
ax.set_xlabel("Latitude band (°N)")
ax.set_ylabel("Mean yield (kg/ha)")
ax.set_title("Yield by Latitude — Cultivar Comparison")
ax.legend()
ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig(OUT_DIR / "yield_by_lat_cultivar.png", dpi=130)
plt.close()
print(f"  saved: yield_by_lat_cultivar.png")

# === 6. 품종별 yield 분포 (히스토그램) ===
print("\n[6] 품종별 yield 분포 hist...")
fig, ax = plt.subplots(figsize=(10, 5.5))
for cv, lbl in [("MZ990001", "LONG"), ("MZ990002", "MEDIUM"), ("MZ990003", "SHORT")]:
    sub = df[df["CultivarCode"] == cv]["HWAM"].dropna()
    ax.hist(sub, bins=60, alpha=0.45, label=lbl, color=winner_color[lbl])
ax.set_xlabel("Yield (kg/ha)")
ax.set_ylabel("Count")
ax.set_title("Yield Distribution by Cultivar")
ax.legend()
ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig(OUT_DIR / "yield_hist_cultivar.png", dpi=130)
plt.close()
print(f"  saved: yield_hist_cultivar.png")

print(f"\n[done] outputs: {OUT_DIR}")
sys.stdout = sys.__stdout__
_log.close()
