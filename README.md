# 🥛 Amul Order Portal v2 — PIN Auth + Mobile First

Complete mobile-ready order management system with PIN login for all customers.

---

## 🚀 Quick Start

```bash
pip install flask openpyxl
python app.py
# Open: http://localhost:5000
```

---

## 🔐 Login System

### Admin Login
| Field    | Value   |
|----------|---------|
| Username | `admin` |
| PIN      | `1234`  |

> ⚠️ **Change admin PIN immediately** after first login via Profile → Change PIN

### Customer Login
- Customers log in with their **phone number** + **4-digit PIN**
- Admin sets PIN when adding a customer
- Admin can reset any customer's PIN anytime

---

## 👑 Admin Features
- **Order Tab** — Place orders on behalf of any customer
- **Manage Tab**:
  - **Orders** — View, confirm, cancel, delete orders + Excel export
  - **Summary** — Total quantities to order from Amul company today
  - **Customers** — Add/delete customers, reset PINs
- **Profile** — Change admin PIN, logout

## 📱 Customer Features
- **Order Tab** — Browse products, select quantities, place order
- **My Orders** — View own order history, cancel pending orders
- **Profile** — Change own PIN, logout

---

## 📁 File Structure

```
amul_system_v2/
├── app.py              ← Flask backend (all APIs + auth)
├── requirements.txt    ← pip dependencies
├── README.md
├── data/
│   ├── orders.json     ← All orders (auto-created)
│   ├── customers.json  ← Customer list + hashed PINs
│   └── admin.json      ← Admin credentials (hashed PIN)
└── templates/
    └── index.html      ← Full mobile-first frontend
```

---

## 🔒 Security Notes
- All PINs are **SHA-256 hashed** — never stored in plain text
- Sessions last 12 hours, then require re-login
- Customers can **only see their own orders**
- Only admin can see all orders, summary, and manage customers

---

## 📊 Excel Export (3 Sheets)
1. **All Orders** — Every order with customer details
2. **Order Summary** — Total quantities per product (what to order from company)
3. **Customer Breakdown** — Who ordered what

---

## ➕ Adding Products
Edit the `PRODUCTS` list in `app.py`:
```python
{"id": "unique_id", "name": "Product Name", "variant": "Size", "category": "Milk", "emoji": "🥛"},
```

---

## 🌐 Deploy on Network (LAN)
To let customers access from their phones on same WiFi:
```bash
python app.py  # finds your IP e.g. 192.168.1.5
# Customers open: http://192.168.1.5:5000
```
Or change `app.run()` to `app.run(host='0.0.0.0', port=5000)` in app.py.
