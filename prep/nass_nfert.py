#!/usr/bin/env python3
"""
Add state-level nitrogen fertilizer application rates (kg N/ha) to the
DSSAT maize/soybean grid pipeline for the USA.

Data source: USDA NASS Chemical Use Survey (Quick Stats API)
  Commodity : CORN / SOYBEANS
  Domain    : FERTILIZER: (NITROGEN)
  Statistic : APPLICATIONS, MEASURED IN LB / ACRE
  Level     : STATE

Approach
--------
1. Fetch state-level N application rates from NASS Quick Stats API.
2. Average across available survey years.
3. Build a CELL5M → state lookup from mapspam2020_USA_wide.csv.
4. For each row, assign the state N rate for the crop type(s).
   Rows with Crops="MZ,SB" get a comma-separated pair (MZ rate, SB rate),
   matching the PlantingDates convention.
5. Write output CSV with an added NFertRate column (kg N/ha).

Unit conversion: lb/acre × 1.12085 = kg/ha

Requirements
------------
  pip install requests

API key
-------
  Free key from: https://quickstats.nass.usda.gov/api
  Pass via --api-key, or set the NASS_API_KEY environment variable.
  If neither provided, the built-in fallback table is used.

Output
------
  maiz_soyb_25ha_long_soil_depth_plant_nass_nfert.csv
"""

import os, csv, argparse
from collections import defaultdict

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

BASE        = os.path.dirname(os.path.abspath(__file__))
INPUT_CSV   = os.path.join(BASE, "maiz_soyb_25ha_long_soil_depth_plant_nass.csv")
OUTPUT_CSV  = os.path.join(BASE, "maiz_soyb_25ha_long_soil_depth_plant_nass_nfert.csv")
MAPSPAM_CSV = os.path.join(BASE, "mapspam2020_USA_wide.csv")

NASS_API_URL    = "https://quickstats.nass.usda.gov/api/api_GET/"
LB_ACRE_TO_KG_HA = 1.12085

# ── Fallback tables: state N application rate (lb N/acre) ───────────────────
# Source: USDA NASS Chemical Use surveys (2019, 2021, 2023 averages)
# Reference: USDA NASS "Corn Objective Yield" and "Agricultural Chemical Use"
#   survey publications. States not listed default to 0.

FALLBACK_N_MZ = {
    "Alabama":         90,
    "Arizona":        155,
    "Arkansas":       130,
    "California":     155,
    "Colorado":       125,
    "Connecticut":    115,
    "Delaware":       130,
    "Florida":         80,
    "Georgia":         90,
    "Idaho":          145,
    "Illinois":       155,
    "Indiana":        155,
    "Iowa":           150,
    "Kansas":         130,
    "Kentucky":       130,
    "Louisiana":      130,
    "Maryland":       130,
    "Michigan":       130,
    "Minnesota":      150,
    "Mississippi":    110,
    "Missouri":       130,
    "Montana":         90,
    "Nebraska":       155,
    "New Jersey":     130,
    "New Mexico":     135,
    "New York":       120,
    "North Carolina": 110,
    "North Dakota":   110,
    "Ohio":           145,
    "Oklahoma":        95,
    "Oregon":         130,
    "Pennsylvania":   130,
    "South Carolina":  90,
    "South Dakota":   115,
    "Tennessee":      115,
    "Texas":          125,
    "Utah":           130,
    "Virginia":       120,
    "Washington":     145,
    "West Virginia":  120,
    "Wisconsin":      145,
    "Wyoming":        110,
}

# Soybeans fix atmospheric N; synthetic N is primarily starter fertilizer.
FALLBACK_N_SB = {
    "Alabama":          5,
    "Arkansas":        10,
    "Delaware":         5,
    "Georgia":          5,
    "Illinois":         5,
    "Indiana":          5,
    "Iowa":             5,
    "Kansas":           5,
    "Kentucky":         5,
    "Louisiana":        5,
    "Maryland":         5,
    "Michigan":         5,
    "Minnesota":        5,
    "Mississippi":      5,
    "Missouri":         5,
    "Nebraska":         5,
    "North Carolina":   5,
    "North Dakota":     5,
    "Ohio":             5,
    "Pennsylvania":     5,
    "South Carolina":   5,
    "South Dakota":     5,
    "Tennessee":        5,
    "Texas":            5,
    "Virginia":         5,
    "Wisconsin":        5,
}


# ───────────────────────────────────────────────────────────────────────────
def fetch_nass_nfert(api_key, commodity, year_start=2015, year_end=2023):
    """
    Return {state_name: avg_kg_ha} for N fertilizer application rate.
    commodity: "CORN" or "SOYBEANS"
    """
    if not HAS_REQUESTS:
        raise RuntimeError("'requests' package not installed. Run: pip install requests")

    params = {
        "key":               api_key,
        "commodity_desc":    commodity,
        "statisticcat_desc": "APPLICATIONS",
        "unit_desc":         "LB / ACRE / YEAR, AVG",
        "domain_desc":       "FERTILIZER",
        "domaincat_desc":    "FERTILIZER: (NITROGEN)",
        "agg_level_desc":    "STATE",
        "freq_desc":         "ANNUAL",
        "year__GE":          str(year_start),
        "year__LE":          str(year_end),
        "format":            "JSON",
    }

    label = f"{commodity} N fertilizer {year_start}–{year_end}"
    print(f"Fetching NASS {label} …")
    resp = requests.get(NASS_API_URL, params=params, timeout=120)
    resp.raise_for_status()
    data = resp.json()

    if "data" not in data:
        raise ValueError(f"Unexpected NASS API response: {list(data.keys())}")

    # Keep only records where domaincat contains "NITROGEN"
    by_state = defaultdict(list)
    skipped = 0
    for rec in data["data"]:
        domaincat = rec.get("domaincat_desc", "")
        if "NITROGEN" not in domaincat.upper():
            skipped += 1
            continue
        state   = rec.get("state_name", "").strip().title()
        val_str = rec.get("Value", "").strip().replace(",", "")
        if not state or val_str in ("", "(D)", "(Z)", "(NA)"):
            skipped += 1
            continue
        try:
            lb_acre = float(val_str)
            by_state[state].append(lb_acre)
        except ValueError:
            skipped += 1

    print(f"  Parsed {len(data['data'])} records, {skipped} skipped.")

    state_kg_ha = {}
    for state, vals in by_state.items():
        avg_lb = sum(vals) / len(vals)
        kg_ha  = round(avg_lb * LB_ACRE_TO_KG_HA, 1)
        state_kg_ha[state] = kg_ha
        print(f"    {state:25s}  n={len(vals):2d}  avg={avg_lb:.1f} lb/ac  "
              f"= {kg_ha:.1f} kg/ha")

    return state_kg_ha


# ───────────────────────────────────────────────────────────────────────────
def lb_to_kg(lb_acre):
    return round(lb_acre * LB_ACRE_TO_KG_HA, 1)


def build_fallback_kg(fallback_lb):
    return {state: lb_to_kg(v) for state, v in fallback_lb.items()}


# ───────────────────────────────────────────────────────────────────────────
def build_cell_state_map():
    """Return {cell5m_str: state_name} from mapspam2020_USA_wide.csv."""
    print(f"Building CELL5M → state map from {MAPSPAM_CSV} …")
    cell_state = {}
    with open(MAPSPAM_CSV, newline="") as f:
        for row in csv.DictReader(f):
            state = row.get("ADM1_NAME", "").strip()
            cell  = row.get("CELL5M",    "").strip()
            if cell and state:
                cell_state[cell] = state
    print(f"  {len(cell_state):,} cells mapped.")
    return cell_state


# ───────────────────────────────────────────────────────────────────────────
def rewrite_csv(nfert_mz, nfert_sb, cell_state):
    """Add NFertRate column (kg N/ha) to each row; write output CSV."""
    updated = skipped_no_state = skipped_no_rate = 0

    with open(INPUT_CSV,  newline="")       as fin, \
         open(OUTPUT_CSV, "w", newline="")  as fout:

        reader    = csv.DictReader(fin)
        out_fields = reader.fieldnames + ["NFertRate"]
        writer    = csv.DictWriter(fout, fieldnames=out_fields,
                                   quoting=csv.QUOTE_ALL)
        writer.writeheader()

        for row in reader:
            crops = row["Crops"]
            cell  = row["CELL5M"].strip()
            state = cell_state.get(cell)

            if state is None:
                row["NFertRate"] = ""
                skipped_no_state += 1
                writer.writerow(row)
                continue

            rates = []
            missing = False
            for crop in crops.split(","):
                crop = crop.strip()
                if crop == "MZ":
                    r = nfert_mz.get(state)
                elif crop == "SB":
                    r = nfert_sb.get(state)
                else:
                    r = None

                if r is None:
                    rates.append("0.0")
                    missing = True
                else:
                    rates.append(str(r))

            if missing:
                skipped_no_rate += 1

            row["NFertRate"] = ",".join(rates)
            updated += 1
            writer.writerow(row)

    print(f"\n  Rows written             : {updated:,}")
    if skipped_no_state:
        print(f"  Rows – no state mapping  : {skipped_no_state:,}  (NFertRate left blank)")
    if skipped_no_rate:
        print(f"  Rows – no rate in table  : {skipped_no_rate:,}  (defaulted to 0.0)")


# ───────────────────────────────────────────────────────────────────────────
def print_table(label, rates_kg):
    print(f"\n{label} N application rate table ({len(rates_kg)} states):")
    for state in sorted(rates_kg):
        print(f"  {state:25s}  {rates_kg[state]:.1f} kg N/ha")


# ───────────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description=__doc__,
                formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--api-key", default=os.environ.get("NASS_API_KEY", ""),
                        help="NASS Quick Stats API key (or set NASS_API_KEY env var)")
    parser.add_argument("--year-start", type=int, default=2015)
    parser.add_argument("--year-end",   type=int, default=2023)
    parser.add_argument("--use-fallback", action="store_true",
                        help="Force use of built-in fallback table")
    args = parser.parse_args()

    # ── 1. Get N rates ───────────────────────────────────────────────────
    if args.use_fallback or not args.api_key:
        if not args.api_key:
            print("No NASS API key – using built-in fallback table.")
            print("(Get a free key at https://quickstats.nass.usda.gov/api)")
        else:
            print("--use-fallback specified – using built-in fallback table.")
        nfert_mz = build_fallback_kg(FALLBACK_N_MZ)
        nfert_sb = build_fallback_kg(FALLBACK_N_SB)
    else:
        nfert_mz = fetch_nass_nfert(args.api_key, "CORN",
                                    args.year_start, args.year_end)
        nfert_sb = fetch_nass_nfert(args.api_key, "SOYBEANS",
                                    args.year_start, args.year_end)

        # Fill gaps from fallback
        fallback_mz_kg = build_fallback_kg(FALLBACK_N_MZ)
        fallback_sb_kg = build_fallback_kg(FALLBACK_N_SB)
        for state, v in fallback_mz_kg.items():
            nfert_mz.setdefault(state, v)
        for state, v in fallback_sb_kg.items():
            nfert_sb.setdefault(state, v)

    print_table("Maize", nfert_mz)
    print_table("Soybean", nfert_sb)

    # ── 2. Build CELL5M → state lookup ──────────────────────────────────
    cell_state = build_cell_state_map()

    # ── 3. Rewrite CSV ───────────────────────────────────────────────────
    print(f"\nWriting {OUTPUT_CSV} …")
    rewrite_csv(nfert_mz, nfert_sb, cell_state)
    print("Done.")


if __name__ == "__main__":
    main()
