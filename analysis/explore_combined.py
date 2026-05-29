"""
Tokki combinedOutput 탐색 스크립트
- 패턴 A: pandas 기본 통계/그룹분석
- 패턴 C: matplotlib 산점도 지도화 (geopandas 미사용)
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

CSV = Path("/home/ironm/codebase/Tokki/res/result/tokki_combinedOutput_1778735237602.csv")
OUT_DIR = Path("/home/ironm/codebase/Tokki/analysis/out")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# 콘솔 + 파일 동시 출력 (패턴 A 결과 자동 저장)
class _Tee:
    def __init__(self, *streams): self._streams = streams
    def write(self, s):
        for st in self._streams: st.write(s)
    def flush(self):
        for st in self._streams: st.flush()

_log_path = OUT_DIR / "pattern_A_results.txt"
_log_file = open(_log_path, "w")
sys.stdout = _Tee(sys.__stdout__, _log_file)

print(f"[load] {CSV.name} ({CSV.stat().st_size/1e6:.1f} MB)")

# 결측값 처리: DSSAT는 -99 또는 -99.0을 sentinel로 씀
NA_VALS = [-99, -99.0, "-99", "-99.0", "-99.000000", "-99.0000000"]

usecols = [
    "LAT", "LONG", "CropCode", "CultivarCode", "WYEAR",
    "PDAT", "HDAT", "NDCH",
    "HWAM", "CWAM", "LAIX",
    "PRCM", "IRCM", "ETCM", "DRCM",
    "NICM", "NUCM", "NLCM", "N2OEM",
    "TMAXA", "TMINA", "SRADA", "PRCP", "CO2A",
    "TNAM",
]
df = pd.read_csv(CSV, usecols=usecols, na_values=NA_VALS, index_col=False)
print(f"[load] rows={len(df):,}  cols={df.shape[1]}")

# LAT/LONG에 좌우 공백 + '+' 부호 → 숫자 변환
for c in ("LAT", "LONG"):
    df[c] = pd.to_numeric(df[c].astype(str).str.strip(), errors="coerce")

print()
print("=" * 70)
print("패턴 A — 기본 탐색")
print("=" * 70)

# A.0 — 데이터 범위 요약
print("\n[A.0] 식별자 분포")
print(f"  작물(CropCode):  {df['CropCode'].value_counts().to_dict()}")
print(f"  품종(CultivarCode): {df['CultivarCode'].value_counts().to_dict()}")
print(f"  연도(WYEAR):     {sorted(df['WYEAR'].dropna().unique().astype(int))}")
print(f"  LAT 범위:        {df['LAT'].min():.2f} ~ {df['LAT'].max():.2f}")
print(f"  LONG 범위:       {df['LONG'].min():.2f} ~ {df['LONG'].max():.2f}")
print(f"  고유 셀 수:      {df.groupby(['LAT','LONG']).ngroups:,}")
print(f"  TNAM 시나리오:   {df['TNAM'].nunique()} 종류 (예: {df['TNAM'].unique()[:5].tolist()})")

# A.1 — 핵심 변수 분포
print("\n[A.1] 핵심 변수 통계 요약")
key = ["HWAM", "CWAM", "LAIX", "NDCH", "PRCM", "IRCM", "ETCM",
       "NICM", "NUCM", "NLCM", "N2OEM", "TMAXA", "TMINA", "SRADA"]
print(df[key].describe().T[["count", "mean", "std", "min", "50%", "max"]].round(2).to_string())

# A.2 — 연도별 평균 수확량
print("\n[A.2] 연도별 옥수수 수확량 (HWAM, kg/ha)")
year_stats = df.groupby("WYEAR")["HWAM"].agg(["count", "mean", "median", "std"]).round(1)
print(year_stats.to_string())

# A.3 — 위도대별 수확량 (남북 차이)
print("\n[A.3] 위도대별 평균 수확량 (2도 단위)")
df["lat_band"] = (df["LAT"] // 2 * 2).astype("Int64")
lat_stats = df.groupby("lat_band").agg(
    n=("HWAM", "count"),
    yield_mean=("HWAM", "mean"),
    rain_mm=("PRCM", "mean"),
    irrig_mm=("IRCM", "mean"),
    NDCH=("NDCH", "mean"),
).round(1)
print(lat_stats.to_string())

# A.4 — 강수와 수확량 상관
print("\n[A.4] 자원 변수 vs 수확량 상관 (Pearson)")
corr = df[["HWAM", "PRCM", "IRCM", "ETCM", "NICM", "NUCM",
           "TMAXA", "TMINA", "SRADA"]].corr()["HWAM"].drop("HWAM").round(3)
print(corr.sort_values(ascending=False).to_string())

# A.5 — N 효율성
print("\n[A.5] 질소 효율 (yield/NICM, kg yield per kg N)")
df["N_efficiency"] = df["HWAM"] / df["NICM"].replace(0, np.nan)
print(df["N_efficiency"].describe().round(2).to_string())

# A.6 — 시뮬 실패 진단
print("\n[A.6] 결측/실패 진단")
fail = df["HWAM"].isna().sum()
zero_yield = (df["HWAM"] == 0).sum()
print(f"  HWAM 결측(-99 처리됨): {fail:,} ({fail/len(df)*100:.2f}%)")
print(f"  HWAM = 0(작황실패):    {zero_yield:,} ({zero_yield/len(df)*100:.2f}%)")

# A.7 — 파종일/수확일 변환
print("\n[A.7] 파종일·수확일 분포 (DOY)")
def to_doy(s):
    s = pd.to_numeric(s, errors="coerce")
    year = (s // 1000).astype("Int64")
    doy = (s % 1000).astype("Int64")
    return year, doy

_, p_doy = to_doy(df["PDAT"])
_, h_doy = to_doy(df["HDAT"])
print(f"  파종 DOY:  median={p_doy.median()}, range={p_doy.min()}-{p_doy.max()}")
print(f"  수확 DOY:  median={h_doy.median()}, range={h_doy.min()}-{h_doy.max()}")

print()
print("=" * 70)
print("패턴 C — 지도화 (matplotlib scatter)")
print("=" * 70)

# 셀×연도 평균 → 셀별 5년 평균
agg = (df.groupby(["LAT", "LONG"])
         .agg(yield_mean=("HWAM", "mean"),
              rain_mean=("PRCM", "mean"),
              n2o_mean=("N2OEM", "mean"),
              irrig_mean=("IRCM", "mean"))
         .reset_index())
print(f"[C] 셀 단위 집계: {len(agg):,}")

def make_map(col, title, cmap, fname, vmin=None, vmax=None, units=""):
    fig, ax = plt.subplots(figsize=(13, 7.5))
    sc = ax.scatter(agg["LONG"], agg["LAT"], c=agg[col],
                    s=4, cmap=cmap, vmin=vmin, vmax=vmax, alpha=0.85, linewidths=0)
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_title(title)
    ax.set_aspect("equal")
    ax.grid(True, alpha=0.3)
    cb = plt.colorbar(sc, ax=ax, shrink=0.8)
    cb.set_label(units)
    out = OUT_DIR / fname
    plt.tight_layout()
    plt.savefig(out, dpi=130)
    plt.close()
    print(f"  saved: {out.name}  ({out.stat().st_size//1024} KB)")
    return out

q05, q95 = agg["yield_mean"].quantile([0.05, 0.95])
make_map("yield_mean",
         "US Maize: 5-Year Mean Yield (HWAM, kg/ha)",
         "RdYlGn", "map_yield.png",
         vmin=float(q05), vmax=float(q95), units="kg/ha")

make_map("rain_mean",
         "US Maize Belt: Mean Seasonal Rainfall (PRCM, mm)",
         "Blues", "map_rain.png", units="mm")

make_map("n2o_mean",
         "US Maize: N2O Emission (N2OEM, kg/ha)",
         "Reds", "map_n2o.png", units="kg N2O/ha")

make_map("irrig_mean",
         "US Maize: Irrigation Applied (IRCM, mm)",
         "viridis", "map_irrig.png", units="mm")

# 연도별 수확량 트렌드 차트
print("\n[C+] 연도별 수확량 박스플롯")
fig, ax = plt.subplots(figsize=(9, 5))
years = sorted(df["WYEAR"].dropna().unique().astype(int))
data = [df.loc[df["WYEAR"] == y, "HWAM"].dropna() for y in years]
ax.boxplot(data, labels=years, showfliers=False)
ax.set_title("US Maize Yield by Year (HWAM, kg/ha)")
ax.set_xlabel("Year")
ax.set_ylabel("Yield (kg/ha)")
ax.grid(True, alpha=0.3, axis="y")
plt.tight_layout()
plt.savefig(OUT_DIR / "yield_by_year.png", dpi=130)
plt.close()
print(f"  saved: yield_by_year.png")

print(f"\n[done] outputs: {OUT_DIR}")
print(f"[done] pattern A log: {_log_path.name}")
sys.stdout = sys.__stdout__
_log_file.close()
