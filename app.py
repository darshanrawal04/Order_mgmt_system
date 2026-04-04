from flask import Flask, request, jsonify, send_file, session, redirect, url_for
from functools import wraps
import json, os, hashlib, secrets
from datetime import datetime, timedelta
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)
app.permanent_session_lifetime = timedelta(hours=12)

# ── File paths ────────────────────────────────────────────────────────────────
ORDERS_FILE    = "data/orders.json"
CUSTOMERS_FILE = "data/customers.json"
ADMIN_FILE     = "data/admin.json"

os.makedirs("data", exist_ok=True)
os.makedirs("templates", exist_ok=True)

# ── Products ──────────────────────────────────────────────────────────────────
PRODUCTS = [
    {"id": "amul_gold_500ml",  "name": "Amul Gold",       "variant": "500 mL", "category": "Milk",       "emoji": "🥛"},
    {"id": "amul_gold_6ltr",   "name": "Amul Gold",       "variant": "6 Ltr",  "category": "Milk",       "emoji": "🥛"},
    {"id": "amul_taaza_500ml", "name": "Amul Taaza",      "variant": "500 mL", "category": "Milk",       "emoji": "🍼"},
    {"id": "amul_taaza_6ltr",  "name": "Amul Taaza",      "variant": "6 Ltr",  "category": "Milk",       "emoji": "🍼"},
    {"id": "amul_taaza_pouch", "name": "Amul Taaza",      "variant": "Pouch",  "category": "Milk",       "emoji": "🍼"},
    {"id": "buttermilk_500ml", "name": "Buttermilk",      "variant": "500 mL", "category": "Buttermilk", "emoji": "🥤"},
    {"id": "buttermilk_6ltr",  "name": "Buttermilk",      "variant": "6 Ltr",  "category": "Buttermilk", "emoji": "🥤"},
    {"id": "dahi_200ml",       "name": "Amul Dahi",       "variant": "200 mL", "category": "Dahi",       "emoji": "🍶"},
    {"id": "dahi_1kg",         "name": "Amul Dahi",       "variant": "1 Kg",   "category": "Dahi",       "emoji": "🍶"},
]

# ── Helpers ───────────────────────────────────────────────────────────────────
def hash_pin(pin):
    return hashlib.sha256(pin.encode()).hexdigest()

def load_json(path, default):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def load_customers(): return load_json(CUSTOMERS_FILE, [])
def save_customers(d): save_json(CUSTOMERS_FILE, d)
def load_orders():    return load_json(ORDERS_FILE, [])
def save_orders(d):   save_json(ORDERS_FILE, d)

def load_admin():
    default = {"username": "admin", "pin": hash_pin("1234"), "name": "Admin"}
    return load_json(ADMIN_FILE, default)

def save_admin(d): save_json(ADMIN_FILE, d)

def init_admin():
    if not os.path.exists(ADMIN_FILE):
        save_admin({"username": "admin", "pin": hash_pin("1234"), "name": "Admin"})

# ── Auth decorators ───────────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("user_id"):
            return jsonify({"error": "Not authenticated", "redirect": "/"}), 401
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("is_admin"):
            return jsonify({"error": "Admin only"}), 403
        return f(*args, **kwargs)
    return decorated

# ── Serve HTML ────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    with open("templates/index.html", encoding="utf-8") as f:
        return f.read()

# ── Auth APIs ─────────────────────────────────────────────────────────────────
@app.route("/api/auth/login", methods=["POST"])
def login():
    data = request.json
    phone = data.get("phone", "").strip()
    pin   = data.get("pin", "").strip()

    # Admin login
    admin = load_admin()
    if phone == admin["username"] and hash_pin(pin) == admin["pin"]:
        session.permanent = True
        session["user_id"]   = "admin"
        session["user_name"] = admin["name"]
        session["is_admin"]  = True
        return jsonify({"success": True, "is_admin": True, "name": admin["name"]})

    # Customer login
    customers = load_customers()
    for c in customers:
        if c["phone"] == phone and hash_pin(pin) == c["pin"]:
            session.permanent = True
            session["user_id"]   = c["id"]
            session["user_name"] = c["name"]
            session["is_admin"]  = False
            return jsonify({"success": True, "is_admin": False, "name": c["name"], "customer": c})

    return jsonify({"success": False, "error": "Wrong phone number or PIN. Try again."}), 401

@app.route("/api/auth/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"success": True})

@app.route("/api/auth/me", methods=["GET"])
def me():
    if not session.get("user_id"):
        return jsonify({"logged_in": False})
    customers = load_customers()
    c = next((x for x in customers if x["id"] == session["user_id"]), None)
    return jsonify({
        "logged_in": True,
        "user_id":  session["user_id"],
        "name":     session["user_name"],
        "is_admin": session.get("is_admin", False),
        "customer": c
    })

@app.route("/api/auth/change-pin", methods=["POST"])
@login_required
def change_pin():
    data = request.json
    old_pin = data.get("old_pin", "")
    new_pin = data.get("new_pin", "")

    if len(new_pin) != 4 or not new_pin.isdigit():
        return jsonify({"success": False, "error": "PIN must be exactly 4 digits"}), 400

    if session.get("is_admin"):
        admin = load_admin()
        if hash_pin(old_pin) != admin["pin"]:
            return jsonify({"success": False, "error": "Old PIN is incorrect"}), 400
        admin["pin"] = hash_pin(new_pin)
        save_admin(admin)
        return jsonify({"success": True})

    customers = load_customers()
    for c in customers:
        if c["id"] == session["user_id"]:
            if hash_pin(old_pin) != c["pin"]:
                return jsonify({"success": False, "error": "Old PIN is incorrect"}), 400
            c["pin"] = hash_pin(new_pin)
            save_customers(customers)
            return jsonify({"success": True})

    return jsonify({"success": False, "error": "User not found"}), 404

# ── Products API ──────────────────────────────────────────────────────────────
@app.route("/api/products", methods=["GET"])
@login_required
def get_products():
    return jsonify(PRODUCTS)

# ── Customer APIs ─────────────────────────────────────────────────────────────
@app.route("/api/customers", methods=["GET"])
@login_required
def get_customers():
    customers = load_customers()
    # Strip PINs before sending
    return jsonify([{k: v for k, v in c.items() if k != "pin"} for c in customers])

@app.route("/api/customers", methods=["POST"])
@login_required
@admin_required
def add_customer():
    data = request.json
    name  = data.get("name", "").strip()
    phone = data.get("phone", "").strip()
    pin   = data.get("pin", "").strip()
    area  = data.get("area", "").strip()

    if not name or not phone or not pin:
        return jsonify({"success": False, "error": "Name, phone and PIN are required"}), 400
    if len(pin) != 4 or not pin.isdigit():
        return jsonify({"success": False, "error": "PIN must be 4 digits"}), 400

    customers = load_customers()
    if any(c["phone"] == phone for c in customers):
        return jsonify({"success": False, "error": "Phone number already registered"}), 400

    cid = f"C{len(customers)+1:03d}_{int(datetime.now().timestamp())}"
    customer = {"id": cid, "name": name, "phone": phone, "pin": hash_pin(pin), "area": area, "created_at": datetime.now().isoformat()}
    customers.append(customer)
    save_customers(customers)
    return jsonify({"success": True, "customer": {k: v for k, v in customer.items() if k != "pin"}})

@app.route("/api/customers/<cid>", methods=["PUT"])
@login_required
@admin_required
def update_customer(cid):
    data = request.json
    customers = load_customers()
    for c in customers:
        if c["id"] == cid:
            c["name"]  = data.get("name", c["name"])
            c["phone"] = data.get("phone", c["phone"])
            c["area"]  = data.get("area", c["area"])
            if data.get("pin"):
                pin = data["pin"]
                if len(pin) != 4 or not pin.isdigit():
                    return jsonify({"success": False, "error": "PIN must be 4 digits"}), 400
                c["pin"] = hash_pin(pin)
            save_customers(customers)
            return jsonify({"success": True})
    return jsonify({"success": False, "error": "Not found"}), 404

@app.route("/api/customers/<cid>", methods=["DELETE"])
@login_required
@admin_required
def delete_customer(cid):
    customers = load_customers()
    customers = [c for c in customers if c["id"] != cid]
    save_customers(customers)
    return jsonify({"success": True})

# ── Order APIs ────────────────────────────────────────────────────────────────
@app.route("/api/orders", methods=["POST"])
@login_required
def place_order():
    data = request.json
    orders = load_orders()
    customers = load_customers()

    # If admin is placing on behalf, allow; otherwise use session user
    if session.get("is_admin"):
        cid = data.get("customer_id")
        c = next((x for x in customers if x["id"] == cid), None)
        if not c:
            return jsonify({"success": False, "error": "Customer not found"}), 400
    else:
        cid = session["user_id"]
        c = next((x for x in customers if x["id"] == cid), None)

    oid = f"ORD{datetime.now().strftime('%Y%m%d%H%M%S')}{len(orders)+1:03d}"
    order = {
        "id": oid,
        "customer_id":    c["id"] if c else "admin",
        "customer_name":  c["name"] if c else "Admin",
        "customer_phone": c.get("phone", "") if c else "",
        "customer_area":  c.get("area", "") if c else "",
        "items":          data["items"],
        "notes":          data.get("notes", ""),
        "status":         "pending",
        "created_at":     datetime.now().isoformat(),
        "date":           datetime.now().strftime("%d-%m-%Y"),
        "time":           datetime.now().strftime("%H:%M"),
    }
    orders.append(order)
    save_orders(orders)
    return jsonify({"success": True, "order_id": oid, "order": order})

@app.route("/api/orders", methods=["GET"])
@login_required
def get_orders():
    orders = load_orders()
    date_filter = request.args.get("date", "")

    if not session.get("is_admin"):
        orders = [o for o in orders if o["customer_id"] == session["user_id"]]

    if date_filter:
        orders = [o for o in orders if o.get("date") == date_filter]

    return jsonify(sorted(orders, key=lambda x: x.get("created_at", ""), reverse=True))

@app.route("/api/orders/<oid>", methods=["PUT"])
@login_required
def update_order(oid):
    data = request.json
    orders = load_orders()
    for o in orders:
        if o["id"] == oid:
            # Customers can only update their own pending orders
            if not session.get("is_admin"):
                if o["customer_id"] != session["user_id"]:
                    return jsonify({"success": False, "error": "Not your order"}), 403
                if o["status"] != "pending":
                    return jsonify({"success": False, "error": "Cannot edit a confirmed order"}), 400
            o["items"]      = data.get("items", o["items"])
            o["notes"]      = data.get("notes", o.get("notes", ""))
            o["status"]     = data.get("status", o["status"])
            o["updated_at"] = datetime.now().isoformat()
            save_orders(orders)
            return jsonify({"success": True, "order": o})
    return jsonify({"success": False, "error": "Order not found"}), 404

@app.route("/api/orders/<oid>", methods=["DELETE"])
@login_required
@admin_required
def delete_order(oid):
    orders = [o for o in load_orders() if o["id"] != oid]
    save_orders(orders)
    return jsonify({"success": True})

# ── Summary API ───────────────────────────────────────────────────────────────
@app.route("/api/summary", methods=["GET"])
@login_required
@admin_required
def get_summary():
    orders = load_orders()
    date_filter = request.args.get("date", "")
    if date_filter:
        orders = [o for o in orders if o.get("date") == date_filter]
    orders = [o for o in orders if o.get("status") != "cancelled"]

    summary = {}
    for o in orders:
        for item in o.get("items", []):
            pid = item["product_id"]
            if pid not in summary:
                summary[pid] = {**item, "total_quantity": 0, "customer_count": 0, "customers": set()}
            summary[pid]["total_quantity"] += item["quantity"]
            summary[pid]["customers"].add(o["customer_id"])

    result = []
    for pid, s in summary.items():
        result.append({**s, "customer_count": len(s["customers"]), "customers": list(s["customers"])})

    return jsonify({"summary": result, "total_orders": len(orders), "date": date_filter})

# ── Excel Export ──────────────────────────────────────────────────────────────
@app.route("/api/export/excel", methods=["GET"])
@login_required
@admin_required
def export_excel():
    date_filter = request.args.get("date", datetime.now().strftime("%d-%m-%Y"))
    orders = [o for o in load_orders() if o.get("date") == date_filter and o.get("status") != "cancelled"]

    wb = Workbook()
    hdr_fill = PatternFill("solid", start_color="003087")
    hdr_font = Font(bold=True, color="FFFFFF", size=11)
    bdr = Border(
        left=Side(style="thin", color="CCCCCC"), right=Side(style="thin", color="CCCCCC"),
        top=Side(style="thin", color="CCCCCC"),  bottom=Side(style="thin", color="CCCCCC")
    )
    alt = PatternFill("solid", start_color="EBF3FB")

    def hdr_row(ws, row, headers):
        for col, h in enumerate(headers, 1):
            c = ws.cell(row=row, column=col, value=h)
            c.font, c.fill, c.alignment, c.border = hdr_font, hdr_fill, Alignment(horizontal="center"), bdr

    def set_col_widths(ws, widths):
        for i, w in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(i)].width = w

    # Sheet 1 — All Orders
    ws1 = wb.active
    ws1.title = "All Orders"
    ws1["A1"] = f"Amul Order Report — {date_filter}"
    ws1["A1"].font = Font(bold=True, size=14, color="003087")
    ws1.merge_cells("A1:H1")
    ws1["A1"].alignment = Alignment(horizontal="center")
    hdr_row(ws1, 3, ["Order ID", "Customer", "Phone", "Area", "Product", "Variant", "Qty", "Time"])
    row = 4
    for idx, o in enumerate(orders):
        fill = alt if idx % 2 == 0 else PatternFill("solid", start_color="FFFFFF")
        for item in o.get("items", []):
            for col, val in enumerate([o["id"], o["customer_name"], o.get("customer_phone",""), o.get("customer_area",""), item["product_name"], item["variant"], item["quantity"], o.get("time","")], 1):
                c = ws1.cell(row=row, column=col, value=val)
                c.fill, c.border = fill, bdr
                c.alignment = Alignment(horizontal="center" if col == 7 else "left")
            row += 1
    set_col_widths(ws1, [20, 22, 14, 18, 18, 12, 8, 10])

    # Sheet 2 — Summary
    ws2 = wb.create_sheet("Order Summary")
    ws2["A1"] = f"Total Order Summary — {date_filter}"
    ws2["A1"].font = Font(bold=True, size=14, color="003087")
    ws2.merge_cells("A1:E1")
    ws2["A1"].alignment = Alignment(horizontal="center")
    hdr_row(ws2, 3, ["Product", "Variant", "Category", "Total Qty", "# Customers"])
    summary = {}
    pmap = {p["id"]: p for p in PRODUCTS}
    for o in orders:
        for item in o.get("items", []):
            pid = item["product_id"]
            if pid not in summary:
                summary[pid] = {"name": item["product_name"], "variant": item["variant"], "category": pmap.get(pid, {}).get("category", ""), "qty": 0, "custs": set()}
            summary[pid]["qty"] += item["quantity"]
            summary[pid]["custs"].add(o["customer_id"])
    cat_colors = {"Milk": "D6EAF8", "Buttermilk": "D5F5E3", "Dahi": "FEF9E7"}
    for row_idx, s in enumerate(summary.values(), 4):
        cf = PatternFill("solid", start_color=cat_colors.get(s["category"], "F5F5F5"))
        for col, val in enumerate([s["name"], s["variant"], s["category"], s["qty"], len(s["custs"])], 1):
            c = ws2.cell(row=row_idx, column=col, value=val)
            c.fill, c.border = cf, bdr
            c.alignment = Alignment(horizontal="center" if col >= 4 else "left")
            if col == 4: c.font = Font(bold=True)
    set_col_widths(ws2, [22, 12, 14, 12, 14])

    # Sheet 3 — Customer Breakdown
    ws3 = wb.create_sheet("Customer Breakdown")
    ws3["A1"] = f"Customer-wise Breakdown — {date_filter}"
    ws3["A1"].font = Font(bold=True, size=14, color="003087")
    ws3.merge_cells("A1:F1")
    ws3["A1"].alignment = Alignment(horizontal="center")
    hdr_row(ws3, 3, ["Customer", "Area", "Phone", "Product", "Variant", "Qty"])
    row = 4
    for idx, o in enumerate(sorted(orders, key=lambda x: x["customer_name"])):
        fill = alt if idx % 2 == 0 else PatternFill("solid", start_color="FFFFFF")
        for item in o.get("items", []):
            for col, val in enumerate([o["customer_name"], o.get("customer_area",""), o.get("customer_phone",""), item["product_name"], item["variant"], item["quantity"]], 1):
                c = ws3.cell(row=row, column=col, value=val)
                c.fill, c.border = fill, bdr
                c.alignment = Alignment(horizontal="center" if col == 6 else "left")
            row += 1
    set_col_widths(ws3, [22, 18, 14, 18, 12, 8])

    fname = f"Amul_Orders_{date_filter.replace('-','_')}.xlsx"
    fpath = f"/tmp/{fname}"
    wb.save(fpath)
    return send_file(fpath, as_attachment=True, download_name=fname,
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ── Admin PIN reset ───────────────────────────────────────────────────────────
@app.route("/api/admin/reset-customer-pin", methods=["POST"])
@login_required
@admin_required
def reset_customer_pin():
    data = request.json
    cid     = data.get("customer_id")
    new_pin = data.get("new_pin", "")
    if len(new_pin) != 4 or not new_pin.isdigit():
        return jsonify({"success": False, "error": "PIN must be 4 digits"}), 400
    customers = load_customers()
    for c in customers:
        if c["id"] == cid:
            c["pin"] = hash_pin(new_pin)
            save_customers(customers)
            return jsonify({"success": True})
    return jsonify({"success": False, "error": "Customer not found"}), 404

if __name__ == "__main__":
    init_admin()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
