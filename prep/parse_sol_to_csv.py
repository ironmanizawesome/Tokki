#!/usr/bin/env python3
"""
Parse US.SOL (DSSAT soil profile file) and produce a CSV with:
  CELL5M, SoilProfileID, SoilProfile
"""

import csv
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
from cell_id import get_cell_id

SOL_FILE = os.path.join(os.path.dirname(__file__), "US.SOL")
CSV_FILE = os.path.join(os.path.dirname(__file__), "US_SOL_CELL5M.csv")

PROFILE_LINES = 12  # fixed number of lines per soil profile


def parse_lat_long(site_line):
    """Extract LAT and LONG from the site data line (3rd line of a profile)."""
    parts = site_line.split()
    # Format: -99  US  LAT  LONG  SCSFamily
    lat = float(parts[2])
    lon = float(parts[3])
    return lat, lon


def parse_profile_id(header_line):
    """Extract soil profile ID from the first line (starts with *)."""
    # e.g. '*US01006921    USA   SandyLoam ...'
    return header_line[1:].split()[0]


def main():
    with open(SOL_FILE, "r") as fh:
        lines = fh.readlines()

    profiles = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("*"):
            block = lines[i: i + PROFILE_LINES]
            if len(block) < PROFILE_LINES:
                break
            profile_id = parse_profile_id(block[0])
            lat, lon = parse_lat_long(block[2])
            cell5m = get_cell_id(lon, lat, 5)
            # Join the 12 lines into a single string (strip trailing newlines/spaces
            # but preserve internal formatting)
            profile_text = "".join(l.rstrip() + "\n" for l in block).rstrip("\n")
            profiles.append((cell5m, profile_id, profile_text))
            i += PROFILE_LINES
        else:
            i += 1

    profiles.sort(key=lambda r: r[0])

    with open(CSV_FILE, "w", newline="") as fh:
        writer = csv.writer(fh, quoting=csv.QUOTE_ALL)
        writer.writerow(["CELL5M", "SoilProfileID", "SoilProfile"])
        writer.writerows(profiles)

    print(f"Written {len(profiles)} profiles to {CSV_FILE}")


if __name__ == "__main__":
    main()
