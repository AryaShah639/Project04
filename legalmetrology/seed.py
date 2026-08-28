"""Seed the demo database: users, sample products, scans (run through the real pipeline), inspection."""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from werkzeug.security import generate_password_hash
from core import db, pipeline, sample_data

def seed():
    db.init_db()
    conn = db.get_conn()
    if conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"] == 0:
        conn.executemany("INSERT INTO users(username, password_hash, full_name, role, designation, state) VALUES (?,?,?,?,?,?)", [
            ("admin", generate_password_hash("admin123"), "Chief Controller", "admin",
             "Controller of Legal Metrology", "Maharashtra"),
            ("inspector", generate_password_hash("inspector123"), "Asha Verma", "inspector",
             "Legal Metrology Inspector", "Maharashtra"),
            ("viewer", generate_password_hash("viewer123"), "Rahul Mehta", "viewer",
             "Enforcement Officer (view-only)", "Gujarat"),
        ])
        conn.commit()
    count = conn.execute("SELECT COUNT(*) c FROM scans").fetchone()["c"]
    conn.close()
    if count:
        print(f"Database already seeded ({count} scans). Skipping.")
        return

    labels = sample_data.generate_all()
    admin = {"id": 1, "username": "admin"}

    # --- image scans ---
    p = pipeline.run_image_scan(labels["compliant_tea"], "FreshLeaf Premium Darjeeling Tea", "Tea - Food", "10x7.6", admin["id"])
    print(f"[seed] compliant_tea  -> {p['status']} (score {p['score']})")
    conn = db.get_conn()
    conn.execute("INSERT INTO products(name, category, brand, manufacturer) VALUES (?,?,?,?)",
                 ("FreshLeaf Premium Darjeeling Tea", "Tea - Food", "FreshLeaf", "FreshLeaf Beverages Pvt. Ltd."))
    conn.execute("UPDATE scans SET product_id=(SELECT MAX(id) FROM products) WHERE id=?", (p["id"],))
    conn.commit(); conn.close()

    p = pipeline.run_image_scan(labels["noncompliant_noodles"], "NoodleKing Instant Noodles Masala", "Noodles - Food (Imported)", "10x7.6", admin["id"])
    print(f"[seed] noncompliant_noodles -> {p['status']} (score {p['score']})")

    p = pipeline.run_image_scan(labels["partial_soap"], "GlowCare Bathing Soap Neem & Tulsi", "Soap - Cosmetics/Toiletries", "10x7.6", admin["id"])
    print(f"[seed] partial_soap     -> {p['status']} (score {p['score']})")

    p = pipeline.run_image_scan(labels["expired_milk"], "DoodhMilk Toned Milk", "Milk - Dairy", "10x7.6", admin["id"])
    print(f"[seed] expired_milk     -> {p['status']} (score {p['score']})")

    # --- listing scans ---
    p = pipeline.run_listing_scan(sample_data.LISTING_COMPLIANT, "FreshLeaf Premium Darjeeling Tea (Listing)", "Tea - Food", admin["id"])
    print(f"[seed] listing_compliant -> {p['status']} (score {p['score']})")

    p = pipeline.run_listing_scan(sample_data.LISTING_NONCOMPLIANT, "NoodleKing Instant Noodles (Listing)", "Noodles - Food (Imported)", admin["id"])
    print(f"[seed] listing_noncompliant -> {p['status']} (score {p['score']})")

    # --- inspection + one PDF report ---
    conn = db.get_conn()
    row = conn.execute("SELECT id FROM scans ORDER BY id").fetchone()
    conn.execute("INSERT INTO inspections(scan_id, title, location, inspector, findings, action_taken, notice_ref, status) VALUES (?,?,?,?,?,?,?,?)",
                 (row["id"], "Market surveillance - demo store", "BigBasket Mart, Andheri West, Mumbai",
                  "Asha Verma (Inspector)", "Label screening flagged issues; physical verification pending.",
                  "Notice issued for rectification", "LM/Notice/2026/0142", "OPEN"))
    conn.commit(); conn.close()

    from core import reports
    conn = db.get_conn()
    r = conn.execute("SELECT id FROM scans WHERE overall_status != 'COMPLIANT' ORDER BY id LIMIT 1").fetchone()
    if r:
        path = reports.pdf_report(r["id"], db.GEN_DIR, admin)
        conn.execute("INSERT INTO reports(scan_id, fmt, file_path, created_by) VALUES (?,?,?,?)",
                     (r["id"], "pdf", path, admin["id"]))
        conn.commit()
    conn.close()
    print("[seed] done.")

if __name__ == "__main__":
    seed()
