"""LM Compliance System — Legal Metrology (Packaged Commodities) Rules, 2011 compliance checker."""
import os, json, uuid, secrets
from datetime import datetime
from functools import wraps
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from flask import (Flask, request, redirect, url_for, session, render_template,
                   flash, send_file, abort, jsonify, make_response)
from core import db, pipeline, reports as rep

app = Flask(__name__)
app.secret_key = os.environ.get("LM_SECRET", "lm-compliance-demo-secret-change-me")
app.config["MAX_CONTENT_LENGTH"] = 12 * 1024 * 1024

ALLOWED_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".tif"}

# ------------------------------------------------------------------ auth
def _mk_token(user_id):
    """Issue a bearer token (used when the session cookie cannot be set, e.g. inside
    sandboxed preview iframes that reject cookies)."""
    tok = secrets.token_urlsafe(32)
    conn = db.get_conn()
    conn.execute("INSERT INTO auth_tokens(token, user_id) VALUES (?,?)", (tok, user_id))
    conn.commit(); conn.close()
    return tok

def _user_from_token(tok):
    if not tok:
        return None
    conn = db.get_conn()
    row = conn.execute("""SELECT u.* FROM auth_tokens t JOIN users u ON u.id=t.user_id
                          WHERE t.token=? AND u.is_active=1""", (tok,)).fetchone()
    conn.close()
    return row

def current_user():
    """Resolve the current user: session cookie first, then ?token= (Bearer) query param.
    The token fallback keeps the app usable inside sandboxed preview iframes that block cookies."""
    uid = session.get("uid")
    if not uid:
        u = _user_from_token(request.args.get("token") or request.headers.get("X-Auth-Token"))
        if u:
            return u
        return None
    conn = db.get_conn()
    u = conn.execute("SELECT * FROM users WHERE id=? AND is_active=1", (uid,)).fetchone()
    conn.close()
    return u

def login_required(f):
    @wraps(f)
    def w(*a, **k):
        if not current_user():
            return redirect(url_for("login", next=request.path))
        return f(*a, **k)
    return w

def role_required(*roles):
    def deco(f):
        @wraps(f)
        def w(*a, **k):
            u = current_user()
            if not u:
                return redirect(url_for("login"))
            if u["role"] not in roles:
                flash("Access denied — insufficient role.", "danger")
                return redirect(url_for("dashboard"))
            return f(*a, **k)
        return w
    return deco

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        conn = db.get_conn()
        u = conn.execute("SELECT * FROM users WHERE username=? AND is_active=1", (username,)).fetchone()
        conn.close()
        if u and check_password_hash(u["password_hash"], password):
            db.audit(u, "LOGIN", "session", f"{u['username']} logged in")
            # AJAX-style login (fetch) — return a token, the page sets it via localStorage
            if request.headers.get("X-Requested-With") == "fetch" or request.accept_mimetypes.best == "application/json":
                tok = _mk_token(u["id"])
                return jsonify({"ok": True, "token": tok, "role": u["role"],
                                "name": u["full_name"], "next": url_for("dashboard")})
            session.clear()
            session["uid"] = u["id"]
            resp = make_response(redirect(request.args.get("next") or url_for("dashboard")))
            resp.set_cookie("lm_uid", str(u["id"]), samesite="Lax", max_age=60 * 60 * 8)
            return resp
        flash("Invalid credentials or inactive account.", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    u = current_user()
    if u:
        db.audit(u, "LOGOUT", "session", "")
    tok = request.args.get("token")
    if tok:
        conn = db.get_conn()
        conn.execute("DELETE FROM auth_tokens WHERE token=?", (tok,))
        conn.commit(); conn.close()
    session.clear()
    return redirect(url_for("login"))

@app.route("/api/login", methods=["POST"])
def api_login():
    """JSON login for the fetch-based form (returns a bearer token for cookie-less clients)."""
    data = request.get_json(silent=True) or request.form
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))
    conn = db.get_conn()
    u = conn.execute("SELECT * FROM users WHERE username=? AND is_active=1", (username,)).fetchone()
    conn.close()
    if u and check_password_hash(u["password_hash"], password):
        tok = _mk_token(u["id"])
        db.audit(u, "LOGIN", "session", f"{u['username']} logged in (token)")
        return jsonify({"ok": True, "token": tok, "role": u["role"], "name": u["full_name"]})
    return jsonify({"ok": False, "error": "Invalid credentials"}), 401

@app.route("/api/me")
def api_me():
    u = current_user()
    if not u:
        return jsonify({"ok": False}), 401
    return jsonify({"ok": True, "id": u["id"], "username": u["username"],
                    "name": u["full_name"], "role": u["role"],
                    "designation": u["designation"], "state": u["state"]})

@app.context_processor
def inject_globals():
    return {"cur_user": current_user(), "now": datetime.now()}

# ------------------------------------------------------------------ dashboard
@app.route("/")
@app.route("/dashboard")
@login_required
def dashboard():
    conn = db.get_conn()
    total = conn.execute("SELECT COUNT(*) c FROM scans").fetchone()["c"]
    compliant = conn.execute("SELECT COUNT(*) c FROM scans WHERE overall_status='COMPLIANT'").fetchone()["c"]
    partial = conn.execute("SELECT COUNT(*) c FROM scans WHERE overall_status='PARTIALLY COMPLIANT'").fetchone()["c"]
    nonc = conn.execute("SELECT COUNT(*) c FROM scans WHERE overall_status='NON-COMPLIANT'").fetchone()["c"]
    products = conn.execute("SELECT COUNT(DISTINCT product_name) c FROM scans").fetchone()["c"]
    inspections = conn.execute("SELECT COUNT(*) c FROM inspections").fetchone()["c"]
    open_insp = conn.execute("SELECT COUNT(*) c FROM inspections WHERE status='OPEN'").fetchone()["c"]
    recent = conn.execute("""SELECT * FROM scans ORDER BY id DESC LIMIT 8""").fetchall()

    # violations by rule (top 8)
    rule_counts = {}
    for r in conn.execute("SELECT checks_json FROM scans").fetchall():
        for c in json.loads(r["checks_json"] or "[]"):
            if c["status"] == "FAIL":
                key = c["title"].split(" — ")[0]
                rule_counts[key] = rule_counts.get(key, 0) + 1
    top_rules = sorted(rule_counts.items(), key=lambda kv: -kv[1])[:8]

    # severity stats
    sev = {"CRITICAL": 0, "MAJOR": 0, "MINOR": 0}
    for r in conn.execute("SELECT checks_json FROM scans").fetchall():
        for c in json.loads(r["checks_json"] or "[]"):
            if c["status"] == "FAIL":
                sev[c["severity"]] = sev.get(c["severity"], 0) + 1

    # scans per day (last 7)
    by_day = conn.execute("""SELECT substr(created_at,1,10) d, COUNT(*) c FROM scans
                             GROUP BY d ORDER BY d DESC LIMIT 7""").fetchall()
    by_day = list(reversed([(r["d"], r["c"]) for r in by_day]))
    conn.close()
    comp_pct = round(100 * compliant / total, 1) if total else 0
    avg_score = None
    if total:
        conn = db.get_conn()
        avg_score = round(conn.execute("SELECT AVG(score) s FROM scans").fetchone()["s"] or 0)
        conn.close()
    return render_template("dashboard.html", total=total, compliant=compliant, partial=partial,
                           nonc=nonc, products=products, inspections=inspections, open_insp=open_insp,
                           recent=recent, top_rules=top_rules, sev=sev, by_day=by_day,
                           comp_pct=comp_pct, months=json.dumps([m[0] for m in by_day]),
                           days=json.dumps([m[1] for m in by_day]), avg_score=avg_score)

# ------------------------------------------------------------------ scans
@app.route("/scans")
@login_required
def scans():
    q = request.args.get("q", "").strip()
    st = request.args.get("status", "").strip()
    conn = db.get_conn()
    sql = "SELECT * FROM scans WHERE 1=1"; args = []
    if q:
        sql += " AND (product_name LIKE ? OR scan_code LIKE ? OR category LIKE ?)"
        args += [f"%{q}%"] * 3
    if st:
        sql += " AND overall_status=?"
        args.append(st)
    sql += " ORDER BY id DESC LIMIT 200"
    rows = conn.execute(sql, args).fetchall()
    conn.close()
    return render_template("scans.html", rows=rows, q=q, st=st)

@app.route("/scan/new", methods=["GET", "POST"])
@login_required
def scan_new():
    if request.method == "POST":
        source = request.form.get("source", "image")
        product_name = request.form.get("product_name", "").strip()
        category = request.form.get("category", "").strip()
        dims = request.form.get("dims", "").strip()
        if not product_name:
            flash("Product name is required.", "danger")
            return redirect(url_for("scan_new"))
        user = current_user()
        if source == "listing":
            text = request.form.get("listing_text", "")
            if len(text.strip()) < 20:
                flash("Listing text is too short — paste the full product listing.", "danger")
                return redirect(url_for("scan_new"))
            res = pipeline.run_listing_scan(text, product_name, category, user["id"])
            db.audit(user, "SCAN_CREATE", res["scan_code"], "listing")
            return redirect(url_for("scan_detail", scan_id=res["id"]))
        # image upload
        f = request.files.get("image")
        if not f or not f.filename:
            flash("Please choose an image file.", "danger")
            return redirect(url_for("scan_new"))
        ext = os.path.splitext(f.filename)[1].lower()
        if ext not in ALLOWED_EXT:
            flash("Unsupported image format.", "danger")
            return redirect(url_for("scan_new"))
        fname = f"scan_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:6]}{ext}"
        fpath = os.path.join(db.UPLOAD_DIR, secure_filename(fname))
        f.save(fpath)
        try:
            res = pipeline.run_image_scan(fpath, product_name, category, dims, user["id"])
        except Exception as e:
            flash(f"Scan failed: {e}", "danger")
            return redirect(url_for("scan_new"))
        db.audit(user, "SCAN_CREATE", res["scan_code"], "image")
        return redirect(url_for("scan_detail", scan_id=res["id"]))
    return render_template("scan_new.html")

@app.route("/scan/<int:scan_id>")
@login_required
def scan_detail(scan_id):
    conn = db.get_conn()
    row = conn.execute("SELECT * FROM scans WHERE id=?", (scan_id,)).fetchone()
    if not row:
        conn.close(); abort(404)
    checks = json.loads(row["checks_json"] or "[]")
    fields = json.loads(row["font_json"] or "{}")
    ext = json.loads(row["extracted_json"] or "{}")
    insp = conn.execute("SELECT * FROM inspections WHERE scan_id=?", (scan_id,)).fetchall()
    reports_ = conn.execute("SELECT * FROM reports WHERE scan_id=?", (scan_id,)).fetchall()
    conn.close()
    from core.fontsize import required_height_mm
    req = required_height_mm(row["pdp_area_cm2"] or 0) if row["pdp_area_cm2"] else None
    return render_template("scan_detail.html", s=row, checks=checks, fields=fields, ext=ext,
                           insp=insp, reports_=reports_, req=req)

@app.route("/scan/<int:scan_id>/overlay")
@login_required
def scan_overlay(scan_id):
    conn = db.get_conn()
    row = conn.execute("SELECT * FROM scans WHERE id=? AND source='image'", (scan_id,)).fetchone()
    conn.close()
    if not row or not row["file_path"] or not os.path.exists(row["file_path"]):
        abort(404)
    path = pipeline.overlay_for(row, row["file_path"])
    if not path:
        abort(404)
    return send_file(path, mimetype="image/jpeg")

@app.route("/scan/<int:scan_id>/verify", methods=["POST"])
@login_required
def scan_verify(scan_id):
    u = current_user()
    conn = db.get_conn()
    row = conn.execute("SELECT scan_code FROM scans WHERE id=?", (scan_id,)).fetchone()
    if not row:
        conn.close(); abort(404)
    status = request.form.get("review_status", "PENDING")
    conn.execute("UPDATE scans SET review_status=?, notes=? WHERE id=?",
                 (status, request.form.get("notes", "")[:2000], scan_id))
    conn.commit(); conn.close()
    db.audit(u, "REVIEW", row["scan_code"], f"review_status={status}")
    flash("Review status updated.", "success")
    return redirect(url_for("scan_detail", scan_id=scan_id))

# ------------------------------------------------------------------ reports
@app.route("/report/<int:scan_id>/<fmt>")
@login_required
def report_download(scan_id, fmt):
    u = current_user()
    conn = db.get_conn()
    row = conn.execute("SELECT scan_code FROM scans WHERE id=?", (scan_id,)).fetchone()
    conn.close()
    if not row:
        abort(404)
    fn = {"pdf": rep.pdf_report, "docx": rep.docx_report, "csv": rep.csv_report}.get(fmt)
    if not fn:
        abort(404)
    path = fn(scan_id, db.GEN_DIR)
    conn = db.get_conn()
    conn.execute("INSERT INTO reports(scan_id, fmt, file_path, created_by) VALUES (?,?,?,?)",
                 (scan_id, fmt, path, u["id"]))
    conn.commit(); conn.close()
    db.audit(u, "REPORT", row["scan_code"], f"exported {fmt}")
    return send_file(path, as_attachment=True, download_name=os.path.basename(path))

# ------------------------------------------------------------------ products
@app.route("/products")
@login_required
def products():
    conn = db.get_conn()
    rows = conn.execute("""SELECT p.*, COUNT(s.id) scans,
        SUM(CASE WHEN s.overall_status='COMPLIANT' THEN 1 ELSE 0 END) ok
        FROM products p LEFT JOIN scans s ON s.product_id=p.id GROUP BY p.id ORDER BY p.id DESC""").fetchall()
    conn.close()
    return render_template("products.html", rows=rows)

@app.route("/product/<int:pid>")
@login_required
def product_detail(pid):
    conn = db.get_conn()
    p = conn.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
    if not p:
        conn.close(); abort(404)
    scans_ = conn.execute("SELECT * FROM scans WHERE product_id=? ORDER BY id DESC", (pid,)).fetchall()
    conn.close()
    return render_template("product_detail.html", p=p, scans_=scans_)

# ------------------------------------------------------------------ inspections
@app.route("/inspections")
@login_required
def inspections():
    conn = db.get_conn()
    rows = conn.execute("""SELECT i.*, s.product_name, s.scan_code FROM inspections i
        JOIN scans s ON s.id=i.scan_id ORDER BY i.id DESC""").fetchall()
    conn.close()
    return render_template("inspections.html", rows=rows)

@app.route("/inspection/new", methods=["GET", "POST"])
@role_required("admin", "inspector")
def inspection_new():
    if request.method == "POST":
        conn = db.get_conn()
        conn.execute("""INSERT INTO inspections(scan_id, title, location, inspector, findings,
                       action_taken, notice_ref, status) VALUES (?,?,?,?,?,?,?,?)""",
                     (request.form.get("scan_id"), request.form.get("title"),
                      request.form.get("location"), request.form.get("inspector"),
                      request.form.get("findings"), request.form.get("action_taken"),
                      request.form.get("notice_ref"), request.form.get("status", "OPEN")))
        conn.commit(); conn.close()
        u = current_user(); db.audit(u, "INSPECTION_CREATE", request.form.get("title"), "inspection")
        flash("Inspection recorded.", "success")
        return redirect(url_for("inspections"))
    conn = db.get_conn()
    scans_ = conn.execute("SELECT id, scan_code, product_name, overall_status FROM scans ORDER BY id DESC").fetchall()
    conn.close()
    return render_template("inspection_new.html", scans_=scans_)

@app.route("/inspection/<int:iid>/status", methods=["POST"])
@role_required("admin", "inspector")
def inspection_status(iid):
    st = request.form.get("status", "OPEN")
    conn = db.get_conn()
    conn.execute("UPDATE inspections SET status=? WHERE id=?", (st, iid))
    conn.commit(); conn.close()
    db.audit(current_user(), "INSPECTION_UPDATE", str(iid), f"status={st}")
    flash("Inspection status updated.", "success")
    return redirect(url_for("inspections"))

# ------------------------------------------------------------------ users (admin)
@app.route("/users")
@role_required("admin")
def users():
    conn = db.get_conn()
    rows = conn.execute("SELECT * FROM users ORDER BY id").fetchall()
    conn.close()
    return render_template("users.html", rows=rows)

@app.route("/user/new", methods=["POST"])
@role_required("admin")
def user_new():
    u = current_user()
    username = request.form.get("username", "").strip()
    pw = request.form.get("password", "")
    if len(username) < 3 or len(pw) < 6:
        flash("Username (min 3 chars) and password (min 6 chars) required.", "danger")
        return redirect(url_for("users"))
    conn = db.get_conn()
    try:
        conn.execute("INSERT INTO users(username, password_hash, full_name, role, designation, state) VALUES (?,?,?,?,?,?)",
                     (username, generate_password_hash(pw), request.form.get("full_name", username),
                      request.form.get("role", "viewer"), request.form.get("designation", ""),
                      request.form.get("state", "")))
        conn.commit()
        db.audit(u, "USER_CREATE", username, request.form.get("role"))
        flash(f"User '{username}' created.", "success")
    except Exception as e:
        flash(f"Could not create user: {e}", "danger")
    conn.close()
    return redirect(url_for("users"))

@app.route("/user/<int:uid>/toggle")
@role_required("admin")
def user_toggle(uid):
    if uid == current_user()["id"]:
        flash("You cannot deactivate your own account.", "danger")
        return redirect(url_for("users"))
    conn = db.get_conn()
    conn.execute("UPDATE users SET is_active = 1 - is_active WHERE id=?", (uid,))
    conn.commit(); conn.close()
    db.audit(current_user(), "USER_TOGGLE", str(uid), "active flipped")
    return redirect(url_for("users"))

# ------------------------------------------------------------------ audit & settings & docs
@app.route("/audit")
@role_required("admin")
def audit():
    conn = db.get_conn()
    rows = conn.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT 300").fetchall()
    conn.close()
    return render_template("audit.html", rows=rows)

@app.route("/docs")
@login_required
def docs():
    return render_template("docs.html")

@app.route("/health")
def health():
    return jsonify({"status": "ok", "app": "LM Compliance System"})

# ---------------------------------------------------------------- bootstrap
def _bootstrap():
    """Create the schema and seed demo data on first boot (hosting-friendly:
    runs in a background thread so the server starts listening immediately)."""
    try:
        db.init_db()
        conn = db.get_conn()
        n_users = conn.execute("SELECT COUNT(*) c FROM users").fetchone()[0]
        n_scans = conn.execute("SELECT COUNT(*) c FROM scans").fetchone()[0]
        conn.close()
        if n_users == 0 or n_scans == 0:
            import threading
            threading.Thread(target=_seed_worker, name="seed-demo", daemon=True).start()
    except Exception as e:
        print(f"[bootstrap] warning: {e}")

def _seed_worker():
    import seed
    try:
        seed.seed()
        print("[bootstrap] demo data ready")
    except Exception as e:
        print(f"[bootstrap] seeding failed: {e}")

_bootstrap()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
