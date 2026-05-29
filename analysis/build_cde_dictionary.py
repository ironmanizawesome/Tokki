"""
DSSAT 코드 사전 파싱 → CSV lookup 테이블 생성 + combined CSV 헤더 검증

입력:  dssat-csm-os_devData.txt  (DSSAT v4.8 data dictionary)
출력:  analysis/out/cde_dictionary.csv  (cde, section, label, description, synonyms)
검증:  tokki_combinedOutput_*.csv 헤더 99컬럼이 사전에 모두 정의됐는지 확인
"""
import csv
import re
import sys
from pathlib import Path

ROOT = Path("/home/ironm/codebase/Tokki")
DICT_FILE = ROOT / "dssat-csm-os_devData.txt"
OUT_DIR = ROOT / "analysis" / "out"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_CSV = OUT_DIR / "cde_dictionary.csv"
OUT_HEADER_CSV = OUT_DIR / "combined_header_lookup.csv"
RESULT_DIR = ROOT / "res" / "result"

# 컬럼 위치 (1-indexed 헤더 기준): CDE 1-7 / LABEL 8-23 / DESC 24-78 / SYN 81-
COL_CDE = slice(0, 7)
COL_LABEL = slice(7, 23)
COL_DESC = slice(23, 78)
COL_SYN = slice(80, None)


def parse_dictionary(path: Path):
    """섹션별 데이터 행을 (cde, section, label, description, synonyms) tuple로 반환."""
    rows = []
    section = None
    in_data = False  # @CDE 헤더 라인을 본 직후부터 데이터 행 수집

    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not raw.strip():
            continue
        if raw.startswith("*"):
            section = raw.lstrip("*").strip()
            in_data = False
            continue
        if raw.startswith("@"):
            in_data = True
            continue
        if raw.startswith("!"):
            continue
        if not in_data:
            continue

        cde = raw[COL_CDE].strip()
        if not cde:
            continue
        label = raw[COL_LABEL].strip()
        desc = raw[COL_DESC].strip()
        syn_raw = raw[COL_SYN].strip() if len(raw) > 80 else ""
        synonyms = "" if syn_raw in (".", "") else syn_raw

        rows.append((cde, section, label, desc, synonyms))
    return rows


def write_csv(rows, out_path: Path):
    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["cde", "section", "label", "description", "synonyms"])
        w.writerows(rows)


def latest_combined_csv(result_dir: Path) -> Path | None:
    candidates = sorted(result_dir.glob("tokki_combinedOutput_*.csv"))
    return candidates[-1] if candidates else None


# DSSAT summary 파일의 식별자/메타 컬럼 — 데이터 사전이 다루는 측정/시뮬 변수
# 범주가 아니므로 누락이 정상.
STRUCTURAL_COLS = {
    "RUNNO", "TRNO", "R#", "O#", "P#",
    "MODEL", "EXNAME", "SOIL_ID", "LATI", "CR",
}

# DSSAT summary 파일에서 사전이 다루지 않는 식별자/메타 컬럼의 설명을 직접 명시.
# 컬럼명은 App.java rename 적용 후 형태 기준.
STRUCTURAL_DESC = {
    "RUNNO":         ("DSSAT meta", "Run number",         "Sequential run number assigned by DSSAT"),
    "TRNO":          ("DSSAT meta", "Treatment number",   "Treatment number within experiment"),
    "R#":            ("DSSAT meta", "Rotation number",    "Rotation/sequence component number"),
    "O#":            ("DSSAT meta", "Option number",      "Treatment option number"),
    "P#":            ("DSSAT meta", "Plot number",        "Plot/replicate number"),
    "CropCode":      ("DSSAT meta", "Crop code",          "2-letter DSSAT crop code (e.g. MZ=Maize)"),
    "MODEL":         ("DSSAT meta", "DSSAT model",        "DSSAT model identifier (e.g. MZCER048)"),
    "EXNAME":        ("DSSAT meta", "Experiment name",    "Experiment / scenario file name"),
    "SoilProfileID": ("DSSAT meta", "Soil profile ID",    "Soil profile identifier (renamed from SOIL_ID)"),
    "LAT":           ("DSSAT meta", "Latitude (deg)",     "Site latitude in degrees (renamed from LATI)"),
}

# App.java가 출력 직전 헤더에 적용하는 rename. 검증 시 역매핑.
RENAME_BACK = {
    "SoilProfileID": "SOIL_ID",
    "LAT": "LATI",
    "CropCode": "CR",
    "CultivarCode": "FNAM",
}

# 99컬럼에 대한 한글 설명. 키는 CDE(SUMMARY 사전 등재 항목) 또는
# 컬럼명(DSSAT 메타 식별자). build_header_lookup이 우선순위로 조회.
KR_DESC = {
    # ── DSSAT 메타 식별자 ─────────────────────────────────────
    "RUNNO":         "실행 번호 (DSSAT 내부)",
    "TRNO":          "처리(treatment) 번호",
    "R#":            "윤작(rotation) 번호",
    "O#":            "처리 옵션 번호",
    "P#":            "플롯/반복 번호",
    "CropCode":      "작물 코드 (2글자, 예: MZ=옥수수)",
    "MODEL":         "DSSAT 모델 식별자 (예: MZCER048)",
    "EXNAME":        "실험/시나리오 파일명",
    "SoilProfileID": "토양 프로파일 ID (SOIL_ID에서 rename)",
    "LAT":           "위도 (도, LATI에서 rename)",

    # ── 위치/기상 식별자 ───────────────────────────────────────
    "TNAM":  "처리 이름 (시나리오 식별자)",
    "FNAM":  "품종 코드 (App.java가 CultivarCode로 rename)",
    "WSTA":  "기상 관측소",
    "WYEAR": "기상 자료 연도 (예보 앙상블용)",
    "LONG":  "경도 (도)",
    "ELEV":  "고도 (m)",

    # ── 생육 시기 (날짜는 YrDoy = YYYYDDD) ────────────────────
    "SDAT":  "시뮬레이션 시작일 (YrDoy)",
    "PDAT":  "파종일 (YrDoy)",
    "EDAT":  "출아일 (YrDoy)",
    "ADAT":  "개화일 (YrDoy)",
    "MDAT":  "생리적 성숙일 (YrDoy)",
    "HDAT":  "수확일 (YrDoy)",
    "HYEAR": "수확 연도",
    "NDCH":  "파종~수확 일수 (일)",

    # ── 수확량·바이오매스 ─────────────────────────────────────
    "DWAP":  "파종 종자량 (kg [건물]/ha)",
    "CWAM":  "성숙기 총 바이오매스, 뿌리 제외 (kg [건물]/ha)",
    "HWAM":  "성숙기 수확량 (kg [건물]/ha) — 1차 작황 지표",
    "HWAH":  "실제 수확된 수확량 (kg [건물]/ha)",
    "BWAH":  "수확 시 제거된 부산물(짚 등) (kg [건물]/ha)",
    "PWAM":  "성숙기 꼬투리/이삭/이삭축 무게 (kg [건물]/ha)",
    "HWUM":  "단위당 무게 (g [건물]/단위)",
    "H#AM":  "성숙기 단위면적당 개체수 (개/m²)",
    "H#UM":  "성숙기 단위당 개체수 (개/단위)",
    "HIAM":  "수확지수 (HI, 곡립/총 바이오매스)",
    "LAIX":  "최대 엽면적지수 (LAI)",
    "EYLDH": "경제적 수확량 (t/ha)",

    # ── 생체중 (Fresh weight) ────────────────────────────────
    "FCWAM": "성숙기 지상부 생체중 (kg/ha)",
    "FHWAM": "성숙기 수확물 생체중 (kg/ha)",
    "HWAHF": "수확 생체중 수확량 (kg/ha)",
    "FBWAH": "수확 시 제거된 부산물 생체중 (kg/ha)",
    "FPWAM": "성숙기 꼬투리/이삭 생체중 (kg/ha)",

    # ── 물(Water) ─────────────────────────────────────────────
    "IR#M": "관개 횟수",
    "IRCM": "시즌 관개량 (mm, 손실 포함)",
    "PRCM": "시즌 강수량 (mm, 시뮬레이션~수확)",
    "ETCM": "시즌 증발산량 (mm, 시뮬레이션~수확)",
    "EPCM": "시즌 식물 증산량 (mm)",
    "ESCM": "시즌 토양 증발량 (mm)",
    "ROCM": "시즌 지표 유출량 (mm)",
    "DRCM": "시즌 침투/배수량 (mm)",
    "SWXM": "성숙기 토양 가용수분 (mm)",
    "PRCP": "파종~수확 강수량 (mm)",
    "ETCP": "파종~수확 증발산량 (mm)",
    "ESCP": "파종~수확 토양 증발량 (mm)",
    "EPCP": "파종~수확 식물 증산량 (mm)",

    # ── 질소(Nitrogen) ────────────────────────────────────────
    "NI#M":  "질소 시비 횟수",
    "NICM":  "무기질 N 시비 총량 (kg N/ha)",
    "NFXM":  "시즌 N 고정량 (kg N/ha)",
    "NUCM":  "시즌 N 흡수량 (kg N/ha)",
    "NLCM":  "시즌 N 용탈량 (kg N/ha)",
    "NIAM":  "성숙기 토양 무기 N (kg N/ha)",
    "NMINC": "시즌 누적 순 N 무기화량 (kg N/ha)",
    "CNAM":  "성숙기 지상부 N 함량 (kg N/ha)",
    "GNAM":  "성숙기 곡립 N 함량 (kg N/ha)",
    "N2OEM": "성숙기 누적 N₂O 배출량 (kg N/ha)",

    # ── 인(P) / 칼륨(K) / 잔류물 ───────────────────────────────
    "PI#M": "인(P) 시비 횟수",
    "PICM": "무기질 P 시비 총량 (kg P/ha)",
    "PUPC": "시즌 누적 P 흡수량 (kg P/ha)",
    "SPAM": "성숙기 토양 P (kg P/ha)",
    "KI#M": "칼륨(K) 시비 횟수",
    "KICM": "무기질 K 시비 총량 (kg K/ha)",
    "KUPC": "시즌 누적 K 흡수량 (kg K/ha)",
    "SKAM": "성숙기 토양 K (kg K/ha)",
    "RECM": "잔류물 시용량 (kg/ha)",

    # ── 토양 유기물 / 탄소 / 온실가스 ─────────────────────────
    "ONTAM": "성숙기 총 유기 N (토양+표면, kg N/ha)",
    "ONAM":  "성숙기 토양 유기 N (kg N/ha)",
    "OPTAM": "성숙기 총 유기 P (토양+표면, kg P/ha)",
    "OPAM":  "성숙기 토양 유기 P (kg P/ha)",
    "OCTAM": "성숙기 총 유기 C (토양+표면, kg C/ha)",
    "OCAM":  "성숙기 토양 유기 C (kg C/ha)",
    "CO2EM": "누적 순 CO₂ 배출량 (kg C/ha)",
    "CH4EM": "성숙기 누적 메탄 배출량 (kg C/ha)",

    # ── 자원-생산성 (DM/Yield per resource) ────────────────────
    "DMPPM": "강수당 건물생산성 (kg DM/ha/mm rain)",
    "DMPEM": "증발산당 건물생산성 (kg DM/ha/mm ET)",
    "DMPTM": "증산당 건물생산성 (kg DM/ha/mm EP)",
    "DMPIM": "관개당 건물생산성 (kg DM/ha/mm irrig)",
    "YPPM":  "강수당 수확량 생산성 (kg yield/ha/mm rain)",
    "YPEM":  "증발산당 수확량 생산성 (kg yield/ha/mm ET)",
    "YPTM":  "증산당 수확량 생산성 (kg yield/ha/mm EP)",
    "YPIM":  "관개당 수확량 생산성 (kg yield/ha/mm irrig)",
    "DPNAM": "N 비료당 건물생산성 (kg DM/kg N 시비)",
    "DPNUM": "N 흡수당 건물생산성 (kg DM/kg N 흡수)",
    "YPNAM": "N 비료당 수확량 생산성 (kg yield/kg N 시비)",
    "YPNUM": "N 흡수당 수확량 생산성 (kg yield/kg N 흡수)",

    # ── 기후 (생육기 평균) ────────────────────────────────────
    "TMAXA": "생육기 평균 최고기온 (°C, 파종~수확)",
    "TMINA": "생육기 평균 최저기온 (°C, 파종~수확)",
    "SRADA": "생육기 평균 일사량 (MJ/m²/d, 파종~수확)",
    "DAYLA": "생육기 평균 일장 (hr/d, 파종~수확)",
    "CO2A":  "생육기 평균 대기 CO₂ (ppm, 파종~수확)",

    # ── 종료 상태 ─────────────────────────────────────────────
    "CRST":  "시즌 종료 시 작물 상태 코드 (성숙/실패 등)",
}


def verify_against_combined(rows, combined_csv: Path):
    """combined CSV 헤더를 사전과 대조. 결과를 3그룹으로 분류:
       found / expected_missing(메타) / unexpected_missing(진짜 문제).
    """
    with combined_csv.open("r", encoding="utf-8") as f:
        header = next(csv.reader(f))
    header = [h.strip() for h in header if h.strip()]

    cde_set = {r[0] for r in rows}
    found, expected_missing, unexpected_missing = [], [], []
    for col in header:
        lookup = RENAME_BACK.get(col, col)
        if lookup in cde_set:
            found.append(col)
        elif lookup in STRUCTURAL_COLS:
            expected_missing.append(col)
        else:
            unexpected_missing.append((col, lookup))
    return header, found, expected_missing, unexpected_missing


def build_header_lookup(rows, combined_csv: Path):
    """combined CSV의 실제 헤더 컬럼 순서대로 (column, cde, section, label, description) 생성.

    - 사전에서 가장 잘 맞는 엔트리 사용 (SUMMARY 섹션 우선, 다음 GROWTH/WATER/…).
    - 메타 컬럼은 STRUCTURAL_DESC에서 채움.
    - CropCodeST 같은 rename 충돌은 원래 CDE(CRST)를 추적해 매핑.
    """
    section_priority = ["SUMMARY", "GROWTH", "WATER", "NITROGEN", "CARBON",
                        "FRESH WEIGHT", "Greenhouse Gas Emissions"]

    by_cde = {}  # cde → 가장 우선순위 높은 (section, label, description, synonyms)
    for cde, section, label, desc, syn in rows:
        if cde not in by_cde:
            by_cde[cde] = (section, label, desc, syn)
        else:
            cur_section = by_cde[cde][0]
            cur_rank = section_priority.index(cur_section) if cur_section in section_priority else 999
            new_rank = section_priority.index(section) if section in section_priority else 999
            if new_rank < cur_rank:
                by_cde[cde] = (section, label, desc, syn)

    with combined_csv.open("r", encoding="utf-8") as f:
        header = next(csv.reader(f))
    header = [h.strip() for h in header if h.strip()]

    out = []
    for col in header:
        # 1) 메타 컬럼
        if col in STRUCTURAL_DESC:
            section, label, desc = STRUCTURAL_DESC[col]
            kr = KR_DESC.get(col, "")
            out.append((col, "", section, label, desc, kr))
            continue
        # 2) rename된 컬럼 역추적
        lookup = RENAME_BACK.get(col, col)
        # 3) CR-그리디 충돌: CropCodeXXX → CRXXX 로 재시도
        if lookup not in by_cde and col.startswith("CropCode") and col != "CropCode":
            candidate = "CR" + col[len("CropCode"):]
            if candidate in by_cde:
                lookup = candidate
        # 4) 사전 조회 + 한글 description (CDE 우선, 컬럼명 폴백)
        kr = KR_DESC.get(lookup) or KR_DESC.get(col, "")
        if lookup in by_cde:
            section, label, desc, _ = by_cde[lookup]
            out.append((col, lookup, section, label, desc, kr))
        else:
            out.append((col, lookup, "UNKNOWN", "", "", kr))
    return out


def write_header_lookup(rows, out_path: Path):
    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["column", "cde", "section", "label", "description", "description_kr"])
        w.writerows(rows)


def detect_rename_collisions(rows, combined_csv: Path):
    """App.java의 .replace("CR","CropCode")는 그리디해서 CR을 포함한 다른 CDE도
    오염시킨다. 헤더의 'CropCode'로 시작하지만 'CropCode' 자체가 아닌 항목을
    검사해 원래 CDE를 역추정한다 (예: CropCodeST ← CRST)."""
    with combined_csv.open("r", encoding="utf-8") as f:
        header = next(csv.reader(f))
    cde_set = {r[0] for r in rows}
    suspects = []
    for col in header:
        col = col.strip()
        if col.startswith("CropCode") and col not in ("CropCode",):
            suffix = col[len("CropCode"):]
            candidate = "CR" + suffix
            if candidate in cde_set:
                suspects.append((col, candidate))
    return suspects


def main():
    rows = parse_dictionary(DICT_FILE)
    print(f"> Parsed {len(rows)} dictionary entries from {DICT_FILE.name}")

    # 중복 CDE 확인 (다중 섹션 등장)
    seen, dupes = {}, []
    for r in rows:
        key = r[0]
        if key in seen:
            dupes.append((key, seen[key], r[1]))
        else:
            seen[key] = r[1]
    if dupes:
        print(f"> Duplicate CDEs across sections: {len(dupes)} (first 5: {dupes[:5]})")

    write_csv(rows, OUT_CSV)
    print(f"> Wrote {OUT_CSV} ({OUT_CSV.stat().st_size:,} bytes)")

    combined = latest_combined_csv(RESULT_DIR)
    if combined is None:
        print(f"> No combinedOutput CSV in {RESULT_DIR}; skipping header verification.")
        return 0

    header, found, expected, unexpected = verify_against_combined(rows, combined)
    print(f"> Verifying {combined.name}: {len(header)} columns")
    print(f"  found in dictionary:      {len(found)}")
    print(f"  expected missing (meta):  {len(expected)}  {expected}")
    print(f"  UNEXPECTED missing:       {len(unexpected)}")
    for col, lookup in unexpected:
        note = f"(resolved to {lookup})" if lookup != col else ""
        print(f"    - {col} {note}")

    collisions = detect_rename_collisions(rows, combined)
    if collisions:
        print("> Likely rename collisions in App.java .replace(\"CR\",\"CropCode\"):")
        for col, original_cde in collisions:
            print(f"    {col!r} appears to be the corrupted form of CDE {original_cde!r}")

    lookup_rows = build_header_lookup(rows, combined)
    write_header_lookup(lookup_rows, OUT_HEADER_CSV)
    kr_filled = sum(1 for r in lookup_rows if r[5])
    kr_missing = [r[0] for r in lookup_rows if not r[5]]
    print(f"> Wrote header lookup: {OUT_HEADER_CSV} "
          f"({len(lookup_rows)} columns, {OUT_HEADER_CSV.stat().st_size:,} bytes)")
    print(f"  한글 설명: {kr_filled}/{len(lookup_rows)} 채워짐"
          + (f", 누락: {kr_missing}" if kr_missing else ""))
    return 0 if not unexpected else 1


if __name__ == "__main__":
    sys.exit(main())
