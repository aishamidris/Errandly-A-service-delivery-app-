"""
migrate_add_notification_order_id.py

One-time migration: adds the order_id column to the existing
notifications table, so notifications can link back to the laundry
order they're about.

db.create_all() only creates tables that don't exist yet - it never
alters existing tables, so without this script the app will crash
with "OperationalError: no such column: notifications.order_id" the
first time it touches a Notification, if you already had a
notifications table before this update.

If you're setting up the database for the first time, you don't need
this script - db.create_all() will already include the new column.

Usage:
    python migrate_add_notification_order_id.py
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

cursor.execute("PRAGMA table_info(notifications)")
existing_columns = {row[1] for row in cursor.fetchall()}

if "order_id" not in existing_columns:
    cursor.execute(
        "ALTER TABLE notifications ADD COLUMN order_id INTEGER "
        "REFERENCES laundry_orders(id)"
    )
    conn.commit()
    print("Added column: order_id")
    print("Migration complete. Existing notifications are untouched "
          "(their order_id will just be NULL, so they won't show a "
          "'View Order' link - only new notifications going forward "
          "will link to their order).")
else:
    print("order_id already exists. Nothing to do.")

conn.close()
