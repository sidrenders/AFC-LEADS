#!/usr/bin/env python3
"""
Aftercells Lead Management System - Airtable Setup Script

This script creates your complete Airtable base with all tables, fields,
and configuration. Run it once to set up everything.

SETUP:
1. Go to https://airtable.com/create/tokens and create a personal access token
   - Scopes needed: data.records:read, data.records:write, schema.bases:read, schema.bases:write
   - Access: the workspace where you want the base
2. Create a new empty base in Airtable (just the default one is fine)
3. Get the base ID from the URL: https://airtable.com/BASE_ID_HERE/...
4. Copy .env.example to .env and fill in your token and base ID
5. Run: python setup_airtable.py

REQUIREMENTS:
    pip install pyairtable python-dotenv requests
"""

import os
import sys
import time
import requests
from dotenv import load_dotenv

load_dotenv()

AIRTABLE_TOKEN = os.getenv("AIRTABLE_PERSONAL_ACCESS_TOKEN")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID")

API_URL = "https://api.airtable.com/v0"

if not AIRTABLE_TOKEN or not AIRTABLE_BASE_ID:
    print("ERROR: Missing environment variables.")
    print("Make sure .env has AIRTABLE_PERSONAL_ACCESS_TOKEN and AIRTABLE_BASE_ID")
    print("See .env.example for reference.")
    sys.exit(1)


def headers():
    return {
        "Authorization": f"Bearer {AIRTABLE_TOKEN}",
        "Content-Type": "application/json",
    }


def get_base_schema():
    """Get current base schema to find existing tables."""
    resp = requests.get(f"{API_URL}/meta/bases/{AIRTABLE_BASE_ID}/tables", headers=headers())
    resp.raise_for_status()
    return resp.json()


def create_table(name, fields, description=""):
    """Create a new table in the base."""
    # Airtable API requires at least one field that's not a computed type
    # We need to filter out formula/rollup/lastModifiedTime for initial creation
    # and add them after
    simple_fields = []
    deferred_fields = []

    for field in fields:
        if field["type"] in ("formula", "lastModifiedTime", "multipleRecordLinks"):
            deferred_fields.append(field)
        else:
            api_field = {"name": field["name"], "type": field["type"]}
            if "options" in field and field["type"] not in ("formula", "lastModifiedTime"):
                api_field["options"] = field["options"]
            simple_fields.append(api_field)

    payload = {
        "name": name,
        "fields": simple_fields,
    }
    if description:
        payload["description"] = description

    print(f"\n  Creating table: {name}...")
    resp = requests.post(
        f"{API_URL}/meta/bases/{AIRTABLE_BASE_ID}/tables",
        headers=headers(),
        json=payload,
    )

    if resp.status_code != 200:
        print(f"  ERROR creating table {name}: {resp.status_code}")
        print(f"  {resp.text}")
        return None, deferred_fields

    table_data = resp.json()
    table_id = table_data["id"]
    print(f"  Created table: {name} (ID: {table_id})")

    return table_id, deferred_fields


def add_field_to_table(table_id, field):
    """Add a single field to an existing table."""
    api_field = {"name": field["name"], "type": field["type"]}

    if field["type"] == "formula" and "options" in field:
        api_field["options"] = {"formula": field["options"]["formula"]}
    elif field["type"] == "multipleRecordLinks" and "options" in field:
        api_field["options"] = field["options"]
    elif "options" in field:
        api_field["options"] = field["options"]

    resp = requests.post(
        f"{API_URL}/meta/bases/{AIRTABLE_BASE_ID}/tables/{table_id}/fields",
        headers=headers(),
        json=api_field,
    )

    if resp.status_code != 200:
        print(f"    WARNING: Could not add field '{field['name']}': {resp.text}")
        return None

    print(f"    Added field: {field['name']} ({field['type']})")
    return resp.json()


def setup_base():
    """Main setup function - creates all tables and fields."""
    from schema import ALL_TABLES, CHANNEL_VIEWS

    print("=" * 60)
    print("  AFTERCELLS LEAD MANAGEMENT SYSTEM - AIRTABLE SETUP")
    print("=" * 60)
    print(f"\n  Base ID: {AIRTABLE_BASE_ID}")
    print(f"  Token: {AIRTABLE_TOKEN[:12]}...{AIRTABLE_TOKEN[-4:]}")

    # Check existing schema
    print("\n  Checking existing base schema...")
    schema = get_base_schema()
    existing_tables = {t["name"]: t["id"] for t in schema.get("tables", [])}
    print(f"  Existing tables: {list(existing_tables.keys())}")

    table_ids = {}

    # Create tables
    for table_def in ALL_TABLES:
        table_name = table_def["name"]

        if table_name in existing_tables:
            print(f"\n  Table '{table_name}' already exists - skipping creation")
            table_ids[table_name] = existing_tables[table_name]
            continue

        table_id, deferred = create_table(table_name, table_def["fields"])
        if table_id:
            table_ids[table_name] = table_id

            # Add deferred fields (formulas, links, etc.)
            if deferred:
                print(f"  Adding computed/linked fields to {table_name}...")
                time.sleep(0.5)  # Rate limit buffer

                for field in deferred:
                    # For linked records, resolve the table ID
                    if field["type"] == "multipleRecordLinks":
                        linked_table_name = field["options"]["linkedTableId"]
                        if linked_table_name in table_ids:
                            field["options"]["linkedTableId"] = table_ids[linked_table_name]
                        else:
                            print(f"    SKIP: Linked table '{linked_table_name}' not yet created")
                            continue

                    add_field_to_table(table_id, field)
                    time.sleep(0.3)  # Rate limit

        time.sleep(1)  # Rate limit between tables

    # Summary
    print("\n" + "=" * 60)
    print("  SETUP COMPLETE")
    print("=" * 60)
    print(f"\n  Tables created: {list(table_ids.keys())}")
    print(f"\n  NEXT STEPS:")
    print(f"  1. Open your Airtable base: https://airtable.com/{AIRTABLE_BASE_ID}")
    print(f"  2. Delete the default empty table if one exists")
    print(f"  3. Create the views manually (see VIEWS section in schema.py)")
    print(f"     Airtable API doesn't support view creation - but it's easy:")
    print(f"     - Click '+' next to views in the sidebar")
    print(f"     - Add filter conditions as described in schema.py")
    print(f"  4. Start adding leads!")
    print()

    # Print view instructions
    print("  VIEWS TO CREATE (in Channels table):")
    print("  " + "-" * 50)
    for view in CHANNEL_VIEWS:
        print(f"  View: '{view['name']}'")
        print(f"    Filter: {view['filter']}")
        if "sort" in view:
            print(f"    Sort: {view['sort']}")
        print()

    return table_ids


if __name__ == "__main__":
    setup_base()
