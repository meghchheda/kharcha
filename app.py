import os
import sqlite3
from datetime import date

from flask import Flask, request, jsonify, render_template, g

app = Flask(__name__)


DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "expenses.db"))



def get_db():
    """Get (or create) the SQLite connection for the current request."""
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Create the expenses table if it doesn't exist yet."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'Uncategorised',
            amount REAL NOT NULL,
            description TEXT DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    conn.commit()
    conn.close()


def row_to_dict(row):
    return {
        "id": row["id"],
        "date": row["date"],
        "category": row["category"],
        "amount": row["amount"],
        "description": row["description"],
    }



@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/expenses", methods=["GET"])
def get_expenses():
    db = get_db()
    rows = db.execute(
        "SELECT * FROM expenses ORDER BY date DESC, id DESC"
    ).fetchall()
    return jsonify([row_to_dict(r) for r in rows])


@app.route("/api/expenses", methods=["POST"])
def add_expense():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "No data provided"}), 400

    expense_date = (data.get("date") or "").strip() or date.today().isoformat()
    category = (data.get("category") or "").strip() or "Uncategorised"
    description = (data.get("description") or "").strip()

    try:
        amount = float(data.get("amount", 0))
        if amount <= 0:
            raise ValueError
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid amount"}), 400

    db = get_db()
    cur = db.execute(
        "INSERT INTO expenses (date, category, amount, description) VALUES (?, ?, ?, ?)",
        (expense_date, category, amount, description),
    )
    db.commit()

    new_row = db.execute("SELECT * FROM expenses WHERE id = ?", (cur.lastrowid,)).fetchone()
    return jsonify(row_to_dict(new_row)), 201



@app.route("/api/expenses/<int:expense_id>", methods=["DELETE"])
def delete_expense(expense_id):
    db = get_db()
    existing = db.execute("SELECT id FROM expenses WHERE id = ?", (expense_id,)).fetchone()
    if existing is None:
        return jsonify({"error": "Expense not found"}), 404

    db.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
    db.commit()
    return jsonify({"ok": True})



@app.route("/api/summary", methods=["GET"])
def get_summary():
    db = get_db()
    rows = db.execute(
        "SELECT category, SUM(amount) as total FROM expenses GROUP BY category ORDER BY total DESC"
    ).fetchall()
    total = db.execute("SELECT SUM(amount) as total FROM expenses").fetchone()["total"] or 0
    return jsonify({
        "by_category": [{"category": r["category"], "total": r["total"]} for r in rows],
        "total": total,
    })


init_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG", "0") == "1")
