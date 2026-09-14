"""
migrate_add_payment_fields.py

One-time migration: adds payment_reference and paid_at columns to the
existing laundry_orders table. Run this ONCE, after pulling the Paystack
update, before starting the app.

db.create_all() only creates tables that don't exist yet - it never
alters existing tables, so without this script the app will crash with
"OperationalError: no such column: laundry_orders.payment_reference"
the first time it touches a LaundryOrder.

Usage:
    python migrate_add_payment_fields.py
"""

import sqlite3
import os

DB_PATH = os.path.join("instance", "errandly.db")

if not os.path.exists(DB_PATH):
    # Fallback: some setups keep the db file in the project root
    # instead of instance/ - check there too before giving up.
    DB_PATH = "errandly.db"

if not os.path.exists(DB_PATH):
    print(f"Could not find your database file. Looked in "
          f"'instance/errandly.db' and 'errandly.db'.")
    print("If your DATABASE_URL in .env points somewhere else, "
          "edit DB_PATH in this script to match.")
    raise SystemExit(1)

print(f"Using database: {DB_PATH}")

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

cursor.execute("PRAGMA table_info(laundry_orders)")
existing_columns = {row[1] for row in cursor.fetchall()}

added = []

if "payment_reference" not in existing_columns:
    cursor.execute(
        "ALTER TABLE laundry_orders ADD COLUMN payment_reference VARCHAR(100)"
    )
    added.append("payment_reference")

if "paid_at" not in existing_columns:
    cursor.execute(
        "ALTER TABLE laundry_orders ADD COLUMN paid_at DATETIME"
    )
    added.append("paid_at")

conn.commit()
conn.close()

if added:
    print(f"Added columns: {', '.join(added)}")
    print("Migration complete. Your existing orders are untouched.")
else:
    print("Both columns already exist. Nothing to do.")
