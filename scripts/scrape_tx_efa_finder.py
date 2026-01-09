#!/usr/bin/env python3
import csv
import json
import os
import subprocess
import tempfile
import urllib.request
from datetime import datetime, timezone


BASE_URL = "https://finder.educationfreedom.texas.gov/"
VENDORS_URL = f"{BASE_URL}data/tx/vendors.json"
FILTER_OPTIONS_URL = f"{BASE_URL}data/tx/filter-options.json"
CONFIG_URL = f"{BASE_URL}data/tx/config.js"

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "output", "tx_efa_finder")


def fetch_json(url):
    with urllib.request.urlopen(url) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_text(url):
    with urllib.request.urlopen(url) as response:
        return response.read().decode("utf-8", errors="replace")


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def join_list(values):
    if not values:
        return ""
    return "; ".join(str(value) for value in values)


def write_csv(path, fieldnames, rows):
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def update_field_meta(field_meta, path, value):
    entry = field_meta.setdefault(
        path,
        {"types": set(), "non_null_count": 0, "list_item_count": 0},
    )
    value_type = type(value).__name__
    entry["types"].add(value_type)
    if value is not None:
        entry["non_null_count"] += 1
    if isinstance(value, list):
        entry["list_item_count"] += len(value)


def collect_field_meta(field_meta, path, value):
    update_field_meta(field_meta, path, value)
    if isinstance(value, dict):
        for key, child in value.items():
            collect_field_meta(field_meta, f"{path}.{key}", child)


def parse_config_js(config_raw):
    cleaned = config_raw.replace("export default APP_CONFIG;", "")
    cleaned = f"{cleaned}\nconsole.log(JSON.stringify(APP_CONFIG));\n"

    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as handle:
        handle.write(cleaned)
        temp_path = handle.name

    try:
        result = subprocess.run(
            ["node", temp_path],
            check=True,
            capture_output=True,
            text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    finally:
        os.unlink(temp_path)

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return None


def flatten_config(value, path, rows):
    if isinstance(value, dict):
        for key, child in value.items():
            flatten_config(child, f"{path}.{key}" if path else key, rows)
        return
    if isinstance(value, list):
        rows.append(
            {"key_path": path, "value": json.dumps(value, ensure_ascii=False)}
        )
        return
    rows.append({"key_path": path, "value": value})


def main():
    ensure_dir(OUTPUT_DIR)

    vendors = fetch_json(VENDORS_URL)
    filter_options = fetch_json(FILTER_OPTIONS_URL)
    config_raw = fetch_text(CONFIG_URL)
    config = parse_config_js(config_raw)

    vendor_rows = []
    vendor_type_rows = []
    service_type_rows = []
    subject_rows = []
    bonus_tag_rows = []
    specialty_rows = []
    financial_access_rows = []
    feature_rows = []
    academic_achievement_rows = []
    field_meta = {}

    for vendor in vendors:
        collect_field_meta(field_meta, "vendor", vendor)
        address = vendor.get("address") or {}
        location = vendor.get("location") or {}
        contact = vendor.get("contact") or {}
        school_attributes = vendor.get("schoolAttributes") or {}
        financial = school_attributes.get("financial") or {}
        features = school_attributes.get("features") or {}
        academics = school_attributes.get("academics") or {}

        vendor_rows.append(
            {
                "id": vendor.get("id"),
                "name": vendor.get("name"),
                "vendorType": vendor.get("vendorType"),
                "vendorTypes": join_list(vendor.get("vendorTypes")),
                "type": vendor.get("type"),
                "serviceType": join_list(vendor.get("serviceType")),
                "description": vendor.get("description"),
                "directPayMarketplace": vendor.get("directPayMarketplace"),
                "additionalLocations": json.dumps(vendor.get("additionalLocations"), ensure_ascii=False)
                if vendor.get("additionalLocations") is not None
                else "",
                "subjectsTaught": join_list(vendor.get("subjectsTaught")),
                "pricingModel": vendor.get("pricingModel"),
                "price": vendor.get("price"),
                "pricingNotes": vendor.get("pricingNotes"),
                "isProductionReady": vendor.get("isProductionReady"),
                "curricularClassification": vendor.get("curricularClassification"),
                "bonusTagsRaw": join_list(vendor.get("bonusTagsRaw")),
                "minGrade": vendor.get("minGrade"),
                "maxGrade": vendor.get("maxGrade"),
                "isPreK": vendor.get("isPreK"),
                "isElementary": vendor.get("isElementary"),
                "isMiddle": vendor.get("isMiddle"),
                "isHigh": vendor.get("isHigh"),
                "displayGradeRange": vendor.get("displayGradeRange"),
                "costOptions": vendor.get("costOptions"),
                "address_street": address.get("street"),
                "address_city": address.get("city"),
                "address_state": address.get("state"),
                "address_zipcode": address.get("zipcode"),
                "address_county": address.get("county"),
                "address_region": address.get("region"),
                "location_lat": location.get("lat"),
                "location_lng": location.get("lng"),
                "contact_website": contact.get("website"),
                "contact_phone": contact.get("phone"),
                "contact_email": contact.get("email"),
                "financial_minAnnualTuition": financial.get("minAnnualTuition"),
                "financial_maxAnnualTuition": financial.get("maxAnnualTuition"),
                "academics_studentGrowth": academics.get("studentGrowth"),
                "academics_attendanceRate": academics.get("attendanceRate"),
                "academics_graduationRate": academics.get("graduationRate"),
                "academics_studentTeacherRatio": academics.get("studentTeacherRatio"),
                "academics_retentionRate": academics.get("retentionRate"),
            }
        )

        for vendor_type in vendor.get("vendorTypes") or []:
            vendor_type_rows.append(
                {"vendor_id": vendor.get("id"), "vendor_type": vendor_type}
            )

        for service_type in vendor.get("serviceType") or []:
            service_type_rows.append(
                {"vendor_id": vendor.get("id"), "service_type": service_type}
            )

        for subject in vendor.get("subjectsTaught") or []:
            subject_rows.append({"vendor_id": vendor.get("id"), "subject": subject})

        for bonus_tag in vendor.get("bonusTagsRaw") or []:
            bonus_tag_rows.append(
                {"vendor_id": vendor.get("id"), "bonus_tag": bonus_tag}
            )

        specialties = vendor.get("specialties") or {}
        for category, values in specialties.items():
            for value in values or []:
                specialty_rows.append(
                    {
                        "vendor_id": vendor.get("id"),
                        "specialty_category": category,
                        "specialty_value": value,
                    }
                )

        for value in financial.get("financialAccessibility") or []:
            financial_access_rows.append(
                {
                    "vendor_id": vendor.get("id"),
                    "financial_accessibility": value,
                }
            )

        for category, values in features.items():
            for value in values or []:
                feature_rows.append(
                    {
                        "vendor_id": vendor.get("id"),
                        "feature_category": category,
                        "feature_value": value,
                    }
                )

        for value in academics.get("notableAchievements") or []:
            academic_achievement_rows.append(
                {
                    "vendor_id": vendor.get("id"),
                    "notable_achievement": value,
                }
            )

    write_csv(
        os.path.join(OUTPUT_DIR, "tx_vendors.csv"),
        [
            "id",
            "name",
            "vendorType",
            "vendorTypes",
            "type",
            "serviceType",
            "description",
            "directPayMarketplace",
            "additionalLocations",
            "subjectsTaught",
            "pricingModel",
            "price",
            "pricingNotes",
            "isProductionReady",
            "curricularClassification",
            "bonusTagsRaw",
            "minGrade",
            "maxGrade",
            "isPreK",
            "isElementary",
            "isMiddle",
            "isHigh",
            "displayGradeRange",
            "costOptions",
            "address_street",
            "address_city",
            "address_state",
            "address_zipcode",
            "address_county",
            "address_region",
            "location_lat",
            "location_lng",
            "contact_website",
            "contact_phone",
            "contact_email",
            "financial_minAnnualTuition",
            "financial_maxAnnualTuition",
            "academics_studentGrowth",
            "academics_attendanceRate",
            "academics_graduationRate",
            "academics_studentTeacherRatio",
            "academics_retentionRate",
        ],
        vendor_rows,
    )

    write_csv(
        os.path.join(OUTPUT_DIR, "tx_vendor_types.csv"),
        ["vendor_id", "vendor_type"],
        vendor_type_rows,
    )
    write_csv(
        os.path.join(OUTPUT_DIR, "tx_service_types.csv"),
        ["vendor_id", "service_type"],
        service_type_rows,
    )
    write_csv(
        os.path.join(OUTPUT_DIR, "tx_subjects_taught.csv"),
        ["vendor_id", "subject"],
        subject_rows,
    )
    write_csv(
        os.path.join(OUTPUT_DIR, "tx_bonus_tags.csv"),
        ["vendor_id", "bonus_tag"],
        bonus_tag_rows,
    )
    write_csv(
        os.path.join(OUTPUT_DIR, "tx_specialties.csv"),
        ["vendor_id", "specialty_category", "specialty_value"],
        specialty_rows,
    )
    write_csv(
        os.path.join(OUTPUT_DIR, "tx_financial_accessibility.csv"),
        ["vendor_id", "financial_accessibility"],
        financial_access_rows,
    )
    write_csv(
        os.path.join(OUTPUT_DIR, "tx_features.csv"),
        ["vendor_id", "feature_category", "feature_value"],
        feature_rows,
    )
    write_csv(
        os.path.join(OUTPUT_DIR, "tx_academic_notable_achievements.csv"),
        ["vendor_id", "notable_achievement"],
        academic_achievement_rows,
    )

    if config:
        config_rows = []
        flatten_config(config, "", config_rows)
        write_csv(
            os.path.join(OUTPUT_DIR, "tx_config.csv"),
            ["key_path", "value"],
            config_rows,
        )

        regions = config.get("regions") or []
        region_rows = []
        for region in regions:
            center = region.get("center") or {}
            region_rows.append(
                {
                    "id": region.get("id"),
                    "name": region.get("name"),
                    "cities": join_list(region.get("cities")),
                    "center_lat": center.get("lat"),
                    "center_lng": center.get("lng"),
                    "zoom": region.get("zoom"),
                }
            )
        write_csv(
            os.path.join(OUTPUT_DIR, "tx_regions.csv"),
            ["id", "name", "cities", "center_lat", "center_lng", "zoom"],
            region_rows,
        )

    field_inventory_rows = []
    for path, meta in sorted(field_meta.items()):
        field_inventory_rows.append(
            {
                "field_path": path,
                "value_types": ",".join(sorted(meta["types"])),
                "non_null_count": meta["non_null_count"],
                "list_item_count": meta["list_item_count"],
            }
        )
    write_csv(
        os.path.join(OUTPUT_DIR, "tx_field_inventory.csv"),
        ["field_path", "value_types", "non_null_count", "list_item_count"],
        field_inventory_rows,
    )

    counties = {v.get("address", {}).get("county") for v in vendors if v.get("address")}
    regions = {v.get("address", {}).get("region") for v in vendors if v.get("address")}
    cities = {v.get("address", {}).get("city") for v in vendors if v.get("address")}

    metadata_rows = [
        {"key": "vendors_source_url", "value": VENDORS_URL},
        {"key": "filter_options_url", "value": FILTER_OPTIONS_URL},
        {"key": "config_url", "value": CONFIG_URL},
        {"key": "retrieved_at_utc", "value": datetime.now(timezone.utc).isoformat()},
        {"key": "record_count", "value": len(vendors)},
        {"key": "unique_counties", "value": len([c for c in counties if c])},
        {"key": "unique_regions", "value": len([r for r in regions if r])},
        {"key": "unique_cities", "value": len([c for c in cities if c])},
        {"key": "filter_options_json", "value": json.dumps(filter_options, ensure_ascii=False)},
        {"key": "config_raw_length_chars", "value": len(config_raw)},
        {"key": "config_parsed", "value": bool(config)},
    ]
    write_csv(
        os.path.join(OUTPUT_DIR, "tx_dataset_metadata.csv"),
        ["key", "value"],
        metadata_rows,
    )


if __name__ == "__main__":
    main()
