"""
Process MapSPAM 2020 CSV files for USA and create a wide-format joined table.
"""
import csv
import os
import re

CSV_DIR = "/home/jawoo/Claude/mapspam-2020/csv"
OUTPUT_FILE = "/home/jawoo/Claude/mapspam-2020/mapspam2020_USA_wide.csv"

# Shared metadata columns (common across all files, keep from first file)
SHARED_COLS = ['grid_code', 'x', 'y', 'FIPS0', 'FIPS1', 'FIPS2',
               'ADM0_NAME', 'ADM1_NAME', 'ADM2_NAME', 'year_data']

# Columns to drop from final output
DROP_COLS = {'rec_type', 'tech_type', 'unit'}

def get_rec_tech_from_filename(fname):
    """Extract rec_type (A/H/P/Y) and tech_type (TA/TI/TR) from filename."""
    # e.g. spam2020V2r0_global_A_TA.csv
    m = re.search(r'_([AHPY])_(T[AIR])\.csv$', fname)
    if m:
        return m.group(1), m.group(2)
    raise ValueError(f"Cannot parse rec/tech from filename: {fname}")

def get_crop_base(col_name):
    """Strip tech suffix (_A, _I, _R) from crop column name."""
    # Columns like BANA_A, BANA_I, BANA_R
    if '_' in col_name:
        return col_name.rsplit('_', 1)[0]
    return col_name

# --- Step 1: Read all files, filter USA, collect data ---
# Structure: {cell_id: {col_name: value}}
all_data = {}        # {grid_code: {col: val}}
shared_meta = {}     # {grid_code: {shared_col: val}}

files = sorted([f for f in os.listdir(CSV_DIR)
                if f.endswith('.csv') and not f.endswith('.Identifier')])

print(f"Processing {len(files)} files...")

# Track all crop column names (in order) per file for output ordering
all_crop_cols = []  # ordered list of new crop column names
crop_col_set = set()

for fname in files:
    rec_type, tech_type = get_rec_tech_from_filename(fname)
    fpath = os.path.join(CSV_DIR, fname)
    print(f"  Reading {fname} (rec={rec_type}, tech={tech_type})")

    with open(fpath, encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames

        # Identify crop columns (everything except shared/drop cols)
        non_crop = set(SHARED_COLS) | DROP_COLS
        crop_cols_orig = [h for h in headers if h not in non_crop]

        # Build mapping: original col name -> new col name
        col_rename = {}
        for c in crop_cols_orig:
            base = get_crop_base(c)
            new_name = f"{base}_{rec_type}_{tech_type}"
            col_rename[c] = new_name
            if new_name not in crop_col_set:
                all_crop_cols.append(new_name)
                crop_col_set.add(new_name)

        # Read USA rows
        for row in reader:
            if row['FIPS0'] != 'US':
                continue
            gcode = row['grid_code']

            # Store shared metadata (first file that has this cell wins)
            if gcode not in shared_meta:
                shared_meta[gcode] = {col: row[col] for col in SHARED_COLS
                                       if col in row}

            # Store crop values
            if gcode not in all_data:
                all_data[gcode] = {}
            for orig, new in col_rename.items():
                val = row.get(orig, '0.0')
                all_data[gcode][new] = val

print(f"\nUSA grid cells found: {len(all_data)}")
print(f"Total crop columns before dropping zeros: {len(all_crop_cols)}")

# --- Step 2: Drop crop columns where all USA values are 0 ---
def is_zero(v):
    try:
        return float(v) == 0.0
    except (ValueError, TypeError):
        return True

nonzero_cols = []
for col in all_crop_cols:
    has_nonzero = any(
        not is_zero(all_data[g].get(col, '0'))
        for g in all_data
    )
    if has_nonzero:
        nonzero_cols.append(col)

print(f"Crop columns after dropping all-zero: {len(nonzero_cols)}")

# --- Step 3: Write output CSV ---
# Final column order: CELL5M, x, y, FIPS0, FIPS1, FIPS2, ADM0_NAME, ADM1_NAME, ADM2_NAME, year_data, [crops...]
meta_out = ['CELL5M', 'x', 'y', 'FIPS0', 'FIPS1', 'FIPS2',
            'ADM0_NAME', 'ADM1_NAME', 'ADM2_NAME', 'year_data']
output_cols = meta_out + nonzero_cols

# Sort rows by CELL5M
sorted_gcodes = sorted(all_data.keys(), key=lambda x: int(x))

with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(output_cols)

    for gcode in sorted_gcodes:
        meta = shared_meta.get(gcode, {})
        row = [
            gcode,                         # CELL5M (renamed from grid_code)
            meta.get('x', ''),
            meta.get('y', ''),
            meta.get('FIPS0', ''),
            meta.get('FIPS1', ''),
            meta.get('FIPS2', ''),
            meta.get('ADM0_NAME', ''),
            meta.get('ADM1_NAME', ''),
            meta.get('ADM2_NAME', ''),
            meta.get('year_data', ''),
        ]
        crop_row = [all_data[gcode].get(col, '0.0') for col in nonzero_cols]
        writer.writerow(row + crop_row)

print(f"\nOutput written to: {OUTPUT_FILE}")
print(f"Total rows: {len(sorted_gcodes)}, Total columns: {len(output_cols)}")
