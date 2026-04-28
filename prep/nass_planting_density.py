#!/usr/bin/env python3
"""
Add planting density (plants/m²) for maize and soybean to the DSSAT
grid pipeline for the USA.

Data source (maize):
  USDA NASS Objective Yield Survey — "PLANT POPULATION, MEASURED IN
  PLANTS / ACRE" — state level, YEAR reference period.
  Nebraska provides irrigated / non-irrigated splits; all other states
  provide an overall average only.  Remaining states are filled from
  the built-in fallback table (state × irrigation type).

Data source (soybean):
  NASS does not publish plant-population data for soybeans.
  A regional fallback table derived from university extension seeding-rate
  publications is used.

Unit conversion: plants/acre ÷ 4046.86 = plants/m²

Assignment:
  Each grid row already carries WaterSupply ("I" or "R").  For maize the
  irrigation-specific value is applied where available; for soybean the
  same density is used regardless of irrigation status (soybeans
  compensate via branching and pod-set adjustment).

  Rows with Crops = "MZ,SB" receive a comma-separated pair matching the
  PlantingDates / NFertRate / WaterSupply convention (MZ first, SB second).

Output
------
  maiz_soyb_25ha_long_soil_depth_plant_nass_nfert_irr_dens.csv
"""

import os, csv, argparse
from collections import defaultdict

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

BASE        = os.path.dirname(os.path.abspath(__file__))
INPUT_CSV   = os.path.join(BASE, "maiz_soyb_25ha_long_soil_depth_plant_nass_nfert_irr.csv")
OUTPUT_CSV  = os.path.join(BASE, "maiz_soyb_25ha_long_soil_depth_plant_nass_nfert_irr_dens.csv")
MAPSPAM_CSV = os.path.join(BASE, "mapspam2020_USA_wide.csv")

NASS_API_URL   = "https://quickstats.nass.usda.gov/api/api_GET/"
ACRE_TO_M2     = 4046.86          # 1 acre in m²


# ── Maize fallback: {state: {"I": plants/m², "R": plants/m²}} ───────────────
# Sources: USDA NASS Objective Yield Survey averages, Iowa State / Purdue /
#   UNL / NCSU / UGA extension planting-rate guides.
# States covered by NASS API are overwritten at runtime; this table covers
# the remaining 32+ states and provides the irrigation-type split that NASS
# only reports for Nebraska.
FALLBACK_DENS_MZ = {
    # ── Corn Belt / Great Lakes ──
    "Connecticut":     {"I": 7.5, "R": 7.0},
    "Delaware":        {"I": 8.0, "R": 7.2},
    "Kentucky":        {"I": 8.0, "R": 7.0},
    "Maryland":        {"I": 8.0, "R": 7.2},
    "Michigan":        {"I": 8.0, "R": 7.2},
    "New Jersey":      {"I": 8.0, "R": 7.0},
    "New York":        {"I": 7.5, "R": 6.8},
    "North Dakota":    {"I": 7.0, "R": 6.5},
    "Pennsylvania":    {"I": 8.0, "R": 7.0},
    "Virginia":        {"I": 7.5, "R": 6.8},
    "West Virginia":   {"I": 7.5, "R": 6.5},
    # ── Great Plains ──
    "Colorado":        {"I": 8.0, "R": 5.5},
    "Montana":         {"I": 7.0, "R": 5.5},
    "Oklahoma":        {"I": 7.5, "R": 5.5},
    "Texas":           {"I": 7.5, "R": 5.5},
    "Wyoming":         {"I": 7.5, "R": 5.5},
    # ── Irrigated West ──
    "Arizona":         {"I": 8.5, "R": 7.0},
    "California":      {"I": 9.0, "R": 7.0},
    "Idaho":           {"I": 8.0, "R": 6.5},
    "New Mexico":      {"I": 8.5, "R": 6.0},
    "Oregon":          {"I": 8.0, "R": 6.5},
    "Utah":            {"I": 8.0, "R": 6.0},
    "Washington":      {"I": 8.5, "R": 6.5},
    # ── Southeast / Mid-South ──
    "Alabama":         {"I": 7.5, "R": 6.5},
    "Arkansas":        {"I": 7.8, "R": 6.8},
    "Florida":         {"I": 7.5, "R": 6.0},
    "Georgia":         {"I": 8.0, "R": 6.5},
    "Louisiana":       {"I": 7.5, "R": 6.5},
    "Mississippi":     {"I": 7.5, "R": 6.5},
    "North Carolina":  {"I": 8.0, "R": 7.0},
    "South Carolina":  {"I": 7.5, "R": 6.5},
    "Tennessee":       {"I": 7.5, "R": 6.8},
}

# ── Soybean fallback: {state: plants/m²} ────────────────────────────────────
# Source: university extension seeding-rate guides (ISU, Purdue, UNL, NCSU,
#   MSU).  Assumes ~90% field emergence; narrow-row (15") systems common in
#   the northern corn belt push densities higher.
FALLBACK_DENS_SB = {
    # Northern corn belt / Great Lakes (narrow-row common)
    "Illinois":        35.0,
    "Indiana":         35.0,
    "Iowa":            35.0,
    "Kansas":          33.0,
    "Michigan":        35.0,
    "Minnesota":       35.0,
    "Missouri":        34.0,
    "Nebraska":        33.0,
    "North Dakota":    33.0,
    "Ohio":            35.0,
    "South Dakota":    33.0,
    "Wisconsin":       35.0,
    # Mid-Atlantic / Northeast
    "Connecticut":     33.0,
    "Delaware":        34.0,
    "Maryland":        34.0,
    "New Jersey":      33.0,
    "New York":        33.0,
    "Pennsylvania":    33.0,
    "Virginia":        33.0,
    "West Virginia":   33.0,
    # Southeast / Mid-South (wider rows more common)
    "Alabama":         32.0,
    "Arkansas":        32.0,
    "Florida":         30.0,
    "Georgia":         32.0,
    "Kentucky":        34.0,
    "Louisiana":       32.0,
    "Mississippi":     32.0,
    "North Carolina":  33.0,
    "South Carolina":  32.0,
    "Tennessee":       33.0,
    "Texas":           30.0,
    "Oklahoma":        30.0,
    # Great Plains / West
    "Colorado":        30.0,
    "Montana":         30.0,
    "Wyoming":         30.0,
}

DEFAULT_DENS_MZ_I = 8.0   # irrigated fallback for unlisted states
DEFAULT_DENS_MZ_R = 7.0   # rainfed  fallback for unlisted states
DEFAULT_DENS_SB   = 33.0  # fallback for unlisted states

# ── Manual irrigated-density overrides ──────────────────────────────────────
# Applied after NASS data is loaded.  Use when NASS reports only a combined
# statewide average that underestimates irrigated-field density because the
# state has a large dryland acreage pulling the average down.
# Only the "I" key is overridden; "R" retains its NASS or fallback value.
IRR_OVERRIDES_MZ = {
    "Kansas": 7.5,   # NASS ALL=5.54 reflects heavy dryland mix; irrigated
                     # Kansas corn (High Plains) is comparable to Nebraska IRR
}


# ───────────────────────────────────────────────────────────────────────────
def pa_to_m2(plants_per_acre):
    return round(plants_per_acre / ACRE_TO_M2, 2)


def fetch_nass_corn_density(api_key, year_start=2015, year_end=2023):
    """
    Return {state: {"I": plants/m², "R": plants/m²}} from NASS.
    States without an irrigation split use the same overall value for both.
    """
    if not HAS_REQUESTS:
        raise RuntimeError("'requests' package not installed.")

    params = {
        "key":                   api_key,
        "commodity_desc":        "CORN",
        "statisticcat_desc":     "PLANT POPULATION",
        "unit_desc":             "PLANTS / ACRE",
        "reference_period_desc": "YEAR",
        "agg_level_desc":        "STATE",
        "year__GE":              str(year_start),
        "year__LE":              str(year_end),
        "format":                "JSON",
    }

    print(f"Fetching NASS corn plant population {year_start}–{year_end} …")
    resp = requests.get(NASS_API_URL, params=params, timeout=120)
    resp.raise_for_status()
    recs = resp.json().get("data", [])
    print(f"  {len(recs)} records received.")

    by_state = defaultdict(lambda: {"IRR": [], "NON": [], "ALL": []})
    for rec in recs:
        sd    = rec.get("short_desc", "")
        state = rec.get("state_name", "").strip().title()
        val   = rec.get("Value", "").replace(",", "").strip()
        try:
            v = float(val)
        except ValueError:
            continue
        if "NON-IRRIGATED" in sd:
            by_state[state]["NON"].append(v)
        elif "IRRIGATED" in sd:
            by_state[state]["IRR"].append(v)
        else:
            by_state[state]["ALL"].append(v)

    result = {}
    for state, d in by_state.items():
        avg_irr = sum(d["IRR"]) / len(d["IRR"]) if d["IRR"] else None
        avg_non = sum(d["NON"]) / len(d["NON"]) if d["NON"] else None
        avg_all = sum(d["ALL"]) / len(d["ALL"]) if d["ALL"] else None

        if avg_irr is not None and avg_non is not None:
            irr_m2 = pa_to_m2(avg_irr)
            non_m2 = pa_to_m2(avg_non)
            print(f"  {state:20s}  IRR={avg_irr:.0f} pa → {irr_m2} /m²  "
                  f"NON={avg_non:.0f} pa → {non_m2} /m²")
        elif avg_all is not None:
            irr_m2 = non_m2 = pa_to_m2(avg_all)
            print(f"  {state:20s}  ALL={avg_all:.0f} pa → {irr_m2} /m²")
        else:
            continue

        result[state] = {"I": irr_m2, "R": non_m2}

    return result


# ───────────────────────────────────────────────────────────────────────────
def build_density_tables(api_key=None):
    """Return (dens_mz, dens_sb) dicts: {state: {"I":v, "R":v}} and {state:v}."""

    # Maize: start from fallback, then overwrite with NASS data
    dens_mz = {s: dict(v) for s, v in FALLBACK_DENS_MZ.items()}

    if api_key:
        nass = fetch_nass_corn_density(api_key)
        # For NASS states that only have ALL (no IRR/NON split), we still
        # apply the value to both irrigation types.  For Nebraska the split
        # values replace the fallback.
        for state, vals in nass.items():
            dens_mz[state] = vals
        missing = [s for s in FALLBACK_DENS_MZ if s not in nass]
        if missing:
            print(f"\n  {len(missing)} states filled from fallback: "
                  f"{', '.join(missing)}")
    else:
        print("No API key — using built-in fallback table for maize.")

    # Apply manual irrigated overrides (after NASS / fallback are merged)
    for state, irr_val in IRR_OVERRIDES_MZ.items():
        if state in dens_mz:
            old = dens_mz[state]["I"]
            dens_mz[state]["I"] = irr_val
            print(f"  Override: {state} irrigated {old} → {irr_val} /m²")
        else:
            dens_mz[state] = {"I": irr_val, "R": DEFAULT_DENS_MZ_R}

    dens_sb = dict(FALLBACK_DENS_SB)
    return dens_mz, dens_sb


# ───────────────────────────────────────────────────────────────────────────
def build_cell_state_map():
    cell_state = {}
    with open(MAPSPAM_CSV, newline="") as f:
        for row in csv.DictReader(f):
            cell  = row.get("CELL5M", "").strip()
            state = row.get("ADM1_NAME", "").strip()
            if cell and state:
                cell_state[cell] = state
    return cell_state


# ───────────────────────────────────────────────────────────────────────────
def rewrite_csv(dens_mz, dens_sb, cell_state):
    no_cell = no_rate = written = 0

    with open(INPUT_CSV,  newline="")      as fin, \
         open(OUTPUT_CSV, "w", newline="") as fout:

        reader     = csv.DictReader(fin)
        out_fields = reader.fieldnames + ["PlantingDensity"]
        writer     = csv.DictWriter(fout, fieldnames=out_fields,
                                    quoting=csv.QUOTE_ALL)
        writer.writeheader()

        for row in reader:
            cell   = row["CELL5M"].strip()
            crops  = row["Crops"]
            ws_raw = row.get("WaterSupply", "")

            state = cell_state.get(cell)
            if state is None:
                row["PlantingDensity"] = ""
                no_cell += 1
                writer.writerow(row)
                continue

            crop_list = crops.split(",")
            ws_list   = ws_raw.split(",") if ws_raw else ["R"] * len(crop_list)
            # Guard against mismatched lengths
            while len(ws_list) < len(crop_list):
                ws_list.append("R")

            parts = []
            for crop, ws in zip(crop_list, ws_list):
                crop = crop.strip()
                ws   = ws.strip()

                if crop == "MZ":
                    state_mz = dens_mz.get(state)
                    if state_mz:
                        val = state_mz.get(ws, state_mz.get("R", DEFAULT_DENS_MZ_R))
                    else:
                        val = DEFAULT_DENS_MZ_I if ws == "I" else DEFAULT_DENS_MZ_R
                        no_rate += 1
                elif crop == "SB":
                    val = dens_sb.get(state, DEFAULT_DENS_SB)
                else:
                    val = ""
                parts.append(str(val) if val != "" else "")

            row["PlantingDensity"] = ",".join(parts)
            written += 1
            writer.writerow(row)

    print(f"\n  Rows written              : {written:,}")
    if no_cell:
        print(f"  Rows – no cell mapping    : {no_cell:,}  (PlantingDensity blank)")
    if no_rate:
        print(f"  Rows – used global default: {no_rate:,}")


# ───────────────────────────────────────────────────────────────────────────
def print_tables(dens_mz, dens_sb):
    print(f"\nMaize planting density table ({len(dens_mz)} states):")
    for s in sorted(dens_mz):
        d = dens_mz[s]
        print(f"  {s:22s}  I={d['I']} /m²  R={d['R']} /m²")
    print(f"\nSoybean planting density table ({len(dens_sb)} states):")
    for s in sorted(dens_sb):
        print(f"  {s:22s}  {dens_sb[s]} /m²")


# ───────────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description=__doc__,
                formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--api-key", default=os.environ.get("NASS_API_KEY", ""),
                        help="NASS Quick Stats API key (or set NASS_API_KEY)")
    parser.add_argument("--year-start", type=int, default=2015)
    parser.add_argument("--year-end",   type=int, default=2023)
    parser.add_argument("--use-fallback", action="store_true",
                        help="Force use of built-in fallback table")
    args = parser.parse_args()

    api_key = None if (args.use_fallback or not args.api_key) else args.api_key
    if not api_key:
        reason = "--use-fallback" if args.use_fallback else "no API key provided"
        print(f"Using built-in fallback ({reason}).")

    dens_mz, dens_sb = build_density_tables(api_key)
    print_tables(dens_mz, dens_sb)

    cell_state = build_cell_state_map()
    print(f"\nWriting {OUTPUT_CSV} …")
    rewrite_csv(dens_mz, dens_sb, cell_state)
    print("Done.")


if __name__ == "__main__":
    main()
