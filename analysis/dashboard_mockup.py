"""
작황 판단 대시보드 시안 (PNG 목업)
- 대상: MEDIUM 품종(MZ990002), 2021-2025
- 목적: 99컬럼 중 작황 의사결정에 의미 있는 지표를 한 화면에 배치하는 방식 제안
- 각 패널 = (지표, 근거 변수, 시각화 형태) 한 세트
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.gridspec import GridSpec

# WSL에서 Windows 한글 폰트 등록
_KR_FONT = "/mnt/c/Windows/Fonts/malgun.ttf"
if Path(_KR_FONT).exists():
    font_manager.fontManager.addfont(_KR_FONT)
    plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False

CSV_DIR = Path("/home/ironm/codebase/Tokki/res/result")
OUT_DIR = Path("/home/ironm/codebase/Tokki/analysis/out")
OUT_DIR.mkdir(parents=True, exist_ok=True)
CSV = sorted(CSV_DIR.glob("tokki_combinedOutput_*.csv"))[-1]
print(f"[load] {CSV.name}")

NA = [-99, -99.0]
COLS = [
    "LAT", "LONG", "CultivarCode", "WYEAR",
    "HWAM", "CWAM", "HIAM", "LAIX",                # yield & biomass
    "PDAT", "EDAT", "ADAT", "MDAT", "HDAT", "NDCH",  # phenology
    "PRCM", "ETCM", "EPCM", "ESCM", "DRCM", "ROCM", "IRCM",  # water
    "NICM", "NUCM", "NLCM", "GNAM",                # nitrogen
    "TMAXA", "TMINA", "SRADA",                     # climate
    "CropCodeST",                                  # status (CRST)
]
df = pd.read_csv(CSV, usecols=COLS, na_values=NA, index_col=False)
df = df.rename(columns={"LONG": "lon", "LAT": "lat"})
for c in ("lat", "lon"):
    df[c] = pd.to_numeric(df[c].astype(str).str.strip(), errors="coerce")
df["CultivarCode"] = df["CultivarCode"].astype(str).str.strip()
df = df[df["CultivarCode"] == "MZ990002"].copy()         # MEDIUM only
df["year"] = df["WYEAR"].astype(int)
print(f"[load] MEDIUM rows={len(df):,}, years={sorted(df['year'].unique())}")

# DOY 추출 (YYYYDDD → DDD)
def to_doy(s: pd.Series) -> pd.Series:
    v = pd.to_numeric(s, errors="coerce")
    return (v % 1000).where(v > 1000, np.nan)

for d in ("PDAT", "EDAT", "ADAT", "MDAT", "HDAT"):
    df[d + "_doy"] = to_doy(df[d])

# ===================== 도화지 =====================
fig = plt.figure(figsize=(20, 14))
gs = GridSpec(3, 3, figure=fig, hspace=0.55, wspace=0.30,
              left=0.05, right=0.97, top=0.92, bottom=0.05)
fig.suptitle(
    "Crop-yield dashboard mockup — MEDIUM cultivar (MZ990002), US maize, 2021–2025\n"
    "각 패널 = (지표 · 근거 컬럼 · 시각화). 데이터는 실제 결과 CSV 사용.",
    fontsize=15, y=0.985,
)

# ---------- (1) 헤드라인 지도: 5년 평균 수확량 ----------
ax1 = fig.add_subplot(gs[0, 0:2])
cell = df.groupby(["lat", "lon"])["HWAM"].mean().reset_index()
vmin, vmax = cell["HWAM"].quantile(0.05), cell["HWAM"].quantile(0.95)
sc = ax1.scatter(cell["lon"], cell["lat"], c=cell["HWAM"],
                 s=4, cmap="RdYlGn", vmin=vmin, vmax=vmax, linewidths=0, alpha=0.85)
ax1.set_title("① 수확량 공간분포 (HWAM, 5y mean)\n"
              "─ 무엇: 셀별 평균 단위면적 수확량 · 왜: 1차 작황 지표 · "
              "어떻게: HWAM 셀평균을 RdYlGn으로",
              loc="left", fontsize=10)
ax1.set_xlabel("Longitude"); ax1.set_ylabel("Latitude")
ax1.set_aspect("equal"); ax1.grid(True, alpha=0.3)
fig.colorbar(sc, ax=ax1, shrink=0.7, label="kg/ha")

# ---------- (2) 연도별 수확량 추세 (median + IQR band) ----------
ax2 = fig.add_subplot(gs[0, 2])
by_year = df.groupby("year")["HWAM"]
med = by_year.median(); q1 = by_year.quantile(0.25); q3 = by_year.quantile(0.75)
ax2.fill_between(med.index, q1.values, q3.values, alpha=0.25, color="#2ca02c", label="IQR")
ax2.plot(med.index, med.values, "o-", color="#2ca02c", lw=2, label="median")
ax2.set_title("② 연도별 수확량 추세\n"
              "─ HWAM median ± IQR. 평년대비/이상기상 영향 탐지",
              loc="left", fontsize=10)
ax2.set_xlabel("Year"); ax2.set_ylabel("HWAM (kg/ha)")
ax2.grid(True, alpha=0.3); ax2.legend(fontsize=8)
ax2.set_xticks(sorted(df["year"].unique()))

# ---------- (3) 생육 캘린더 (PDAT→EDAT→ADAT→MDAT→HDAT의 DOY 분포) ----------
ax3 = fig.add_subplot(gs[1, 0])
stages = [("PDAT", "Plant"), ("EDAT", "Emerge"),
          ("ADAT", "Anthesis"), ("MDAT", "Maturity"), ("HDAT", "Harvest")]
data = [df[c + "_doy"].dropna() for c, _ in stages]
bp = ax3.boxplot(data, vert=False, patch_artist=True,
                 labels=[lbl for _, lbl in stages], widths=0.55)
for patch, color in zip(bp["boxes"], ["#8c6d31", "#a1d99b", "#fdae6b", "#e6550d", "#636363"]):
    patch.set_facecolor(color); patch.set_alpha(0.7)
ax3.set_title("③ 생육 단계별 시기 (DOY)\n"
              "─ PDAT/EDAT/ADAT/MDAT/HDAT. 평년 대비 조기/지연 진단",
              loc="left", fontsize=10)
ax3.set_xlabel("Day of year"); ax3.grid(True, axis="x", alpha=0.3)

# ---------- (4) 연도별 수확량 분포 (boxplot) ----------
ax4 = fig.add_subplot(gs[1, 1])
years = sorted(df["year"].unique())
data_y = [df[df["year"] == y]["HWAM"].dropna() for y in years]
ax4.boxplot(data_y, labels=years, patch_artist=True,
            boxprops=dict(facecolor="#a1d99b", alpha=0.7))
ax4.set_title("④ 수확량 분포 (연도별)\n"
              "─ 분포 폭이 곧 지역별 편차. 평균 한 줄로 가려진 위험 노출",
              loc="left", fontsize=10)
ax4.set_xlabel("Year"); ax4.set_ylabel("HWAM (kg/ha)")
ax4.grid(True, axis="y", alpha=0.3)

# ---------- (5) 물수지 (연도별 PRCM = ETCM + ROCM + DRCM 근사) ----------
ax5 = fig.add_subplot(gs[1, 2])
wmean = df.groupby("year")[["PRCM", "ETCM", "EPCM", "ESCM", "DRCM", "ROCM", "IRCM"]].mean()
x = wmean.index.values
ax5.bar(x, wmean["EPCM"], label="Transp. (EP)", color="#2ca02c", alpha=0.85)
ax5.bar(x, wmean["ESCM"], bottom=wmean["EPCM"], label="Soil Evap. (ES)", color="#bcbd22", alpha=0.85)
ax5.bar(x, wmean["ROCM"], bottom=wmean["EPCM"] + wmean["ESCM"], label="Runoff", color="#9467bd", alpha=0.85)
ax5.bar(x, wmean["DRCM"], bottom=wmean["EPCM"] + wmean["ESCM"] + wmean["ROCM"], label="Drainage", color="#8c564b", alpha=0.85)
ax5.plot(x, wmean["PRCM"], "ko--", lw=1.5, label="Precip. total", ms=6)
ax5.set_title("⑤ 물수지 (mm)\n"
              "─ PRCM=강수 / EPCM 증산 / ESCM 토양증발 / DRCM 배수 / ROCM 유출\n"
              "  증산 비중 ↓ = 가뭄/뿌리 스트레스 시사",
              loc="left", fontsize=9)
ax5.set_xlabel("Year"); ax5.set_ylabel("mm")
ax5.legend(fontsize=7, ncol=2); ax5.grid(True, axis="y", alpha=0.3)
ax5.set_xticks(years)

# ---------- (6) 질소수지 (NICM 투입 vs NUCM 흡수 vs NLCM 누출) ----------
ax6 = fig.add_subplot(gs[2, 0])
nmean = df.groupby("year")[["NICM", "NUCM", "NLCM", "GNAM"]].mean()
w = 0.25
xn = np.arange(len(years))
ax6.bar(xn - w, nmean["NICM"], w, label="Applied (NICM)", color="#9ecae1")
ax6.bar(xn,     nmean["NUCM"], w, label="Uptake (NUCM)",  color="#3182bd")
ax6.bar(xn + w, nmean["NLCM"], w, label="Leached (NLCM)", color="#d62728")
ax6.set_xticks(xn); ax6.set_xticklabels(years)
ax6.set_title("⑥ 질소수지 (kg N/ha)\n"
              "─ 흡수율 NUCM/NICM = 비료 효율 · NLCM 환경부하 동시 점검",
              loc="left", fontsize=10)
ax6.set_xlabel("Year"); ax6.set_ylabel("kg N/ha")
ax6.legend(fontsize=8); ax6.grid(True, axis="y", alpha=0.3)

# ---------- (7) 기후 컨텍스트 (TMAXA/TMINA + SRADA 2축) ----------
ax7 = fig.add_subplot(gs[2, 1])
cmean = df.groupby("year")[["TMAXA", "TMINA", "SRADA"]].mean()
xc = cmean.index.values
ax7.fill_between(xc, cmean["TMINA"], cmean["TMAXA"], alpha=0.3, color="#fdae6b", label="T range")
ax7.plot(xc, cmean["TMAXA"], "r^-", label="TMAXA", ms=6)
ax7.plot(xc, cmean["TMINA"], "bv-", label="TMINA", ms=6)
ax7.set_xlabel("Year"); ax7.set_ylabel("°C", color="#d62728")
ax7b = ax7.twinx()
ax7b.plot(xc, cmean["SRADA"], "s--", color="#bcbd22", label="SRADA")
ax7b.set_ylabel("MJ/m²/d", color="#bcbd22")
ax7.set_title("⑦ 기후 배경 (생육기 평균)\n"
              "─ TMAXA/TMINA 온도범위 · SRADA 일사. 이상치 해석의 근거",
              loc="left", fontsize=10)
ax7.legend(loc="upper left", fontsize=8); ax7.grid(True, alpha=0.3)
ax7.set_xticks(years)

# ---------- (8) 작황 상태 플래그 (CRST 카운트) ----------
ax8 = fig.add_subplot(gs[2, 2])
crst = df["CropCodeST"].fillna("missing").astype(str).str.strip().replace("", "missing")
crst_year = (df.assign(crst=crst).groupby(["year", "crst"]).size()
               .unstack(fill_value=0))
crst_year.plot(kind="bar", stacked=True, ax=ax8, colormap="tab20", width=0.7)
ax8.set_title("⑧ 종료 상태 코드 (CRST)\n"
              "─ 수확 도달 / 성숙 미달 / 실패 구분. 실패 셀의 공간분포로 위험지대 추적",
              loc="left", fontsize=10)
ax8.set_xlabel("Year"); ax8.set_ylabel("# of runs")
ax8.legend(title="status", fontsize=7, loc="upper right", ncol=2)
ax8.tick_params(axis="x", rotation=0); ax8.grid(True, axis="y", alpha=0.3)

# ===================== 저장 =====================
out = OUT_DIR / "dashboard_mockup.png"
plt.savefig(out, dpi=120, bbox_inches="tight")
plt.close()
print(f"[save] {out}")
