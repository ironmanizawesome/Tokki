#!/usr/bin/env python3
"""
Read plant.asc from each crop-calendar folder and build a wide-format CSV:
  CELL5M, Barley, Barley.Winter, Cassava, ...

CELL5M = flat raster index (row * ncols + col), identical to the 5-arcmin cell ID.
Uses only the standard library — no numpy/pandas required.
"""

import os
import csv

BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
OUT_CSV      = os.path.join(BASE_DIR, "plant_dates_CELL5M.csv")
NODATA_LIMIT = 1e18   # values >= this are NODATA
HEADER_LINES = 6
NCOLS, NROWS = 4320, 2160
XRES = 360.0 / NCOLS   # 1/12 degree
YRES = 180.0 / NROWS


def cell_coords(cell_id):
    """Return (x, y) centre coordinates for a CELL5M id."""
    col = cell_id % NCOLS
    row = cell_id // NCOLS
    x = round(-180.0 + (col + 0.5) * XRES, 10)
    y = round( 90.0  - (row + 0.5) * YRES, 10)
    return x, y


def crop_name(folder):
    return folder.replace(".crop.calendar.fill", "")


def read_plant_asc(path):
    """Return a dict {cell_id: int_value} for all valid (non-NODATA) cells."""
    data = {}
    cell_id = 0
    with open(path, "r") as fh:
        for _ in range(HEADER_LINES):
            next(fh)
        for line in fh:
            for tok in line.split():
                v = float(tok)
                if v < NODATA_LIMIT:
                    data[cell_id] = int(round(v))
                cell_id += 1
    return data


def main():
    folders = sorted(
        d for d in os.listdir(BASE_DIR)
        if os.path.isdir(os.path.join(BASE_DIR, d)) and d.endswith(".crop.calendar.fill")
    )
    print(f"Found {len(folders)} crop folders.")

    crop_names = []
    all_data   = []   # list of dicts, one per crop

    for folder in folders:
        asc_path = os.path.join(BASE_DIR, folder, "plant.asc")
        if not os.path.isfile(asc_path):
            print(f"  SKIP (no plant.asc): {folder}")
            continue
        name = crop_name(folder)
        print(f"  Reading: {name} ...", end=" ", flush=True)
        d = read_plant_asc(asc_path)
        print(f"{len(d):,} valid cells")
        crop_names.append(name)
        all_data.append(d)

    # Union of all cell IDs that have at least one valid value
    all_cells = sorted(set().union(*all_data))
    print(f"\nTotal unique valid cells: {len(all_cells):,}")

    print(f"Writing {OUT_CSV} ...")
    with open(OUT_CSV, "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["CELL5M", "X", "Y"] + crop_names)
        for cid in all_cells:
            x, y = cell_coords(cid)
            row = [cid, x, y] + [d.get(cid, "") for d in all_data]
            writer.writerow(row)

    print(f"Done. {len(all_cells):,} rows × {1 + len(crop_names)} columns.")


if __name__ == "__main__":
    main()
