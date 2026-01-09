#!/usr/bin/env python3
import argparse
import csv
import json
import os
import shutil
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from lib.excel import format_worksheet_as_table
from lib.geo import GeoFeatureIndex


DEFAULT_INPUT_DIR = os.path.join("output", "tx_efa_finder")
DEFAULT_BOUNDARY_DIR = os.path.join("data", "tea")
DEFAULT_OUTPUT_PATH = os.path.join("output", "tx_efa_finder", "tx_efa_finder.xlsx")

BOUNDARY_ITEMS = {
    "esc_regions": "d273301a15b343a99d4c8211b7c112e0",
    "counties": "c71146b6426248a5a484d8b3c192b9fe",
    "school_districts": "edbb3c145304494382da3aa30c154b5e",
}

PORTAL_BASE = "https://tea-texas.maps.arcgis.com"


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        return reader.fieldnames or [], rows


def write_csv(path, fieldnames, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def fetch_item_service_url(item_id):
    url = f"{PORTAL_BASE}/sharing/rest/content/items/{item_id}?f=json"
    with urllib.request.urlopen(url) as response:
        payload = json.loads(response.read().decode("utf-8"))
    service_url = payload.get("url")
    if not service_url:
        raise ValueError(f"No service URL found for item {item_id}")
    return service_url


def fetch_layer_metadata(layer_url):
    with urllib.request.urlopen(f"{layer_url}?f=json") as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_object_ids(layer_url):
    params = {"where": "1=1", "returnIdsOnly": "true", "f": "json"}
    query = urllib.parse.urlencode(params)
    url = f"{layer_url}/query?{query}"
    with urllib.request.urlopen(url, timeout=60) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload.get("objectIds") or []


def fetch_geojson(layer_url):
    metadata = fetch_layer_metadata(layer_url)
    object_id_field = metadata.get("objectIdField", "OBJECTID")
    max_record_count = metadata.get("maxRecordCount", 2000)
    batch_size = min(max_record_count, 100)

    object_ids = fetch_object_ids(layer_url)
    features = []

    if object_ids:
        object_ids = sorted(object_ids)
        for i in range(0, len(object_ids), batch_size):
            chunk = object_ids[i : i + batch_size]
            params = {
                "objectIds": ",".join(str(item) for item in chunk),
                "outFields": "*",
                "returnGeometry": "true",
                "outSR": 4326,
                "f": "geojson",
            }
            query = urllib.parse.urlencode(params)
            url = f"{layer_url}/query?{query}"
            with urllib.request.urlopen(url, timeout=60) as response:
                payload = json.loads(response.read().decode("utf-8"))
            features.extend(payload.get("features", []))
    else:
        offset = 0
        while True:
            params = {
                "where": "1=1",
                "outFields": "*",
                "returnGeometry": "true",
                "outSR": 4326,
                "f": "geojson",
                "resultOffset": offset,
                "resultRecordCount": batch_size,
                "orderByFields": object_id_field,
            }
            query = urllib.parse.urlencode(params)
            url = f"{layer_url}/query?{query}"
            with urllib.request.urlopen(url, timeout=60) as response:
                payload = json.loads(response.read().decode("utf-8"))
            batch = payload.get("features", [])
            if not batch:
                break
            features.extend(batch)
            offset += len(batch)
            if not payload.get("exceededTransferLimit"):
                break

    return {"type": "FeatureCollection", "features": features}


def load_or_fetch_boundary(boundary_dir, name, refresh=False):
    os.makedirs(boundary_dir, exist_ok=True)
    path = os.path.join(boundary_dir, f"{name}.geojson")
    if os.path.exists(path) and not refresh:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)

    item_id = BOUNDARY_ITEMS[name]
    service_url = fetch_item_service_url(item_id)
    layer_url = f"{service_url}/0"
    geojson = fetch_geojson(layer_url)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(geojson, handle)
    return geojson


def enrich_vendors(vendor_rows, esc_index, county_index, district_index):
    enriched_rows = []
    missing = {"esc": 0, "county": 0, "district": 0}
    for row in vendor_rows:
        enriched = dict(row)
        lat = row.get("location_lat")
        lng = row.get("location_lng")

        esc_props = None
        county_props = None
        district_props = None
        if lat and lng:
            try:
                point = (float(lng), float(lat))
            except ValueError:
                point = None
            if point:
                esc_props = esc_index.lookup(point)
                county_props = county_index.lookup(point)
                district_props = district_index.lookup(point)

        if not esc_props:
            missing["esc"] += 1
            esc_props = {}
        if not county_props:
            missing["county"] += 1
            county_props = {}
        if not district_props:
            missing["district"] += 1
            district_props = {}

        enriched["tea_esc_region"] = esc_props.get("ESC_REGION", "")
        enriched["tea_esc_city"] = esc_props.get("CITY", "")
        enriched["tea_esc_website"] = esc_props.get("WEBSITE", "")
        county_name = county_props.get("FENAME", "") or county_props.get("NAME", "")
        enriched["tea_county_name"] = county_name.title() if county_name else ""
        enriched["tea_county_fips"] = county_props.get("FIPS", "")
        enriched["tea_county_cntyfips"] = county_props.get("CNTYFIPS", "")
        enriched["tea_school_district_name"] = district_props.get("NAME", "")
        enriched["tea_school_district_name20"] = district_props.get("NAME20", "")
        enriched["tea_school_district_number"] = district_props.get("DISTRICT_C", "")
        enriched["tea_school_district_nces"] = district_props.get("NCES_DISTR", "")
        enriched["tea_school_district_geoid20"] = district_props.get("GEOID20", "")
        enriched_rows.append(enriched)

    return enriched_rows, missing


def add_sheet_from_rows(workbook, title, fieldnames, rows):
    worksheet = workbook.create_sheet(title=title)
    worksheet.append(fieldnames)
    for row in rows:
        worksheet.append([row.get(field, "") for field in fieldnames])
    format_worksheet_as_table(worksheet, table_name=f"{title}_table")


def add_overview_sheet(workbook, metadata_rows, summary_rows):
    worksheet = workbook.active
    worksheet.title = "Overview"
    worksheet.append(["Key", "Value"])
    for row in metadata_rows + summary_rows:
        worksheet.append([row["key"], row["value"]])

    title_cell = worksheet["A1"]
    title_cell.font = Font(bold=True)
    title_cell.alignment = Alignment(horizontal="center")

    format_worksheet_as_table(worksheet, table_name="Overview_table")


def main():
    parser = argparse.ArgumentParser(
        description="Build a formatted XLSX workbook from TEFA finder CSV exports."
    )
    parser.add_argument(
        "--input-dir",
        default=DEFAULT_INPUT_DIR,
        help="Directory containing the CSV outputs from scrape_tx_efa_finder.py",
    )
    parser.add_argument(
        "--boundary-dir",
        default=DEFAULT_BOUNDARY_DIR,
        help="Directory to cache TEA boundary GeoJSON files",
    )
    parser.add_argument(
        "--refresh-boundaries",
        action="store_true",
        help="Re-download TEA boundary data even if cached",
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT_PATH,
        help="Path to the XLSX workbook to write",
    )
    parser.add_argument(
        "--publish-dir",
        default=os.path.join("docs"),
        help="Optional directory to copy the XLSX workbook for GitHub Pages",
    )
    args = parser.parse_args()

    input_dir = args.input_dir
    esc_geojson = load_or_fetch_boundary(
        args.boundary_dir, "esc_regions", refresh=args.refresh_boundaries
    )
    county_geojson = load_or_fetch_boundary(
        args.boundary_dir, "counties", refresh=args.refresh_boundaries
    )
    district_geojson = load_or_fetch_boundary(
        args.boundary_dir, "school_districts", refresh=args.refresh_boundaries
    )
    esc_index = GeoFeatureIndex(esc_geojson.get("features", []))
    county_index = GeoFeatureIndex(county_geojson.get("features", []))
    district_index = GeoFeatureIndex(district_geojson.get("features", []))

    vendors_fields, vendors_rows = read_csv(os.path.join(input_dir, "tx_vendors.csv"))
    enriched_rows, missing_counts = enrich_vendors(
        vendors_rows, esc_index, county_index, district_index
    )
    enriched_fields = list(vendors_fields) + [
        "tea_esc_region",
        "tea_esc_city",
        "tea_esc_website",
        "tea_county_name",
        "tea_county_fips",
        "tea_county_cntyfips",
        "tea_school_district_name",
        "tea_school_district_name20",
        "tea_school_district_number",
        "tea_school_district_nces",
        "tea_school_district_geoid20",
    ]

    enriched_csv_path = os.path.join(input_dir, "tx_vendors_enriched.csv")
    write_csv(enriched_csv_path, enriched_fields, enriched_rows)

    metadata_fields, metadata_rows = read_csv(
        os.path.join(input_dir, "tx_dataset_metadata.csv")
    )
    metadata_keyed = {row["key"]: row["value"] for row in metadata_rows}
    summary_rows = [
        {"key": "tea_boundary_dir", "value": args.boundary_dir},
        {"key": "tea_esc_missing_count", "value": missing_counts["esc"]},
        {"key": "tea_county_missing_count", "value": missing_counts["county"]},
        {"key": "tea_district_missing_count", "value": missing_counts["district"]},
        {"key": "workbook_generated_at_utc", "value": datetime.now(timezone.utc).isoformat()},
    ]
    overview_rows = [
        {"key": key, "value": metadata_keyed[key]}
        for key in sorted(metadata_keyed.keys())
    ]

    workbook = Workbook()
    add_overview_sheet(workbook, overview_rows, summary_rows)

    add_sheet_from_rows(workbook, "Vendors", enriched_fields, enriched_rows)
    for filename, title in [
        ("tx_vendor_types.csv", "Vendor Types"),
        ("tx_service_types.csv", "Service Types"),
        ("tx_subjects_taught.csv", "Subjects"),
        ("tx_bonus_tags.csv", "Bonus Tags"),
        ("tx_specialties.csv", "Specialties"),
        ("tx_features.csv", "Features"),
        ("tx_financial_accessibility.csv", "Financial Access"),
        ("tx_academic_notable_achievements.csv", "Academic Achievements"),
        ("tx_regions.csv", "Regions"),
        ("tx_config.csv", "Config"),
        ("tx_dataset_metadata.csv", "Dataset Metadata"),
        ("tx_field_inventory.csv", "Field Inventory"),
    ]:
        fields, rows = read_csv(os.path.join(input_dir, filename))
        add_sheet_from_rows(workbook, title, fields, rows)

    workbook.save(args.output)

    if args.publish_dir:
        os.makedirs(args.publish_dir, exist_ok=True)
        published_path = os.path.join(args.publish_dir, os.path.basename(args.output))
        shutil.copyfile(args.output, published_path)


if __name__ == "__main__":
    main()
