# DSSAT Maize & Soybean Grid Input Table — Column Documentation

**File:** `maiz_soyb_25ha_long_soil_depth_plant_nass_nfert_irr_dens_nrec.csv`  
**Scope:** Continental USA, 5 arc-minute grid cells with ≥ 25 ha harvested area for maize and/or soybean  
**Rows:** 47,707 (crop × cell combinations)  
**Crops:** MZ (maize), SB (soybean); some cells carry both (comma-separated values)

---

## Pipeline Overview

The table was assembled in sequential stages, each adding one or more columns:

| Stage | Script | Columns Added |
|---|---|---|
| 1 | `process_mapspam.py` | CELL5M, X, Y, crop areas |
| 2 | `unit-information/parse_sol_to_csv.py` | SoilProfileID, SoilProfile |
| 3 | `extract_resdept.py` | SoilRootingDepth |
| 4 | `crop-calendar/parse_plant_dates.py` → `nass_maize_planting.py` → `smooth_maize_planting.py` | PlantingDates |
| 5 | `nass_nfert.py` | NFertRateAct |
| 6 | `mapspam_irrigation.py` | WaterSupply |
| 7 | `nass_planting_density.py` | PlantingDensity |
| 8 | `nfert_recommended.py` | NFertRateRec |

---

## Column Descriptions

### UnitID
| | |
|---|---|
| **Type** | Integer |
| **Unit** | — |
| **Source** | Assigned sequentially during long-format restructuring |

Row index assigned during the pivot from wide to long format. No external data source. Unique within the table.

---

### CELL5M
| | |
|---|---|
| **Type** | Integer |
| **Unit** | — |
| **Source** | MapSPAM 2020 (`grid_code`) |

Flat raster cell identifier for the global 5 arc-minute grid (4,320 columns × 2,160 rows). Computed as `row × 4320 + column`, where row 0 starts at 90°N and column 0 starts at 180°W. Serves as the primary spatial join key across all data sources.

---

### X
| | |
|---|---|
| **Type** | Float |
| **Unit** | Decimal degrees (°E, WGS84) |
| **Source** | MapSPAM 2020 |

Longitude of the grid cell centre. Derived from CELL5M as `−180 + (col + 0.5) × (5/60)`.

---

### Y
| | |
|---|---|
| **Type** | Float |
| **Unit** | Decimal degrees (°N, WGS84) |
| **Source** | MapSPAM 2020 |

Latitude of the grid cell centre. Derived from CELL5M as `90 − (row + 0.5) × (5/60)`.

---

### SoilProfileID
| | |
|---|---|
| **Type** | String |
| **Unit** | — |
| **Source** | `US.SOL` (ISRIC SoilGrids v2 + HC27) |

DSSAT soil profile identifier, formatted as `US` + CELL5M (e.g., `US02126127`). Uniquely links each grid cell to its DSSAT-formatted soil profile stored in the `SoilProfile` column and in the `US.SOL` file.

---

### SoilProfile
| | |
|---|---|
| **Type** | Multi-line string |
| **Unit** | — (DSSAT `.SOL` format) |
| **Source** | ISRIC SoilGrids v2 + HC27 pedo-transfer functions |

Full DSSAT-format soil profile text, containing site metadata and horizon-by-horizon physical and hydraulic properties (bulk density, field capacity, wilting point, saturated hydraulic conductivity, organic carbon, clay/silt/sand fractions). 

**Soil property source:** ISRIC SoilGrids v2 (250 m resolution, aggregated to 5 arc-minute).  
**Hydraulic parameter derivation:** HC27 pedo-transfer lookup — maps USDA soil texture class to DSSAT `SLDR`, `SLRO`, `SLLL`, `SDUL`, `SSAT`, and `SRGF` parameters.  
**Parsing:** `unit-information/parse_sol_to_csv.py` extracted profiles from `US.SOL` and matched them to CELL5M via cell centroid coordinates.

---

### SoilRootingDepth
| | |
|---|---|
| **Type** | Integer |
| **Unit** | cm |
| **Source** | USDA SSURGO / STATSGO2 via Soil Data Access (SDA) API |

Depth to the shallowest restrictive soil layer (`resdept_r` in SSURGO component-restriction table). Constrains the maximum rooting depth used in DSSAT simulations.

**Processing (`extract_resdept.py`):**
1. For each grid cell, a spatial point query was submitted to the USDA SDA REST API (`SDA_Get_Mukey_from_intersection_with_WktWgs84`) using the cell centroid coordinates to retrieve the SSURGO map unit key (mukey).
2. A second query retrieved `resdept_r` for the dominant major component (highest `comppct_r`) within each mukey.
3. Batched in groups of 100 points with local JSON caching to allow safe resume.
4. `NULL` values (no restriction recorded within surveyed depth) were filled with **200 cm** (`rooting_depth_CELL5M_filled.csv`).

---

### Crops
| | |
|---|---|
| **Type** | String |
| **Unit** | — |
| **Values** | `MZ`, `SB`, `MZ,SB` |
| **Source** | MapSPAM 2020 physical harvested area |

Crop code(s) present in the grid cell above the inclusion threshold. Cells with both maize and soybean above threshold carry comma-separated codes; corresponding columns (PlantingDates, NFertRateAct, etc.) also carry comma-separated pairs in the same order.

**Derivation:** Grid cells were retained where MapSPAM 2020 physical harvested area (`MAIZ_H_TA` or `SOYB_H_TA`, all technologies combined) was ≥ 25 ha.

---

### PlantingDates
| | |
|---|---|
| **Type** | Integer (or comma-separated pair) |
| **Unit** | Day of year (DOY, 1–365) |
| **Source — MZ** | USDA NASS QuickStats API + GAEZ fallback |
| **Source — SB** | GAEZ crop calendar |

Day of year on which the crop is planted (emergence date for DSSAT).

**Maize (`nass_maize_planting.py` → `smooth_maize_planting.py`):**
- Weekly corn planting progress data (`CORN, PROGRESS, PCT PLANTED, WEEKLY, STATE`) were fetched from the USDA NASS QuickStats API for 2010–2023.
- For each state × year, the DOY when cumulative % planted crossed 50% was determined by linear interpolation, then averaged across years to produce a state median DOY.
- USDA Ag Handbook 628 tabular values were used as fallback for states with no API coverage.
- CELL5M → state mapping was constructed from MapSPAM 2020 `ADM1_NAME`.
- A NaN-safe 2D Gaussian spatial smoothing filter (σ = 4 grid cells ≈ 33 km) was applied to remove zone-boundary artifacts in the underlying GAEZ raster visible at 40°N latitude.

**Soybean:**
- Planting DOY extracted directly from the GAEZ crop calendar raster (`Soybeans.crop.calendar.fill/plant.asc`) at each CELL5M centroid.

---

### Areas
| | |
|---|---|
| **Type** | Float (or comma-separated pair) |
| **Unit** | Hectares (ha) |
| **Source** | MapSPAM 2020 |

Physical harvested area for the crop within the 5 arc-minute grid cell, from MapSPAM 2020 `MAIZ_H_TA` or `SOYB_H_TA` (all technologies combined, no double-counting across seasons). Used to weight results when aggregating from grid to regional scale.

---

### NFertRateAct
| | |
|---|---|
| **Type** | Float (or comma-separated pair) |
| **Unit** | kg N / ha |
| **Source** | USDA NASS Chemical Use Survey via QuickStats API |

**Actual** nitrogen fertilizer application rate — what farmers applied on average in the field.

**Processing (`nass_nfert.py`):**
- Queried USDA NASS QuickStats API for `APPLICATIONS, LB / ACRE / YEAR, AVG` with `DOMAIN: FERTILIZER: (NITROGEN)` at STATE level for 2015–2023.
- Averages computed across available survey years per state (NASS runs Chemical Use surveys periodically, not annually).
- Converted from lb N/acre to kg N/ha using factor **× 1.12085**.
- CELL5M → state mapping from MapSPAM 2020 `ADM1_NAME`.
- States not returned by the API were filled from a built-in fallback table based on published NASS survey reports.
- **Soybean:** 5–82 kg N/ha across states, reflecting actual synthetic N applied (pre-plant or starter); higher values in the Mid-South (Louisiana 82, Arkansas 47 kg N/ha).

---

### NFertRateRec
| | |
|---|---|
| **Type** | Float (or comma-separated pair) |
| **Unit** | kg N / ha |
| **Source** | MRTN (7 states) + state university extension guides |

**Recommended** nitrogen fertilizer rate — the agronomically and economically optimal rate based on field trial data.

**Processing (`nfert_recommended.py`):**

*Maize:*
- **7 MRTN states** (IA, IL, IN, MI, MN, OH, WI): Maximum Return to N (MRTN) values from the Corn Nitrogen Rate Calculator (Sawyer et al. 2006, updated 2020–2023), corn-after-soybean scenario, mid price ratio (~$5/bu corn, ~$0.50/lb N). Range: 140–155 lb N/acre (157–174 kg N/ha).
- **All other states:** State land-grant university extension N rate recommendations (Auburn, UGA, UNL, KSU, TAMU, NCSU, UC Davis, etc.).
- For states with significant irrigated acreage (NE, KS, CO, TX, AZ, CA, ID, WA, OR, NM, UT, WY), **irrigation-specific** recommended rates were applied using the `WaterSupply` column (irrigated fields typically receive 10–30 lb N/acre more than rainfed).

*Soybean:*
- **0 kg N/ha** (all states). Soybeans meet their nitrogen demand through biological nitrogen fixation (BNF) with *Bradyrhizobium* under normal conditions with adequate nodulation. Synthetic N is not agronomically recommended.

**N surplus (NFertRateAct − NFertRateRec):** Notable over-application observed in Georgia (+82 kg N/ha), Kansas (+40), and Missouri (+35).

---

### WaterSupply
| | |
|---|---|
| **Type** | String (or comma-separated pair) |
| **Unit** | — |
| **Values** | `I` (irrigated), `R` (rainfed) |
| **Source** | MapSPAM 2020 |

Dominant water management system for the crop in the grid cell.

**Processing (`mapspam_irrigation.py`):**  
Derived from the ratio of irrigated to total MapSPAM 2020 harvested area:

- **Maize:** `MAIZ_A_TI` (irrigated) vs. `MAIZ_A_TR` (rainfed)
- **Soybean:** `SOYB_A_TI` vs. `SOYB_A_TR`

Assignment rule: `I` if `TI / (TI + TR) > 0.5`; `R` otherwise (including cells where both are zero).

**Summary:** 31.3% of maize grid cells are classified as irrigated (concentrated in Nebraska, Kansas, Colorado, California, Idaho); 12.7% of soybean cells are irrigated.

---

### PlantingDensity
| | |
|---|---|
| **Type** | Float (or comma-separated pair) |
| **Unit** | plants / m² |
| **Source — MZ** | USDA NASS Objective Yield Survey + extension guides |
| **Source — SB** | University extension seeding-rate publications |

Number of plants per m² at emergence (DSSAT `PPOP` parameter).

**Maize (`nass_planting_density.py`):**
- USDA NASS Objective Yield Survey (`CORN, GRAIN, PLANT POPULATION, PLANTS / ACRE, YEAR, STATE`) fetched via QuickStats API for 2015–2023, averaged across years.
- API returned data for **10 states**: IL, IN, IA, KS, MN, MO, NE, OH, SD, WI.
- **Nebraska** uniquely provides irrigated / non-irrigated breakdowns: 6.98 plants/m² (irrigated) vs. 5.82 plants/m² (non-irrigated).
- Remaining 32 states filled from a fallback table of state-specific extension recommendations, with differentiated irrigated and rainfed values for key states.
- **Kansas override:** NASS statewide average (5.54 plants/m²) was manually overridden to **7.5 plants/m² for irrigated cells**, because the combined average is pulled down by the large dryland acreage in western Kansas. The rainfed value retains the NASS-derived 5.54 plants/m².
- Converted from plants/acre using factor **÷ 4046.86**.

**Soybean:**
- No NASS plant population survey available for soybeans.
- Regional values from university extension seeding-rate guides: 35 plants/m² in the northern and central corn belt (IA, IL, IN, OH, MN, WI); 32–33 plants/m² in the Mid-South and Southeast; 30 plants/m² in the Great Plains and West.
- Same density applied regardless of irrigation status (soybeans adjust yield through branching and pod-set compensation).

**Typical ranges:** MZ irrigated 5.54–9.0 plants/m² (mean 7.50); MZ rainfed 5.50–7.72 plants/m² (mean 6.13); SB 30–35 plants/m² (mean 32.8).

---

## Notes on Comma-Separated Values

For cells where `Crops = "MZ,SB"`, all data columns carry comma-separated pairs with MZ as the first element and SB as the second. This applies to: `PlantingDates`, `Areas`, `NFertRateAct`, `NFertRateRec`, `WaterSupply`, and `PlantingDensity`. The `SoilProfile` and `SoilRootingDepth` columns are soil properties shared by both crops at the same location and are therefore single values.

## Key Data Sources

| Source | Description | Access |
|---|---|---|
| MapSPAM 2020 | Spatial crop area and technology allocation | mapspam.info |
| USDA NASS QuickStats | Chemical use, planting progress, plant population surveys | quickstats.nass.usda.gov/api |
| USDA SDA (Soil Data Access) | SSURGO/STATSGO2 soil restrictive layer depth | sdmdataaccess.nrcs.usda.gov |
| ISRIC SoilGrids v2 | Global 250 m soil physical/chemical properties | soilgrids.org |
| HC27 | DSSAT soil hydraulic parameter pedo-transfer lookup | DSSAT documentation |
| GAEZ crop calendar | Global crop planting date rasters | FAO/IIASA |
| MRTN calculator | Maximum Return to N for corn (7 Midwest states) | extension.agron.iastate.edu |
