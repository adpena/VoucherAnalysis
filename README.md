# Texas TEFA School Finder Data

This project scrapes the Texas Comptroller TEFA School Finder and consolidates
the data into a formatted Excel workbook for analysis of voucher (ESA) schools
across Texas. The output includes normalized tables plus an enriched vendor
sheet with TEA boundary-based ESC region, county, and school district fields.

## Data Sources

- TEFA Finder (Texas Comptroller): https://finder.educationfreedom.texas.gov/
- Primary data feed: https://finder.educationfreedom.texas.gov/data/tx/vendors.json
- Config metadata: https://finder.educationfreedom.texas.gov/data/tx/config.js
- TEA boundaries (ESC regions, counties, school districts):
  https://schoolsdata2-tea-texas.opendata.arcgis.com/

## Outputs

- `output/tx_efa_finder/tx_efa_finder.xlsx` consolidated workbook
- `output/tx_efa_finder/tx_vendors_enriched.csv` vendor table with TEA boundary fields
- `docs/tx_efa_finder.xlsx` published copy for GitHub Pages download
- Other CSVs in `output/tx_efa_finder/` are the raw normalized exports

## Quickstart

1. Scrape the latest TEFA Finder data:
   ```
   python3 scripts/scrape_tx_efa_finder.py
   ```

2. Create a virtual environment and install dependencies:
   ```
   python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   ```

3. Build the formatted Excel workbook (and publish to `docs/`):
   ```
   .venv/bin/python scripts/build_tx_efa_workbook.py
   ```

   To refresh cached TEA boundary data:
   ```
   .venv/bin/python scripts/build_tx_efa_workbook.py --refresh-boundaries
   ```

## Workbook Structure

The workbook contains multiple sheets:

- Overview (metadata + generation details)
- Vendors (with ESC region columns)
- Normalized list tables (vendor types, specialties, features, etc.)
- Config, Regions, and Field Inventory

Each sheet is styled as an Excel table with frozen headers and auto-fit
columns for easy filtering and analysis.

## Notes

- The TEFA Finder feed is the authoritative source used by the map UI.
- Boundary data is fetched from the TEA open data portal and cached in
  `data/tea/*.geojson` for repeatable joins.

## Optional AskTED Mapping

If you need a county -> ESC mapping from AskTED exports, the helper script is:

```
python3 scripts/build_county_esc_mapping.py \
  --input /path/to/askted_district_and_site_directory.csv
```

## GitHub Pages

The static site in `docs/` provides a download link for the latest workbook.
Publish by enabling GitHub Pages on the repository and selecting the `/docs`
folder as the source.
