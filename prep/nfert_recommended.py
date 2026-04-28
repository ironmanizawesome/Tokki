#!/usr/bin/env python3
"""
Add recommended nitrogen fertilizer rates (NFertRateRec, kg N/ha) and
rename the existing NFertRate column to NFertRateAct in the DSSAT grid
pipeline for the USA.

Recommended rates
-----------------
Maize:
  Seven MRTN states (IA, IL, IN, MI, MN, OH, WI): Maximum Return to N
    values from the Corn Nitrogen Rate Calculator, corn-after-soybean
    scenario, mid price ratio (~$5/bu corn, ~$0.50/lb N).
    Reference: Sawyer et al. (2006) "Concepts and Rationale for Regional
    Nitrogen Rate Guidelines for Corn", Iowa State Univ. Extension PM 2015;
    updated state bulletins 2020–2023.
  All other states: state land-grant university extension recommendations
    (primary sources: UNL, KSU, TAMU, NCSU, UGA, UC Davis, etc.).
  Irrigation-specific rates applied for states where extension guidelines
    distinguish irrigated from rainfed management; WaterSupply column
    (already present in the input file) is used to select the value.

Soybean:
  Recommended = 0 kg N/ha.  Soybeans meet N demand through biological
  N fixation (BNF); synthetic N is agronomically unnecessary under normal
  conditions with adequate nodulation.

Unit: kg N/ha  (lb/acre × 1.12085)

Input : maiz_soyb_25ha_long_soil_depth_plant_nass_nfert_irr_dens.csv
Output: maiz_soyb_25ha_long_soil_depth_plant_nass_nfert_irr_dens_nrec.csv
"""

import os, csv

BASE      = os.path.dirname(os.path.abspath(__file__))
INPUT_CSV = os.path.join(BASE,
    "maiz_soyb_25ha_long_soil_depth_plant_nass_nfert_irr_dens.csv")
OUTPUT_CSV = os.path.join(BASE,
    "maiz_soyb_25ha_long_soil_depth_plant_nass_nfert_irr_dens_nrec.csv")
MAPSPAM_CSV = os.path.join(BASE, "mapspam2020_USA_wide.csv")

LB_ACRE_TO_KG_HA = 1.12085

# ── Recommended N rates for maize (lb N/acre) ────────────────────────────────
# Each entry: {"I": irrigated_rate, "R": rainfed_rate}
# Where guidelines do not distinguish by irrigation, I == R.
#
# MRTN states use the Corn Nitrogen Rate Calculator corn-after-soybean
# mid-price scenario.  All other states use published extension guides.
REC_N_MZ_LB = {
    # ── MRTN states ─────────────────────────────────────────
    "Illinois":       {"I": 155, "R": 155},   # UI MRTN
    "Indiana":        {"I": 155, "R": 155},   # Purdue MRTN
    "Iowa":           {"I": 150, "R": 150},   # ISU MRTN
    "Michigan":       {"I": 145, "R": 145},   # MSU MRTN
    "Minnesota":      {"I": 145, "R": 145},   # UMN MRTN
    "Ohio":           {"I": 155, "R": 155},   # OSU MRTN
    "Wisconsin":      {"I": 140, "R": 140},   # UW MRTN
    # ── Other corn belt / Great Lakes ───────────────────────
    "Connecticut":    {"I": 125, "R": 125},
    "Delaware":       {"I": 130, "R": 130},
    "Kentucky":       {"I": 140, "R": 140},   # UK Extension
    "Maryland":       {"I": 130, "R": 130},
    "Missouri":       {"I": 140, "R": 140},   # MU Extension
    "New Jersey":     {"I": 130, "R": 130},
    "New York":       {"I": 120, "R": 120},   # Cornell
    "Pennsylvania":   {"I": 120, "R": 120},   # PSU
    "Virginia":       {"I": 120, "R": 120},   # VA Tech
    "West Virginia":  {"I": 120, "R": 120},
    # ── Northern / Central Plains ────────────────────────────
    "Kansas":         {"I": 130, "R": 100},   # KSU Extension
    "Montana":        {"I": 100, "R":  80},   # MSU Extension
    "Nebraska":       {"I": 160, "R": 130},   # UNL NebGuide
    "North Dakota":   {"I": 115, "R": 110},   # NDSU Extension
    "Oklahoma":       {"I": 110, "R":  90},   # OSU Extension
    "South Dakota":   {"I": 130, "R": 120},   # SDSU Extension
    "Wyoming":        {"I": 120, "R":  80},   # UW Extension
    # ── Irrigated West ───────────────────────────────────────
    "Arizona":        {"I": 150, "R": 120},   # AZ irrigated guide
    "California":     {"I": 175, "R": 140},   # UC Davis
    "Colorado":       {"I": 135, "R": 100},   # CSU Extension
    "Idaho":          {"I": 150, "R": 110},   # UI Extension
    "New Mexico":     {"I": 150, "R": 110},   # NMSU
    "Oregon":         {"I": 140, "R": 110},   # OSU irrigated
    "Utah":           {"I": 145, "R": 110},   # USU
    "Washington":     {"I": 150, "R": 110},   # WSU
    # ── Southeast / Mid-South ────────────────────────────────
    "Alabama":        {"I": 110, "R":  90},   # Auburn
    "Arkansas":       {"I": 130, "R": 120},   # UA Extension
    "Florida":        {"I": 140, "R": 120},   # UF/IFAS
    "Georgia":        {"I": 130, "R": 115},   # UGA Extension
    "Louisiana":      {"I": 130, "R": 120},   # LSU AgCenter
    "Mississippi":    {"I": 130, "R": 120},   # MSU Extension
    "North Carolina": {"I": 135, "R": 130},   # NCSU Extension
    "South Carolina": {"I": 110, "R": 100},   # Clemson
    "Tennessee":      {"I": 130, "R": 120},   # UT Extension
    "Texas":          {"I": 140, "R": 100},   # TAMU Extension
}

DEFAULT_REC_MZ_I = 140   # irrigated default for any unlisted state (lb/acre)
DEFAULT_REC_MZ_R = 120   # rainfed  default for any unlisted state (lb/acre)


def lb_to_kg(lb):
    return round(lb * LB_ACRE_TO_KG_HA, 1)


# Convert table to kg/ha at import time
REC_N_MZ_KG = {
    state: {"I": lb_to_kg(v["I"]), "R": lb_to_kg(v["R"])}
    for state, v in REC_N_MZ_LB.items()
}
DEFAULT_REC_MZ_I_KG = lb_to_kg(DEFAULT_REC_MZ_I)
DEFAULT_REC_MZ_R_KG = lb_to_kg(DEFAULT_REC_MZ_R)


def build_cell_state_map():
    cell_state = {}
    with open(MAPSPAM_CSV, newline="") as f:
        for row in csv.DictReader(f):
            cell  = row.get("CELL5M", "").strip()
            state = row.get("ADM1_NAME", "").strip()
            if cell and state:
                cell_state[cell] = state
    return cell_state


def rewrite_csv(cell_state):
    no_cell = no_rate = written = 0

    with open(INPUT_CSV,  newline="")      as fin, \
         open(OUTPUT_CSV, "w", newline="") as fout:

        reader = csv.DictReader(fin)

        # Rename NFertRate → NFertRateAct; insert NFertRateRec immediately after
        old_fields = reader.fieldnames
        renamed = ["NFertRateAct" if f == "NFertRate" else f for f in old_fields]
        idx = renamed.index("NFertRateAct")
        new_fields = renamed[:idx+1] + ["NFertRateRec"] + renamed[idx+1:]

        writer = csv.DictWriter(fout, fieldnames=new_fields,
                                quoting=csv.QUOTE_ALL)
        writer.writeheader()

        for row in reader:
            # Rename key in-place
            row["NFertRateAct"] = row.pop("NFertRate")

            cell  = row["CELL5M"].strip()
            crops = row["Crops"]
            ws_raw = row.get("WaterSupply", "")

            state = cell_state.get(cell)
            if state is None:
                row["NFertRateRec"] = ""
                no_cell += 1
                writer.writerow(row)
                continue

            crop_list = crops.split(",")
            ws_list   = ws_raw.split(",") if ws_raw else ["R"] * len(crop_list)
            while len(ws_list) < len(crop_list):
                ws_list.append("R")

            rec_parts = []
            for crop, ws in zip(crop_list, ws_list):
                crop = crop.strip()
                ws   = ws.strip()
                if crop == "MZ":
                    entry = REC_N_MZ_KG.get(state)
                    if entry:
                        val = entry.get(ws, entry["R"])
                    else:
                        val = DEFAULT_REC_MZ_I_KG if ws == "I" \
                              else DEFAULT_REC_MZ_R_KG
                        no_rate += 1
                elif crop == "SB":
                    val = 0.0
                else:
                    val = ""
                rec_parts.append(str(val) if val != "" else "")

            row["NFertRateRec"] = ",".join(rec_parts)
            written += 1
            writer.writerow(row)

    print(f"  Rows written              : {written:,}")
    if no_cell:
        print(f"  Rows – no cell mapping    : {no_cell:,}  (NFertRateRec blank)")
    if no_rate:
        print(f"  Rows – used global default: {no_rate:,}")


def print_table():
    print(f"\nMaize recommended N rate table ({len(REC_N_MZ_KG)} states):")
    for s in sorted(REC_N_MZ_KG):
        d = REC_N_MZ_KG[s]
        flag = " *MRTN*" if REC_N_MZ_LB.get(s, {}).get("I") in \
               [140, 145, 150, 155] and s in \
               ["Illinois","Indiana","Iowa","Michigan","Minnesota","Ohio","Wisconsin"] \
               else ""
        print(f"  {s:22s}  I={d['I']:6.1f} kg/ha  R={d['R']:6.1f} kg/ha{flag}")
    print("\nSoybean recommended N rate: 0.0 kg/ha (all states)")


def main():
    print(f"Reading {INPUT_CSV} …")
    cell_state = build_cell_state_map()
    print_table()
    print(f"\nWriting {OUTPUT_CSV} …")
    rewrite_csv(cell_state)
    print("Done.")


if __name__ == "__main__":
    main()
