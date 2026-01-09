#!/usr/bin/env python3
import argparse
import csv
import os


def normalize_county(name):
    if not name:
        return ""
    cleaned = name.strip().upper()
    if cleaned.endswith(" COUNTY"):
        cleaned = cleaned[: -len(" COUNTY")].strip()
    return cleaned


def strip_leading_apostrophe(value):
    if isinstance(value, str) and value.startswith("'"):
        return value[1:]
    return value


def title_case_county(name):
    if not name:
        return ""
    return name.title()


def build_mapping(input_path):
    aggregates = {}
    with open(input_path, newline="", encoding="utf-8", errors="replace") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            county_name = row.get("County Name", "")
            esc_served = strip_leading_apostrophe(row.get("ESC Region Served", "")).strip()
            esc_peims = strip_leading_apostrophe(row.get("ESC Region PEIMS", "")).strip()
            esc_geo = strip_leading_apostrophe(row.get("ESC Region Geographic", "")).strip()

            key = normalize_county(county_name)
            if not key:
                continue

            entry = aggregates.setdefault(
                key,
                {
                    "esc_region_served": {},
                    "esc_region_peims": {},
                    "esc_region_geographic": {},
                },
            )
            if esc_served:
                entry["esc_region_served"][esc_served] = (
                    entry["esc_region_served"].get(esc_served, 0) + 1
                )
            if esc_peims:
                entry["esc_region_peims"][esc_peims] = (
                    entry["esc_region_peims"].get(esc_peims, 0) + 1
                )
            if esc_geo:
                entry["esc_region_geographic"][esc_geo] = (
                    entry["esc_region_geographic"].get(esc_geo, 0) + 1
                )

    mapping = {}
    conflicts = {}
    for key, counts in aggregates.items():
        def pick_best(counter):
            if not counter:
                return ""
            return max(counter.items(), key=lambda item: (item[1], item[0]))[0]

        esc_served = pick_best(counts["esc_region_served"])
        esc_peims = pick_best(counts["esc_region_peims"])
        esc_geo = pick_best(counts["esc_region_geographic"])

        mapping[key] = {
            "county_key": key,
            "county_name": title_case_county(key),
            "esc_region_served": esc_served,
            "esc_region_peims": esc_peims,
            "esc_region_geographic": esc_geo,
        }

        if len(counts["esc_region_served"]) > 1:
            conflicts[key] = counts["esc_region_served"]

    return mapping, conflicts


def write_mapping(output_path, mapping):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    fieldnames = [
        "county_key",
        "county_name",
        "esc_region_served",
        "esc_region_peims",
        "esc_region_geographic",
    ]
    with open(output_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for key in sorted(mapping.keys()):
            writer.writerow(mapping[key])


def main():
    parser = argparse.ArgumentParser(
        description="Build Texas county to ESC region mapping from AskTED directory export."
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to an AskTED directory CSV export containing ESC region columns.",
    )
    parser.add_argument(
        "--output",
        default=os.path.join("data", "tx_county_esc_mapping.csv"),
        help="Output CSV path for the county -> ESC mapping.",
    )
    args = parser.parse_args()

    mapping, conflicts = build_mapping(args.input)
    if conflicts:
        conflict_list = ", ".join(sorted(conflicts.keys()))
        print(f"Warning: multiple ESC Region Served values found for: {conflict_list}")

    write_mapping(args.output, mapping)


if __name__ == "__main__":
    main()
