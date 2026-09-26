from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
import sqlite3
import random
import string

from flask import make_response
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from io import BytesIO
from werkzeug.utils import secure_filename
import uuid

app = Flask(__name__)

app.secret_key = "expense_tracker_secret"


# ---------------- PWA: MANIFEST + SERVICE WORKER ---------------- #
# Serves these two files from the site's ROOT ("/manifest.json",
# "/sw.js") instead of "/static/...", which is what lets the app be
# installed with scope "/" (the whole site) and get its own icon on the
# phone's home screen, like WhatsApp or any other app.

@app.route('/manifest.json')
def pwa_manifest():
    return send_from_directory(
        os.path.join(app.root_path, 'static'),
        'manifest.json',
        mimetype='application/manifest+json'
    )


@app.route('/sw.js')
def pwa_service_worker():
    response = send_from_directory(
        os.path.join(app.root_path, 'static'),
        'sw.js',
        mimetype='application/javascript'
    )
    # Allows a worker served from "/sw.js" to control the entire site.
    response.headers['Service-Worker-Allowed'] = '/'
    return response


# ---------------- DATABASE CONNECTION ---------------- #

import os
import sqlite3
import random
import string

def get_db_connection():
    db_path = os.path.join(os.path.dirname(__file__), "expense tracker.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------- PROFILE PHOTO SETUP ---------------- #

PROFILE_PHOTO_FOLDER = os.path.join(os.path.dirname(__file__), "static", "uploads", "profile_photos")
ALLOWED_PHOTO_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}


def allowed_photo_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_PHOTO_EXTENSIONS


def update_users_photo_column():
    """Adds a `photo` column to users (stores just the filename saved under
    static/uploads/profile_photos/), and makes sure that folder exists."""

    os.makedirs(PROFILE_PHOTO_FOLDER, exist_ok=True)

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(users)")
    existing_columns = [row["name"] for row in cursor.fetchall()]

    if "photo" not in existing_columns:
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN photo TEXT")
            conn.commit()
        except Exception:
            pass

    conn.close()

def create_group_expense_table():

    conn = get_db_connection()
    cursor = conn.cursor()



    cursor.execute("""
    CREATE TABLE IF NOT EXISTS group_expense (
        group_expense_id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_id INTEGER,
        user_id INTEGER,
        expense_name TEXT,
        category TEXT,
        paid_by TEXT,
        amount REAL,
        members INTEGER,
        date TEXT
    )
    """)

    conn.commit()

    # If group_expense already existed with an older/legacy shape (e.g.
    # created by database.sql, which only has group_id, paid_by, amount,
    # description, date), CREATE TABLE IF NOT EXISTS above is a no-op and
    # leaves it missing columns the rest of the app needs. Patch those in.
    cursor.execute("PRAGMA table_info(group_expense)")
    existing_columns = [row["name"] for row in cursor.fetchall()]

    required_columns = {
        "user_id": "INTEGER",
        "expense_name": "TEXT",
        "category": "TEXT",
        "paid_by": "TEXT",
        "amount": "REAL",
        "members": "INTEGER",
        "date": "TEXT",
    }

    for column_name, column_type in required_columns.items():
        if column_name not in existing_columns:
            try:
                cursor.execute(f"ALTER TABLE group_expense ADD COLUMN {column_name} {column_type}")
                conn.commit()
            except Exception:
                pass

    # Older schema used "description" instead of "expense_name" - carry
    # over any existing text so old rows still show a name.
    if "description" in existing_columns and "expense_name" in [r for r in required_columns]:
        try:
            cursor.execute("""
                UPDATE group_expense
                SET expense_name = description
                WHERE expense_name IS NULL AND description IS NOT NULL
            """)
            conn.commit()
        except Exception:
            pass

    conn.close()
def update_groups_table():

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            ALTER TABLE groups
            ADD COLUMN group_code TEXT
        """)
    except:
        pass

    conn.commit()
    conn.close()


def create_group_members_table():

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS group_members(
        member_id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_id INTEGER,
        user_id INTEGER
    )
    """)

    conn.commit()
    conn.close()




def update_settlement_columns():
    """
    Makes sure the settlement table matches the schema the app needs:
    (settlement_id, group_id, payer_id, receiver_id, amount, status, created_at).

    Older versions of this project used a different settlement table
    (user_id, member_name ... with NOT NULL constraints on both), which
    blocks inserts from the current code. If that legacy shape is found,
    or any required column is missing, this rebuilds the table with the
    correct schema and carries over any existing rows on a best-effort
    basis. Safe to run every time the app starts.
    """

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(settlement)")
    existing_columns = [row["name"] for row in cursor.fetchall()]

    required_columns = {"group_id", "payer_id", "receiver_id", "amount", "status", "created_at"}

    legacy_columns_present = "user_id" in existing_columns or "member_name" in existing_columns
    table_missing = len(existing_columns) == 0
    missing_required = not required_columns.issubset(set(existing_columns))

    needs_rebuild = table_missing or legacy_columns_present or missing_required

    if needs_rebuild:

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settlement_new (
                settlement_id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER,
                payer_id INTEGER,
                receiver_id INTEGER,
                amount REAL,
                status TEXT DEFAULT 'Pending',
                created_at TEXT
            )
        """)

        if existing_columns:

            # Best-effort carry over of any existing rows into the new shape
            payer_expr = "payer_id" if "payer_id" in existing_columns else (
                "user_id" if "user_id" in existing_columns else "NULL"
            )
            receiver_expr = "receiver_id" if "receiver_id" in existing_columns else "NULL"
            group_expr = "group_id" if "group_id" in existing_columns else "NULL"
            amount_expr = "amount" if "amount" in existing_columns else "0"
            status_expr = "status" if "status" in existing_columns else "'Pending'"
            created_expr = "created_at" if "created_at" in existing_columns else "NULL"

            try:
                cursor.execute(f"""
                    INSERT INTO settlement_new
                        (group_id, payer_id, receiver_id, amount, status, created_at)
                    SELECT {group_expr}, {payer_expr}, {receiver_expr},
                           {amount_expr}, {status_expr}, {created_expr}
                    FROM settlement
                """)
            except Exception:
                pass

            cursor.execute("DROP TABLE settlement")

        cursor.execute("ALTER TABLE settlement_new RENAME TO settlement")

    conn.commit()
    conn.close()


def update_settlement_expense_link():
    """
    Adds a group_expense_id column to settlement so each settlement row can
    be traced back to the exact shared expense it came from. This lets us
    safely recompute splits (e.g. when a new member joins a group) without
    duplicating rows or touching ones that are already marked Paid.
    """

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(settlement)")
    existing_columns = [row["name"] for row in cursor.fetchall()]

    if "group_expense_id" not in existing_columns:
        try:
            cursor.execute("""
                ALTER TABLE settlement
                ADD COLUMN group_expense_id INTEGER
            """)
            conn.commit()
        except Exception:
            pass

    conn.close()


def update_personal_ledger_links():
    """
    Links group money-flow to the personal Income/Expense ledger:
      - expense.group_expense_id  -> the shared expense that generated
        this personal expense row (money the payer actually handed over)
      - income.settlement_id      -> the settlement that generated this
        personal income row (a reimbursement received from a member)
    """

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(expense)")
    expense_columns = [row["name"] for row in cursor.fetchall()]

    if "group_expense_id" not in expense_columns:
        try:
            cursor.execute("ALTER TABLE expense ADD COLUMN group_expense_id INTEGER")
            conn.commit()
        except Exception:
            pass

    cursor.execute("PRAGMA table_info(income)")
    income_columns = [row["name"] for row in cursor.fetchall()]

    if "settlement_id" not in income_columns:
        try:
            cursor.execute("ALTER TABLE income ADD COLUMN settlement_id INTEGER")
            conn.commit()
        except Exception:
            pass

    # expense.settlement_id -> the settlement that generated this personal
    # expense row (a member's own share of a shared expense, deducted from
    # THEIR dashboard once the person who fronted the money confirms they
    # were paid back)
    if "settlement_id" not in expense_columns:
        try:
            cursor.execute("ALTER TABLE expense ADD COLUMN settlement_id INTEGER")
            conn.commit()
        except Exception:
            pass

    conn.close()


def resolve_group_member_id_by_name(cursor, group_id, name):
    """Matches a name (e.g. from the Paid By dropdown) to a current group member's user_id."""

    if not name:
        return None

    cursor.execute("""
        SELECT users.user_id
        FROM group_members
        JOIN users ON group_members.user_id = users.user_id
        WHERE group_members.group_id=? AND LOWER(users.name)=LOWER(?)
    """, (group_id, name.strip()))

    row = cursor.fetchone()

    return row["user_id"] if row else None


def generate_group_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))


# ---------------- SETTLEMENT SPLIT LOGIC ---------------- #

def sync_expense_settlement(cursor, group_expense_id):
    """
    (Re)builds the settlement rows for a single shared expense based on
    who is CURRENTLY a member of the group. Called right after an expense
    is added, and again for every existing expense whenever someone new
    joins the group, so a newly joined member is correctly added to the
    split for expenses too.

    Rows already marked 'Paid' are never touched or removed. Pending rows
    are refreshed to the current per-person amount, new members get a new
    Pending row, and members who are no longer in the group have their
    stale Pending row removed.
    """

    cursor.execute("""
        SELECT group_expense_id, group_id, paid_by, amount, date
        FROM group_expense
        WHERE group_expense_id=?
    """, (group_expense_id,))

    exp = cursor.fetchone()

    if not exp:
        return

    group_id = exp["group_id"]
    amount = float(exp["amount"] or 0)

    # Resolve who paid this expense, matched against actual group members
    cursor.execute("""
        SELECT users.user_id, users.name
        FROM group_members
        JOIN users ON group_members.user_id = users.user_id
        WHERE group_members.group_id=?
    """, (group_id,))

    all_members = cursor.fetchall()

    payer_id = resolve_group_member_id_by_name(cursor, group_id, exp["paid_by"])

    if not payer_id:
        return

    receiver_ids = [m["user_id"] for m in all_members if m["user_id"] != payer_id]

    # Existing settlement rows tied to this expense
    cursor.execute("""
        SELECT settlement_id, payer_id, status
        FROM settlement
        WHERE group_expense_id=?
    """, (group_expense_id,))

    existing_rows = {row["payer_id"]: row for row in cursor.fetchall()}

    if not receiver_ids:
        # Nobody else to split with (e.g. solo group) - drop stale pending rows
        for ower_id, row in existing_rows.items():
            if row["status"] != "Paid":
                cursor.execute(
                    "DELETE FROM settlement WHERE settlement_id=?",
                    (row["settlement_id"],)
                )
        return

    # Split the FULL amount across every current member of the group
    # (payer included) - e.g. a 4000 bill split between 2 members means
    # each person's share is 2000, not 4000. The payer's own share is
    # covered by the fact that they fronted the money; only the other
    # members owe their per-person share back to the payer.
    per_person = amount / len(all_members)

    # Remove pending rows for people who are no longer members of the group
    for ower_id, row in list(existing_rows.items()):
        if ower_id not in receiver_ids and row["status"] != "Paid":
            cursor.execute(
                "DELETE FROM settlement WHERE settlement_id=?",
                (row["settlement_id"],)
            )
            del existing_rows[ower_id]

    for ower_id in receiver_ids:

        row = existing_rows.get(ower_id)

        if row is None:
            # New member (or first time this expense is being synced)
            cursor.execute("""
                INSERT INTO settlement
                (group_id, payer_id, receiver_id, amount, status, created_at, group_expense_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                group_id,
                ower_id,       # person who owes
                payer_id,      # person who gets paid back
                per_person,
                "Pending",
                exp["date"],
                group_expense_id
            ))

        elif row["status"] != "Paid":
            # Refresh the amount in case the member count changed
            cursor.execute("""
                UPDATE settlement
                SET amount=?
                WHERE settlement_id=?
            """, (
                per_person,
                row["settlement_id"]
            ))


def sync_group_settlements(cursor, group_id):
    """Re-syncs every shared expense in a group - used when a member joins."""

    cursor.execute("""
        SELECT group_expense_id
        FROM group_expense
        WHERE group_id=?
    """, (group_id,))

    for row in cursor.fetchall():
        sync_expense_settlement(cursor, row["group_expense_id"])


def backfill_group_expense_data():
    """
    One-time (but safe to re-run) repair pass for group expenses that were
    created before the settlement-splitting and personal-ledger-linking
    logic existed. Without this, old shared expenses have no settlement
    rows (so the Settlement page shows nothing for them) and never
    reduced the payer's personal balance (so Dashboard/Reports never
    reflected the money they actually spent). Safe to run on every
    startup - it only fills in what's missing, and never touches rows
    that already exist.
    """

    conn = get_db_connection()
    cursor = conn.cursor()

    # 1) Make sure every group has settlement rows for all its expenses
    cursor.execute("SELECT group_id FROM groups")
    for group in cursor.fetchall():
        sync_group_settlements(cursor, group["group_id"])

    # 2) Make sure every group expense has a matching personal expense
    #    entry for whoever paid it (so it counts against their balance)
    cursor.execute("""
        SELECT ge.group_expense_id, ge.group_id, ge.paid_by, ge.amount,
               ge.category, ge.date, ge.expense_name, g.group_name
        FROM group_expense ge
        LEFT JOIN groups g ON ge.group_id = g.group_id
        WHERE NOT EXISTS (
            SELECT 1 FROM expense e
            WHERE e.group_expense_id = ge.group_expense_id
        )
    """)

    missing = cursor.fetchall()

    for exp in missing:

        payer_id = resolve_group_member_id_by_name(cursor, exp["group_id"], exp["paid_by"])

        if not payer_id:
            continue

        group_name = exp["group_name"] or "Group"
        expense_name = exp["expense_name"] or "Shared Expense"
        category = exp["category"] or "Others"

        cursor.execute("""
            INSERT INTO expense
            (user_id, amount, category, date, description, group_expense_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            payer_id,
            exp["amount"],
            category,
            exp["date"],
            f"{group_name} - {expense_name} (Group Expense, paid in full)",
            exp["group_expense_id"]
        ))

    conn.commit()
    conn.close()


# Run schema migrations (and repair any pre-existing data) right away,
# no matter how this app is started (python app.py, flask run, an IDE
# "run" button, a WSGI server, or even just importing this module for
# tests). This guarantees the database always has the columns the rest
# of the app expects, instead of relying on the `if __name__ == "__main__"`
# block at the bottom of this file, which only fires for one specific
# way of launching the app.
create_group_expense_table()
update_groups_table()
create_group_members_table()
update_settlement_columns()
update_settlement_expense_link()
update_personal_ledger_links()
update_users_photo_column()
backfill_group_expense_data()


# ---------------- LOGIN PAGE ---------------- #

@app.route('/', methods=['GET', 'POST'])
def login():

    if request.method == 'POST':

        email = request.form['email']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM users WHERE email=? AND password=?",
            (email, password)
        )

        user = cursor.fetchone()

        conn.close()

        if user:
            session['user_id'] = user['user_id']
            session['name'] = user['name']

            return redirect('/dashboard')

        else:
            flash("Invalid Email or Password")
            return redirect('/')

    return render_template('login.html')

# ---------------- REGISTER PAGE ---------------- #

@app.route('/register', methods=['GET', 'POST'])
def register():

    if request.method == 'POST':

        name = request.form['name']
        email = request.form['email']
        phone = request.form['phone']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if password != confirm_password:
            flash("Password and Confirm Password do not match!")
            return redirect('/register')

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()

        if user:
            flash("Email already exists!")
            conn.close()
            return redirect('/register')

        cursor.execute("""
            INSERT INTO users(name, email, password, phone)
            VALUES(?,?,?,?)
        """, (name, email, password, phone))

        conn.commit()
        conn.close()

        flash("Registration Successful! Please Login.")
        return redirect('/')

    return render_template('register.html')


# ---------------- FORGOT PASSWORD ---------------- #

@app.route('/forgot-password')
def forgot_password():
    return render_template('forgot_password.html')


# ---------------- DASHBOARD ---------------- #

@app.route('/dashboard')
def dashboard():

    if 'user_id' not in session:
        return redirect('/')

    conn = get_db_connection()
    cursor = conn.cursor()

    # Total Income
    cursor.execute(
        "SELECT SUM(amount) AS total FROM income WHERE user_id=?",
        (session['user_id'],)
    )
    income = cursor.fetchone()['total'] or 0

    # Total Expense
    cursor.execute(
        "SELECT SUM(amount) AS total FROM expense WHERE user_id=?",
        (session['user_id'],)
    )
    expense = cursor.fetchone()['total'] or 0

    balance = income - expense

    # Recent Expenses
    cursor.execute("""
        SELECT category, amount
        FROM expense
        WHERE user_id=?
        ORDER BY expense_id DESC
        LIMIT 5
    """, (session['user_id'],))

    expenses = cursor.fetchall()

    # Recent Group Expenses
    cursor.execute("""
        SELECT expense_name, paid_by, amount
        FROM group_expense
        WHERE user_id=?
        ORDER BY group_expense_id DESC
        LIMIT 5
    """, (session['user_id'],))

    group_expenses = cursor.fetchall()

    # Pending Settlements (amounts this user owes to others)
    cursor.execute("""
        SELECT
            receiver.name AS member_name,
            s.amount,
            s.status
        FROM settlement s
        JOIN users receiver
            ON s.receiver_id = receiver.user_id
        WHERE s.payer_id=?
        ORDER BY s.settlement_id DESC
        LIMIT 5
    """, (session['user_id'],))

    settlements = cursor.fetchall()

    # Profile photo (for the avatar shown next to the greeting)
    cursor.execute(
        "SELECT photo FROM users WHERE user_id=?",
        (session['user_id'],)
    )
    profile_row = cursor.fetchone()
    user_photo = profile_row['photo'] if profile_row else None

    conn.close()

    return render_template(
        'dashboard.html',
        income=income,
        expense=expense,
        balance=balance,
        savings=balance,
        expenses=expenses,
        username=session['name'],
        group_expenses=group_expenses,
        settlements=settlements,
        user_photo=user_photo
    )
    
# ---------------- INCOME ---------------- #

@app.route('/income', methods=['GET', 'POST'])
def income():

    if 'user_id' not in session:
        return redirect('/')

    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':

        source = request.form['source']
        amount = request.form['amount']
        date = request.form['date']
        description = request.form['description']

        cursor.execute("""
            INSERT INTO income(user_id, amount, source, date, description)
            VALUES (?, ?, ?, ?, ?)
        """, (
            session['user_id'],
            amount,
            source,
            date,
            description
        ))

        conn.commit()

        flash("Income Added Successfully!")

        return redirect('/dashboard')

    cursor.execute(
        "SELECT * FROM income WHERE user_id=? ORDER BY income_id DESC",
        (session['user_id'],)
    )

    incomes = cursor.fetchall()

    cursor.execute(
        "SELECT SUM(amount) AS total FROM income WHERE user_id=?",
        (session['user_id'],)
    )

    total = cursor.fetchone()['total'] or 0

    conn.close()

    return render_template(
        'income.html',
        incomes=incomes,
        total_income=total
    )
# ---------------- EXPENSE ---------------- #

@app.route('/expense', methods=['GET', 'POST'])
def expense():

    if 'user_id' not in session:
        return redirect('/')

    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':

        amount = request.form['amount']
        category = request.form['category']
        date = request.form['date']
        description = request.form['description']

        try:
            amount_value = float(amount)
        except (TypeError, ValueError):
            amount_value = 0

        cursor.execute(
            "SELECT SUM(amount) AS total FROM income WHERE user_id=?",
            (session['user_id'],)
        )
        total_income = cursor.fetchone()['total'] or 0

        cursor.execute(
            "SELECT SUM(amount) AS total FROM expense WHERE user_id=?",
            (session['user_id'],)
        )
        total_expense_so_far = cursor.fetchone()['total'] or 0

        remaining = total_income - total_expense_so_far

        # Your balance should never go negative - if this expense is more
        # than what's left, stop it here with a clear warning instead of
        # quietly letting the dashboard show a minus amount.
        if amount_value > remaining:
            conn.close()
            flash(
                f"⚠️ This expense is more than your remaining balance of ₹{remaining:.2f}. "
                f"Add more income first, or lower the amount.",
                "error"
            )
            return redirect('/expense')

        cursor.execute("""
            INSERT INTO expense(user_id, amount, category, date, description)
            VALUES (?, ?, ?, ?, ?)
        """, (
            session['user_id'],
            amount,
            category,
            date,
            description
        ))

        conn.commit()

        # Notification Save
        cursor.execute("""
            INSERT INTO notifications
            (user_id, message, created_at)
            VALUES (?, ?, datetime('now'))
        """, (
            session['user_id'],
            f"💸 Expense ₹{amount} added successfully."
        ))

        conn.commit()

        flash("Expense Added Successfully!")

        return redirect('/expense')

    cursor.execute(
        "SELECT * FROM expense WHERE user_id=? ORDER BY expense_id DESC",
        (session['user_id'],)
    )

    expenses = cursor.fetchall()

    cursor.execute(
        "SELECT SUM(amount) AS total FROM expense WHERE user_id=?",
        (session['user_id'],)
    )

    total = cursor.fetchone()['total'] or 0

    conn.close()

    return render_template(
        'expense.html',
        expenses=expenses,
        total_expense=total
    )
 # ---------------- MY GROUPS ---------------- #

@app.route('/my_groups')
def my_groups():

    if 'user_id' not in session:
        return redirect('/')

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT DISTINCT
            g.group_id,
            g.group_name,
            g.group_code,
            g.created_by
        FROM groups g
        LEFT JOIN group_members gm
            ON g.group_id = gm.group_id
        WHERE g.created_by = ?
           OR gm.user_id = ?
        ORDER BY g.group_id DESC
    """, (
        session['user_id'],
        session['user_id']
    ))

    groups = cursor.fetchall()

    conn.close()

    return render_template(
        'my_groups.html',
        groups=groups,
        current_user_id=session['user_id']
    )
@app.route('/open_group/<int:group_id>')
def open_group(group_id):

    session['group_id'] = group_id

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT group_name FROM groups WHERE group_id=?", (group_id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        session['group_name'] = row['group_name']

    return redirect('/group_expense')
# ---------------- GROUP EXPENSE ---------------- #

@app.route('/group_expense', methods=['GET', 'POST'])
def group_expense():

    if 'user_id' not in session:
        return redirect('/')

    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':

        expense_name = request.form['expense_name']
        group_id = session.get('group_id')
        category = request.form['category']
        paid_by = request.form['paid_by']
        amount = float(request.form['amount'])
        date = request.form['date']

        # Check group selected
        if not group_id:
            flash("Please join or create a group first!")
            conn.close()
            return redirect('/group_expense')

        # Total members
        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM group_members
            WHERE group_id=?
        """, (group_id,))

        members = cursor.fetchone()["total"]

        # Minimum members check
        if members < 2:
            flash("At least 2 members are required in the group!")
            conn.close()
            return redirect('/group_expense')

        # Figure out who's actually paying and make sure THEIR balance can
        # cover it, before we write anything - avoids leaving behind a
        # group expense / settlement rows if this turns out to be blocked.
        payer_id = resolve_group_member_id_by_name(cursor, group_id, paid_by)

        if payer_id:
            cursor.execute(
                "SELECT SUM(amount) AS total FROM income WHERE user_id=?",
                (payer_id,)
            )
            payer_income = cursor.fetchone()['total'] or 0

            cursor.execute(
                "SELECT SUM(amount) AS total FROM expense WHERE user_id=?",
                (payer_id,)
            )
            payer_expense_so_far = cursor.fetchone()['total'] or 0

            payer_remaining = payer_income - payer_expense_so_far

            if amount > payer_remaining:
                conn.close()
                flash(
                    f"⚠️ {paid_by}'s balance is only ₹{payer_remaining:.2f} - this expense "
                    f"is more than they have. Add more income for {paid_by} first, or lower the amount.",
                    "error"
                )
                return redirect('/group_expense')

        # Save expense
        cursor.execute("""
            INSERT INTO group_expense
            (group_id, user_id, expense_name, category, paid_by, amount, members, date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            group_id,
            session['user_id'],
            expense_name,
            category,
            paid_by,
            amount,
            members,
            date
        ))

        conn.commit()

        new_expense_id = cursor.lastrowid

        # Split the expense among the CURRENT members of the group and
        # create a "who owes whom" settlement row for everyone except
        # the person who paid.
        sync_expense_settlement(cursor, new_expense_id)

        # The payer handed over the FULL amount out of their own pocket,
        # so record it as a personal expense too - this is what makes it
        # show up in their Dashboard/Reports savings right away. As their
        # members pay them back (settlement marked Paid), that comes back
        # in as personal income.
        cursor.execute("SELECT group_name FROM groups WHERE group_id=?", (group_id,))
        group_row = cursor.fetchone()
        group_name = group_row["group_name"] if group_row else "Group"

        if payer_id:
            cursor.execute("""
                INSERT INTO expense
                (user_id, amount, category, date, description, group_expense_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                payer_id,
                amount,
                category,
                date,
                f"{group_name} - {expense_name} (Group Expense, paid in full)",
                new_expense_id
            ))

        conn.commit()

        flash("Group Expense Added Successfully!")

        return redirect('/group_expense')

    # Expense History
    history_query = """
        SELECT
            ge.*,
            g.group_name AS group_name,
            (SELECT COUNT(*) FROM settlement s WHERE s.group_expense_id = ge.group_expense_id) AS total_shares,
            (SELECT COUNT(*) FROM settlement s WHERE s.group_expense_id = ge.group_expense_id AND s.status='Paid') AS paid_shares,
            (SELECT COUNT(*) FROM group_members gm WHERE gm.group_id = ge.group_id) AS live_member_count
        FROM group_expense ge
        LEFT JOIN groups g ON ge.group_id = g.group_id
    """

    if 'group_id' in session:

        cursor.execute(
            history_query + " WHERE ge.group_id=? ORDER BY ge.group_expense_id DESC",
            (session['group_id'],)
        )

    else:

        cursor.execute(
            history_query + " WHERE ge.user_id=? ORDER BY ge.group_expense_id DESC",
            (session['user_id'],)
        )

    expenses = cursor.fetchall()

    # Members List (fetched first so the summary below can use the LIVE
    # member count, not a stale snapshot from whenever an expense was
    # created)
    members = []

    if 'group_id' in session:

        cursor.execute("""
            SELECT users.user_id, users.name
            FROM group_members
            JOIN users
            ON group_members.user_id = users.user_id
            WHERE group_members.group_id=?
        """, (session['group_id'],))

        members = cursor.fetchall()

    total_expense = 0
    total_members = 0
    split_amount = 0

    if expenses:

        total_expense = sum(float(x["amount"]) for x in expenses)

        # Always reflect who is in the group RIGHT NOW - if someone joins
        # after an expense was added, the split shown here must update to
        # include them, same as the actual settlement rows do.
        if 'group_id' in session and members:
            total_members = len(members)
        else:
            total_members = int(expenses[0]["members"] or 0)

        if total_members > 0:
            split_amount = total_expense / total_members

    conn.close()

    return render_template(
        "group_expense.html",
        expenses=expenses,
        total_expense=total_expense,
        total_members=total_members,
        split_amount=split_amount,
        members=members
    )

@app.route('/create_group', methods=['POST'])
def create_group():

    if 'user_id' not in session:
        return redirect('/')

    group_name = request.form['group_name']
    group_code = generate_group_code()

    conn = get_db_connection()
    cursor = conn.cursor()

    # Create Group
    cursor.execute("""
        INSERT INTO groups
        (group_name, created_by, created_at, group_code)
        VALUES (?, ?, datetime('now'), ?)
    """, (
        group_name,
        session['user_id'],
        group_code
    ))

    # Get newly created group id
    group_id = cursor.lastrowid

    # Add creator as first member
    cursor.execute("""
        INSERT INTO group_members (group_id, user_id)
        VALUES (?, ?)
    """, (
        group_id,
        session['user_id']
    ))

    conn.commit()
    conn.close()

    # Without this, the creator's session still points at whatever group
    # (if any) they had open before, so adding an expense right after
    # creating a new group would either fail with "Please join or create
    # a group first!" or - worse - silently get saved against the OLD
    # group. Switch the session straight to the group they just created.
    session['group_id'] = group_id
    session['group_name'] = group_name

    flash(group_code, "group_code")

    return redirect('/group_expense')

    
@app.route('/join_group', methods=['POST'])
def join_group():

    if 'user_id' not in session:
        return redirect('/')

    group_code = request.form['group_code'].strip()

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM groups WHERE UPPER(TRIM(group_code))=UPPER(?)",
        (group_code,)
    )

    group = cursor.fetchone()

    if group:

        # Already joined?
        cursor.execute("""
            SELECT *
            FROM group_members
            WHERE group_id=? AND user_id=?
        """, (
            group["group_id"],
            session["user_id"]
        ))

        already = cursor.fetchone()

        if not already:

            cursor.execute("""
                INSERT INTO group_members (group_id, user_id)
                VALUES (?, ?)
            """, (
                group["group_id"],
                session["user_id"]
            ))

            conn.commit()

            # Re-split every existing expense in this group so the newly
            # joined member is included and everyone's share is updated.
            sync_group_settlements(cursor, group["group_id"])

        session['group_id'] = group['group_id']
        session['group_name'] = group['group_name']

        conn.commit()
        flash("Joined Successfully!")

    else:
        flash("Invalid Group Code!")

    conn.close()
    return redirect('/group_expense')
@app.route('/delete_group_expense/<int:group_expense_id>')
def delete_group_expense(group_expense_id):

    if 'user_id' not in session:
        return redirect('/')

    conn = get_db_connection()
    cursor = conn.cursor()

    # Reverse any reimbursement income this expense's settlements generated
    cursor.execute("""
        DELETE FROM income
        WHERE settlement_id IN (
            SELECT settlement_id FROM settlement WHERE group_expense_id=?
        )
    """, (group_expense_id,))

    # Remove the personal expense entry recorded for whoever paid this
    cursor.execute(
        "DELETE FROM expense WHERE group_expense_id=?",
        (group_expense_id,)
    )

    # Remove the settlement rows created from this expense
    cursor.execute(
        "DELETE FROM settlement WHERE group_expense_id=?",
        (group_expense_id,)
    )

    cursor.execute(
        "DELETE FROM group_expense WHERE group_expense_id=?",
        (group_expense_id,)
    )

    conn.commit()
    conn.close()

    flash("Expense Deleted Successfully!")

    return redirect('/group_expense')


@app.route('/delete_group/<int:group_id>', methods=['POST'])
def delete_group(group_id):

    if 'user_id' not in session:
        return redirect('/')

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM groups WHERE group_id=?",
        (group_id,)
    )

    group = cursor.fetchone()

    if not group:
        flash("Group not found.")
        conn.close()
        return redirect('/my_groups')

    if group['created_by'] != session['user_id']:
        flash("Only the group creator can delete this group.")
        conn.close()
        return redirect('/my_groups')

    # Reverse any reimbursement income generated from this group's settlements
    cursor.execute("""
        DELETE FROM income
        WHERE settlement_id IN (
            SELECT settlement_id FROM settlement WHERE group_id=?
        )
    """, (group_id,))

    # Remove personal expense entries recorded for this group's expenses
    cursor.execute("""
        DELETE FROM expense
        WHERE group_expense_id IN (
            SELECT group_expense_id FROM group_expense WHERE group_id=?
        )
    """, (group_id,))

    cursor.execute("DELETE FROM settlement WHERE group_id=?", (group_id,))
    cursor.execute("DELETE FROM group_expense WHERE group_id=?", (group_id,))
    cursor.execute("DELETE FROM group_members WHERE group_id=?", (group_id,))
    cursor.execute("DELETE FROM groups WHERE group_id=?", (group_id,))

    conn.commit()
    conn.close()

    if session.get('group_id') == group_id:
        session.pop('group_id', None)
        session.pop('group_name', None)

    flash("Group Deleted Successfully!")

    return redirect('/my_groups')


@app.route('/check_group_expense')
def check_group_expense():

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM group_expense")

    data = cursor.fetchall()

    conn.close()

    return str([dict(row) for row in data])

@app.route('/delete_bad_group_expense')
def delete_bad_group_expense():

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM group_expense
        WHERE members=0 OR group_id IS NULL
    """)

    conn.commit()
    conn.close()

    return "Deleted Successfully"

# ---------------- SETTLEMENT ---------------- #

@app.route('/settlement')
def settlement():

    if 'user_id' not in session:
        return redirect('/')

    conn = get_db_connection()
    cursor = conn.cursor()

    # Total amount current user still owes across all groups
    cursor.execute("""
        SELECT SUM(amount) AS total
        FROM settlement
        WHERE payer_id=? AND status='Pending'
    """, (session['user_id'],))

    pending = cursor.fetchone()['total'] or 0

    # All groups the current user belongs to (created or joined),
    # shown as a list - open one to see who owes what in it.
    cursor.execute("""
        SELECT DISTINCT
            g.group_id,
            g.group_name,
            g.group_code
        FROM groups g
        LEFT JOIN group_members gm
            ON g.group_id = gm.group_id
        WHERE g.created_by = ?
           OR gm.user_id = ?
        ORDER BY g.group_id DESC
    """, (
        session['user_id'],
        session['user_id']
    ))

    groups = cursor.fetchall()

    group_summaries = []

    for group in groups:

        cursor.execute("""
            SELECT
                COUNT(*) AS pending_count,
                COALESCE(SUM(amount), 0) AS pending_total
            FROM settlement
            WHERE group_id=? AND status='Pending'
        """, (group['group_id'],))

        summary = cursor.fetchone()

        group_summaries.append({
            'group_id': group['group_id'],
            'group_name': group['group_name'],
            'group_code': group['group_code'],
            'pending_count': summary['pending_count'],
            'pending_total': summary['pending_total']
        })

    conn.close()

    return render_template(
        'settlement.html',
        pending=pending,
        group_summaries=group_summaries
    )


@app.route('/settlement/<int:group_id>')
def group_settlement(group_id):

    if 'user_id' not in session:
        return redirect('/')

    conn = get_db_connection()
    cursor = conn.cursor()

    # Make sure this user actually belongs to the group
    cursor.execute("""
        SELECT g.*
        FROM groups g
        LEFT JOIN group_members gm
            ON g.group_id = gm.group_id AND gm.user_id = ?
        WHERE g.group_id=? AND (g.created_by=? OR gm.user_id=?)
    """, (
        session['user_id'],
        group_id,
        session['user_id'],
        session['user_id']
    ))

    group = cursor.fetchone()

    if not group:
        flash("You don't have access to that group.")
        conn.close()
        return redirect('/settlement')

    # Every settlement row for this group, showing which member has to
    # pay, how much, who receives it, and whether it's paid
    cursor.execute("""
        SELECT
            s.settlement_id,
            s.amount,
            s.status,
            s.payer_id,
            s.receiver_id,
            payer.name AS member_name,
            receiver.name AS receiver_name
        FROM settlement s
        JOIN users payer
            ON s.payer_id = payer.user_id
        JOIN users receiver
            ON s.receiver_id = receiver.user_id
        WHERE s.group_id=?
        ORDER BY s.status ASC, s.settlement_id DESC
    """, (group_id,))

    rows = cursor.fetchall()

    # Every member of the group, so members with nothing pending still show up
    cursor.execute("""
        SELECT users.user_id, users.name
        FROM group_members
        JOIN users ON group_members.user_id = users.user_id
        WHERE group_members.group_id=?
        ORDER BY users.name
    """, (group_id,))

    members = cursor.fetchall()

    conn.close()

    return render_template(
        'group_settlement.html',
        group=group,
        rows=rows,
        members=members,
        current_user_id=session['user_id']
    )


@app.route('/mark_paid/<int:settlement_id>')
def mark_paid(settlement_id):

    if 'user_id' not in session:
        return redirect('/')

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT s.*, ge.expense_name, g.group_name, payer.name AS ower_name
        FROM settlement s
        LEFT JOIN group_expense ge ON s.group_expense_id = ge.group_expense_id
        LEFT JOIN groups g ON s.group_id = g.group_id
        LEFT JOIN users payer ON s.payer_id = payer.user_id
        WHERE s.settlement_id=?
    """, (settlement_id,))

    row = cursor.fetchone()

    # Only the person who is OWED the money (the one who originally paid
    # the shared expense, i.e. the group creator/expense payer) can mark
    # a member's share as paid - they're the one confirming they actually
    # received the cash. Only allowed while it's still Pending (avoids
    # double-crediting).
    if row and row['receiver_id'] == session['user_id'] and row['status'] == 'Pending':

        cursor.execute("""
            UPDATE settlement
            SET status='Paid'
            WHERE settlement_id=?
        """, (settlement_id,))

        # The receiver actually got this money back - credit their income
        group_name = row['group_name'] or "Group"
        expense_name = row['expense_name'] or "shared expense"
        ower_name = row['ower_name'] or "A member"

        cursor.execute("""
            INSERT INTO income
            (user_id, amount, source, date, description, settlement_id)
            VALUES (?, ?, ?, date('now'), ?, ?)
        """, (
            row['receiver_id'],
            row['amount'],
            "Settlement",
            f"{ower_name} settled their share of {expense_name} ({group_name})",
            settlement_id
        ))

        # The ower actually handed over their share of the bill, so it
        # comes out of THEIR dashboard too - record it as a personal
        # expense for them, same way the receiver's side is credited above.
        cursor.execute("""
            INSERT INTO expense
            (user_id, amount, category, date, description, settlement_id)
            VALUES (?, ?, ?, date('now'), ?, ?)
        """, (
            row['payer_id'],
            row['amount'],
            "Settlement",
            f"Paid your share of {expense_name} ({group_name})",
            settlement_id
        ))

        conn.commit()

        flash("Payment Marked as Paid!")

    conn.close()

    if row:
        return redirect(f"/settlement/{row['group_id']}")

    return redirect('/settlement')


@app.route('/mark_unpaid/<int:settlement_id>')
def mark_unpaid(settlement_id):

    if 'user_id' not in session:
        return redirect('/')

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM settlement WHERE settlement_id=?",
        (settlement_id,)
    )
    row = cursor.fetchone()

    # Only the person who is OWED the money can undo a paid mark,
    # and only if it's currently marked Paid
    if row and row['receiver_id'] == session['user_id'] and row['status'] == 'Paid':

        cursor.execute("""
            UPDATE settlement
            SET status='Pending'
            WHERE settlement_id=?
        """, (settlement_id,))

        # Reverse the income credit that was given to the receiver
        cursor.execute(
            "DELETE FROM income WHERE settlement_id=?",
            (settlement_id,)
        )

        # Reverse the personal expense that was recorded on the ower's side
        cursor.execute(
            "DELETE FROM expense WHERE settlement_id=?",
            (settlement_id,)
        )

        conn.commit()

        flash("Payment Marked as Not Paid!")

    conn.close()

    if row:
        return redirect(f"/settlement/{row['group_id']}")

    return redirect('/settlement')


@app.route('/check_group_table')
def check_group_table():

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(group_expense)")
    columns = cursor.fetchall()

    conn.close()

    return "<br>".join([str(dict(col)) for col in columns])


@app.route('/check_groups_table')
def check_groups_table():

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(groups)")
    columns = cursor.fetchall()

    conn.close()

    return "<br>".join([str(dict(col)) for col in columns])


@app.route('/check_settlement')
def check_settlement():

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM settlement")

    data = cursor.fetchall()

    conn.close()

    return str([dict(row) for row in data])

@app.route('/create_notifications_table')
def create_notifications_table():

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS notifications (
        notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        message TEXT,
        created_at TEXT
    )
    """)

    conn.commit()
    conn.close()

    return "Notifications Table Created Successfully!"

@app.route('/clear_settlement')
def clear_settlement():

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM settlement")

    conn.commit()
    conn.close()

    return "Settlement Table Cleared Successfully!"


# ---------------- PROFILE ---------------- #
@app.route('/profile', methods=['GET', 'POST'])
def profile():

    if 'user_id' not in session:
        return redirect('/')

    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':

        name = request.form['name']
        email = request.form['email']
        phone = request.form['phone']

        cursor.execute("""
            UPDATE users
            SET
                name=?,
                email=?,
                phone=?
            WHERE user_id=?
        """, (
            name,
            email,
            phone,
            session['user_id']
        ))

        conn.commit()

    cursor.execute("""
        SELECT *
        FROM users
        WHERE user_id=?
    """, (
        session['user_id'],
    ))

    user = cursor.fetchone()

    conn.close()

    return render_template(
        'profile.html',
        user=user
    )


@app.route('/profile/photo', methods=['POST'])
def upload_profile_photo():

    if 'user_id' not in session:
        return redirect('/')

    photo = request.files.get('photo')

    if not photo or photo.filename.strip() == '':
        flash("Please choose an image first!")
        return redirect('/profile')

    if not allowed_photo_file(photo.filename):
        flash("Only PNG, JPG, JPEG, GIF or WEBP images are allowed!")
        return redirect('/profile')

    conn = get_db_connection()
    cursor = conn.cursor()

    ext = photo.filename.rsplit('.', 1)[1].lower()
    filename = secure_filename(f"user_{session['user_id']}_{uuid.uuid4().hex}.{ext}")

    # Remove the old photo file (if any) so we don't leave orphaned images
    cursor.execute("SELECT photo FROM users WHERE user_id=?", (session['user_id'],))
    old_row = cursor.fetchone()

    if old_row and old_row['photo']:
        old_path = os.path.join(PROFILE_PHOTO_FOLDER, old_row['photo'])
        if os.path.exists(old_path):
            try:
                os.remove(old_path)
            except Exception:
                pass

    photo.save(os.path.join(PROFILE_PHOTO_FOLDER, filename))

    cursor.execute(
        "UPDATE users SET photo=? WHERE user_id=?",
        (filename, session['user_id'])
    )

    conn.commit()
    conn.close()

    flash("Profile Photo Updated!")

    return redirect('/profile')


@app.route('/profile/photo/delete')
def delete_profile_photo():

    if 'user_id' not in session:
        return redirect('/')

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT photo FROM users WHERE user_id=?", (session['user_id'],))
    row = cursor.fetchone()

    if row and row['photo']:
        old_path = os.path.join(PROFILE_PHOTO_FOLDER, row['photo'])
        if os.path.exists(old_path):
            try:
                os.remove(old_path)
            except Exception:
                pass

        cursor.execute(
            "UPDATE users SET photo=NULL WHERE user_id=?",
            (session['user_id'],)
        )
        conn.commit()

        flash("Profile Photo Removed!")

    conn.close()

    return redirect('/profile')

# ---------------- SETTINGS ---------------- #

@app.route('/settings', methods=['GET', 'POST'])
def settings():

    if 'user_id' not in session:
        return redirect('/')

    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':

        current_password = request.form['current_password']
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']

        cursor.execute("""
            SELECT *
            FROM users
            WHERE user_id=?
        """, (session['user_id'],))

        user = cursor.fetchone()

        if user['password'] != current_password:
            flash("Current Password is Incorrect!")
            conn.close()
            return redirect('/settings')

        if new_password != confirm_password:
            flash("New Password and Confirm Password do not match!")
            conn.close()
            return redirect('/settings')

        cursor.execute("""
            UPDATE users
            SET password=?
            WHERE user_id=?
        """, (
            new_password,
            session['user_id']
        ))

        conn.commit()
        flash("Password Updated Successfully!")

    conn.close()

    return render_template('settings.html')

@app.route('/logout')
def logout():

    session.clear()

    flash("Logged out successfully!")

    return redirect('/')

# ---------------- REPORTS ---------------- #

@app.route('/reports')
def reports():

    if 'user_id' not in session:
        return redirect('/')

    month = request.args.get('month', '').strip()

    conn = get_db_connection()
    cursor = conn.cursor()

    if month:

        cursor.execute(
            "SELECT SUM(amount) AS total FROM income WHERE user_id=? AND strftime('%Y-%m', date)=?",
            (session['user_id'], month)
        )
        total_income = cursor.fetchone()['total'] or 0

        cursor.execute(
            "SELECT SUM(amount) AS total FROM expense WHERE user_id=? AND strftime('%Y-%m', date)=?",
            (session['user_id'], month)
        )
        total_expense = cursor.fetchone()['total'] or 0

        cursor.execute("""
            SELECT category,
                   SUM(amount) AS total
            FROM expense
            WHERE user_id=? AND strftime('%Y-%m', date)=?
            GROUP BY category
            ORDER BY total DESC
        """, (session['user_id'], month))

    else:

        cursor.execute(
            "SELECT SUM(amount) AS total FROM income WHERE user_id=?",
            (session['user_id'],)
        )
        total_income = cursor.fetchone()['total'] or 0

        cursor.execute(
            "SELECT SUM(amount) AS total FROM expense WHERE user_id=?",
            (session['user_id'],)
        )
        total_expense = cursor.fetchone()['total'] or 0

        cursor.execute("""
            SELECT category,
                   SUM(amount) AS total
            FROM expense
            WHERE user_id=?
            GROUP BY category
            ORDER BY total DESC
        """, (session['user_id'],))

    categories = cursor.fetchall()

    savings = total_income - total_expense

    conn.close()

    return render_template(
        'reports.html',
        total_income=total_income,
        total_expense=total_expense,
        savings=savings,
        categories=categories,
        selected_month=month
    )
@app.route('/download_report')
def download_report():

    if 'user_id' not in session:
        return redirect('/')

    month = request.args.get('month', '').strip()

    conn = get_db_connection()
    cursor = conn.cursor()

    if month:

        cursor.execute(
            "SELECT SUM(amount) AS total FROM income WHERE user_id=? AND strftime('%Y-%m', date)=?",
            (session['user_id'], month)
        )
        total_income = cursor.fetchone()['total'] or 0

        cursor.execute(
            "SELECT SUM(amount) AS total FROM expense WHERE user_id=? AND strftime('%Y-%m', date)=?",
            (session['user_id'], month)
        )
        total_expense = cursor.fetchone()['total'] or 0

        cursor.execute("""
            SELECT category,
                   SUM(amount) AS total
            FROM expense
            WHERE user_id=? AND strftime('%Y-%m', date)=?
            GROUP BY category
            ORDER BY total DESC
        """, (session['user_id'], month))

    else:

        cursor.execute(
            "SELECT SUM(amount) AS total FROM income WHERE user_id=?",
            (session['user_id'],)
        )
        total_income = cursor.fetchone()['total'] or 0

        cursor.execute(
            "SELECT SUM(amount) AS total FROM expense WHERE user_id=?",
            (session['user_id'],)
        )
        total_expense = cursor.fetchone()['total'] or 0

        cursor.execute("""
            SELECT category,
                   SUM(amount) AS total
            FROM expense
            WHERE user_id=?
            GROUP BY category
            ORDER BY total DESC
        """, (session['user_id'],))

    categories = cursor.fetchall()

    savings = total_income - total_expense

    conn.close()

    buffer = BytesIO()

    doc = SimpleDocTemplate(buffer)

    styles = getSampleStyleSheet()

    elements = []

    elements.append(
        Paragraph("<b>Expense Tracker Report</b>", styles["Title"])
    )

    if month:
        elements.append(
            Paragraph(f"Period : {month}", styles["Normal"])
        )

    elements.append(
        Paragraph(f"Total Income : ₹{total_income}", styles["Normal"])
    )

    elements.append(
        Paragraph(f"Total Expense : ₹{total_expense}", styles["Normal"])
    )

    elements.append(
        Paragraph(f"Total Savings : ₹{savings}", styles["Normal"])
    )

    elements.append(
        Paragraph("Expense Category Report", styles["Heading2"])
    )

    data = [
        ["Category", "Amount"]
    ]

    for row in categories:

        data.append([
            row["category"],
            f"₹{row['total']}"
        ])
    table = Table(data)

    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.purple),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
    ]))

    elements.append(table)

    doc.build(elements)

    pdf = buffer.getvalue()
    buffer.close()

    response = make_response(pdf)

    filename = f"Expense_Report_{month}.pdf" if month else "Expense_Report.pdf"

    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename={filename}'

    return response

    return render_template(
        "report_pdf.html",
        total_income=total_income,
        total_expense=total_expense,
        savings=savings,
        categories=categories
    )


@app.route('/delete_all_groups')
def delete_all_groups():

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM group_members")
    cursor.execute("DELETE FROM group_expense")
    cursor.execute("DELETE FROM groups")

    conn.commit()
    conn.close()

    return "All Groups Deleted Successfully!"

@app.route('/update_settlement_table')
def update_settlement_table():

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            ALTER TABLE settlement
            ADD COLUMN group_id INTEGER
        """)
        conn.commit()
        message = "group_id column added successfully."

    except Exception as e:
        message = str(e)

    conn.close()

    return message

@app.route('/check_users_table')
def check_users_table():

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(users)")
    columns = cursor.fetchall()

    conn.close()

    return "<br>".join([str(dict(col)) for col in columns])


@app.route('/check_users')
def check_users():

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT user_id,name
        FROM users
    """)

    data = cursor.fetchall()

    conn.close()

    return str([dict(x) for x in data])
@app.route('/fix_users')
def fix_users():

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE users
        SET name='Kasthuri'
        WHERE user_id=1
    """)

    cursor.execute("""
        UPDATE users
        SET name='birundha'
        WHERE user_id=3
    """)

    conn.commit()
    conn.close()

    return "Users Updated Successfully!"
# ---------------- RUN APP ---------------- #

if __name__ == "__main__":

    app.run(debug=True, host='0.0.0.0', port=5000)
