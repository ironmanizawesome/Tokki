#!/usr/bin/env python3
"""
Add a WaterSupply column (I = irrigated, R = rainfed) to the DSSAT
maize/soybean grid pipeline for the USA.

Data source: MapSPAM 2020 harvested-area columns already in
  mapspam2020_USA_wide.csv:
    MAIZ_A_TI / MAIZ_A_TR  — maize irrigated / rainfed harvested area (ha)
    SOYB_A_TI / SOYB_A_TR  — soybean irrigated / rainfed harvested area (ha)

Assignment rule (per crop, per cell):
  TI / (TI + TR) > 0.5  →  "I"  (irrigated majority)
  otherwise              →  "R"  (rainfed majority, including TI == TR == 0)

Rows with Crops = "MZ,SB" receive a comma-separated pair matching the
PlantingDates / NFertRate convention (MZ value first, SB value second).

Output
------
  maiz_soyb_25ha_long_soil_depth_plant_nass_nfert_irr.csv
"""

import os, csv

BASE        = os.path.dirname(os.path.abspath(__file__))
INPUT_CSV   = os.path.join(BASE, "maiz_soyb_25ha_long_soil_depth_plant_nass_nfert.csv")
OUTPUT_CSV  = os.path.join(BASE, "maiz_soyb_25ha_long_soil_depth_plant_nass_nfert_irr.csv")
MAPSPAM_CSV = os.path.join(BASE, "mapspam2020_USA_wide.csv")


def build_irrigation_map():
    """Return {cell5m: {'MZ': 'I'/'R', 'SB': 'I'/'R'}} from MapSPAM areas."""
    print(f"Reading irrigation fractions from {MAPSPAM_CSV} …")
    irr = {}
    with open(MAPSPAM_CSV, newline="") as f:
        for row in csv.DictReader(f):
            cell = row["CELL5M"].strip()

            def dominant(ti_col, tr_col):
                try:
                    ti = float(row.get(ti_col, 0) or 0)
                    tr = float(row.get(tr_col, 0) or 0)
                except ValueError:
                    ti = tr = 0.0
                total = ti + tr
                return "I" if (total > 0 and ti / total > 0.5) else "R"

            irr[cell] = {
                "MZ": dominant("MAIZ_A_TI", "MAIZ_A_TR"),
                "SB": dominant("SOYB_A_TI", "SOYB_A_TR"),
            }

    print(f"  {len(irr):,} cells processed.")
    return irr


def rewrite_csv(irr_map):
    """Add WaterSupply column; write output CSV."""
    n_irr_mz = n_rf_mz = n_irr_sb = n_rf_sb = no_cell = 0

    with open(INPUT_CSV,  newline="")      as fin, \
         open(OUTPUT_CSV, "w", newline="") as fout:

        reader    = csv.DictReader(fin)
        out_fields = reader.fieldnames + ["WaterSupply"]
        writer    = csv.DictWriter(fout, fieldnames=out_fields,
                                   quoting=csv.QUOTE_ALL)
        writer.writeheader()

        for row in reader:
            cell  = row["CELL5M"].strip()
            crops = row["Crops"]
            entry = irr_map.get(cell)

            if entry is None:
                row["WaterSupply"] = ""
                no_cell += 1
                writer.writerow(row)
                continue

            parts = []
            for crop in crops.split(","):
                crop = crop.strip()
                ws = entry.get(crop, "R")
                parts.append(ws)
                if crop == "MZ":
                    if ws == "I": n_irr_mz += 1
                    else:         n_rf_mz  += 1
                elif crop == "SB":
                    if ws == "I": n_irr_sb += 1
                    else:         n_rf_sb  += 1

            row["WaterSupply"] = ",".join(parts)
            writer.writerow(row)

    print(f"\n  MZ rows  — irrigated: {n_irr_mz:,}  rainfed: {n_rf_mz:,}")
    print(f"  SB rows  — irrigated: {n_irr_sb:,}  rainfed: {n_rf_sb:,}")
    if no_cell:
        print(f"  Rows with no MapSPAM cell: {no_cell:,}  (WaterSupply left blank)")


def main():
    irr_map = build_irrigation_map()
    print(f"\nWriting {OUTPUT_CSV} …")
    rewrite_csv(irr_map)
    print("Done.")


if __name__ == "__main__":
    main()
