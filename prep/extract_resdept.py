#!/usr/bin/env python3
"""
Extract SSURGO/STATSGO2 rooting depth (resdept_r, cm) for all MapSPAM USA
crop cells via the USDA Soil Data Access (SDA) API.

Two-step batch approach
-----------------------
Step 1: UNION-ALL spatial query  → cell5m → mukey           (~100 pts/call)
Step 2: component + corestrictions tabular query → mukey → resdept_r

resdept_r = depth to top of the shallowest restrictive layer (cm).
NULL  = no restriction recorded within the surveyed depth (written as empty).

Output: rooting_depth_CELL5M.csv  (CELL5M, resdept_r)
Cache : sda_cache/  — raw JSON per batch, allows safe resume.
"""

import os, csv, json, time, ssl
import urllib.request, urllib.parse

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
MAPSPAM   = os.path.join(BASE_DIR, "mapspam2020_USA_wide.csv")
CACHE_DIR = os.path.join(BASE_DIR, "sda_cache")
OUT_CSV   = os.path.join(BASE_DIR, "rooting_depth_CELL5M.csv")

os.makedirs(CACHE_DIR, exist_ok=True)

SDA_URL    = "https://sdmdataaccess.nrcs.usda.gov/Tabular/post.rest"
BATCH_SIZE = 100    # points per spatial query
RETRY_MAX  = 4
RETRY_DELAY = 25    # seconds between retries
CALL_DELAY  = 1.2   # seconds between successful calls

# SSL context (local CA bundle issue workaround)
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE


# ── SDA helpers ────────────────────────────────────────────────────────────

def sda_query(sql):
    """POST SQL to SDA, return list-of-dicts or None on failure."""
    payload = urllib.parse.urlencode(
        {"query": sql, "format": "JSON+COLUMNNAME"}
    ).encode()
    req = urllib.request.Request(SDA_URL, data=payload, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")

    for attempt in range(1, RETRY_MAX + 1):
        try:
            with urllib.request.urlopen(req, timeout=120, context=SSL_CTX) as r:
                data = json.loads(r.read().decode())
            rows = data.get("Table", [])
            if len(rows) < 1:
                return []
            if len(rows) == 1:          # header only → no data rows
                return []
            hdrs = rows[0]
            return [dict(zip(hdrs, row)) for row in rows[1:]]
        except urllib.error.HTTPError as e:
            msg = e.read().decode()[:200]
            print(f"    HTTP {e.code} (attempt {attempt}/{RETRY_MAX}): {msg}")
        except Exception as e:
            print(f"    Error (attempt {attempt}/{RETRY_MAX}): {e}")
        if attempt < RETRY_MAX:
            time.sleep(RETRY_DELAY)
    return None


# ── Query builders ─────────────────────────────────────────────────────────

def step1_sql(batch):
    """UNION-ALL spatial query: returns rows (cell5m, mukey)."""
    parts = [
        f"SELECT '{cell5m}' AS cell5m, mukey "
        f"FROM SDA_Get_Mukey_from_intersection_with_WktWgs84('POINT({x} {y})')"
        for cell5m, x, y in batch
    ]
    return " UNION ALL ".join(parts)


def step2_sql(mukeys):
    """Component + corestrictions query: returns (mukey, comppct_r, min_resdept_r)."""
    mk_list = ",".join(f"'{m}'" for m in mukeys)
    return f"""
SELECT co.mukey, co.comppct_r,
       MIN(cr.resdept_r) AS min_resdept_r
FROM component co
LEFT JOIN corestrictions cr ON cr.cokey = co.cokey
WHERE co.mukey IN ({mk_list})
  AND co.majcompflag = 'Yes'
GROUP BY co.mukey, co.comppct_r
ORDER BY co.mukey, co.comppct_r DESC
"""


# ── Merge step1 + step2 → {cell5m: resdept_r} ─────────────────────────────

def merge(s1_rows, s2_rows):
    """
    For each cell5m pick the resdept_r of its dominant component
    (highest comppct_r among major components).
    Returns dict {cell5m_str: resdept_r_or_None}.
    """
    # mukey → best (comppct_r, min_resdept_r)
    mukey_best = {}
    for r in s2_rows:
        mk = r["mukey"]
        pct = float(r["comppct_r"] or 0)
        val = r["min_resdept_r"]   # may be None
        if mk not in mukey_best or pct > mukey_best[mk][0]:
            mukey_best[mk] = (pct, val)

    result = {}
    for r in s1_rows:
        cid = r["cell5m"]
        mk  = r["mukey"]
        if mk in mukey_best:
            result[cid] = mukey_best[mk][1]   # resdept_r (None = no restriction)
        # else: mukey had no major component → leave absent (written as "")
    return result


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    # 1. Read all cells
    cells = []
    with open(MAPSPAM) as f:
        for row in csv.DictReader(f):
            cells.append((int(row["CELL5M"]), float(row["x"]), float(row["y"])))
    print(f"MapSPAM cells : {len(cells):,}")

    # 2. Find already-done cell IDs
    done = set()
    if os.path.exists(OUT_CSV):
        with open(OUT_CSV) as f:
            for row in csv.DictReader(f):
                done.add(int(row["CELL5M"]))
    print(f"Already done  : {len(done):,}")

    pending = [c for c in cells if c[0] not in done]
    print(f"Pending       : {len(pending):,}")
    if not pending:
        print("Nothing to do.")
        return

    # 3. Open output (append)
    write_header = len(done) == 0
    out_f  = open(OUT_CSV, "a", newline="")
    writer = csv.writer(out_f)
    if write_header:
        writer.writerow(["CELL5M", "resdept_r"])

    total_batches = (len(pending) + BATCH_SIZE - 1) // BATCH_SIZE
    written = 0

    for bi, start in enumerate(range(0, len(pending), BATCH_SIZE), 1):
        batch = pending[start: start + BATCH_SIZE]
        cache_s1 = os.path.join(CACHE_DIR, f"s1_{start:07d}.json")
        cache_s2 = os.path.join(CACHE_DIR, f"s2_{start:07d}.json")

        print(f"[{bi}/{total_batches}] cells {start+1}–{start+len(batch)} ...",
              end=" ", flush=True)

        # ── Step 1: spatial → mukey ──────────────────────────────────────
        if os.path.exists(cache_s1):
            with open(cache_s1) as f:
                s1_rows = json.load(f)
        else:
            s1_rows = sda_query(step1_sql(batch))
            if s1_rows is None:
                print("Step-1 FAILED — writing blanks")
                for cell5m, _, _ in batch:
                    writer.writerow([cell5m, ""])
                    written += 1
                continue
            with open(cache_s1, "w") as f:
                json.dump(s1_rows, f)
            time.sleep(CALL_DELAY)

        if not s1_rows:
            # No SSURGO coverage for any point in this batch
            for cell5m, _, _ in batch:
                writer.writerow([cell5m, ""])
                written += 1
            print(f"no coverage  [{written} total]")
            continue

        # ── Step 2: mukey → resdept_r ────────────────────────────────────
        mukeys = list({r["mukey"] for r in s1_rows})

        if os.path.exists(cache_s2):
            with open(cache_s2) as f:
                s2_rows = json.load(f)
        else:
            s2_rows = sda_query(step2_sql(mukeys))
            if s2_rows is None:
                print("Step-2 FAILED — writing blanks")
                for cell5m, _, _ in batch:
                    writer.writerow([cell5m, ""])
                    written += 1
                continue
            with open(cache_s2, "w") as f:
                json.dump(s2_rows, f)
            time.sleep(CALL_DELAY)

        # ── Merge and write ──────────────────────────────────────────────
        cell_result = merge(s1_rows, s2_rows)
        for cell5m, _, _ in batch:
            val = cell_result.get(str(cell5m), None)
            writer.writerow([cell5m, val if val is not None else ""])
            written += 1

        n_with_data = sum(1 for v in cell_result.values() if v is not None)
        print(f"{n_with_data}/{len(batch)} have restriction  [total: {written:,}]")

    out_f.close()
    print(f"\nDone. {written:,} rows written to {OUT_CSV}")


if __name__ == "__main__":
    main()
