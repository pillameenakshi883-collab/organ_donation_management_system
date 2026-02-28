import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash

# Optional Twilio SMS (disabled by default)
try:
    from twilio.rest import Client
    TWILIO_ENABLED = True
except ImportError:
    TWILIO_ENABLED = False

app = Flask(__name__)
# 🔹 Fixed secret key to persist session
app.secret_key = "some_fixed_secret_key"

DATABASE = "organ.db"

# ------------------ DATABASE ------------------
def init_db():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE,
                    password TEXT,
                    role TEXT,
                    age INTEGER,
                    blood_group TEXT,
                    phone TEXT,
                    organ TEXT
                )''')
    conn.commit()
    conn.close()

init_db()

# ------------------ HOME ------------------
@app.route("/")
def home():
    return render_template("home.html")

# ------------------ REGISTER + DETAILS (Single Step) ------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        confirm = request.form["confirm_password"]
        role = request.form["role"]
        age = request.form["age"]
        blood_group = request.form["blood_group"]
        phone = request.form["phone"]
        organ = request.form["organ"]

        if password != confirm:
            return render_template("register.html", error="Passwords do not match")

        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        try:
            c.execute("""INSERT INTO users 
                         (username,password,role,age,blood_group,phone,organ)
                         VALUES (?,?,?,?,?,?,?)""",
                      (username,
                       generate_password_hash(password),
                       role,
                       age,
                       blood_group,
                       phone,
                       organ))
            conn.commit()
            user_id = c.lastrowid
        except sqlite3.IntegrityError:
            conn.close()
            return render_template("register.html", error="Username already exists!")
        conn.close()

        # Auto login after registration
        session["user_id"] = user_id
        return redirect(url_for("matches"))

    return render_template("register.html")

# ------------------ LOGIN ------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username=?", (username,))
        user = c.fetchone()
        conn.close()

        if not user:
            return redirect(url_for("register"))

        if check_password_hash(user[2], password):
            session["user_id"] = user[0]
            return redirect(url_for("matches"))

        return render_template("login.html", error="Invalid Password")

    return render_template("login.html")

# ------------------ MATCHES ------------------
@app.route("/matches")
def matches():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    # Current logged-in user
    c.execute("SELECT * FROM users WHERE id=?", (session["user_id"],))
    current_user = c.fetchone()

    # Find matching users
    needed_role = "Recipient" if current_user[3] == "Donor" else "Donor"
    c.execute("""SELECT * FROM users 
                 WHERE organ=? AND blood_group=? 
                 AND role=? AND id!=?""",
              (current_user[7], current_user[5], needed_role, current_user[0]))
    matches_list = c.fetchall()
    conn.close()

    # Optional Twilio SMS Notification
    if TWILIO_ENABLED and matches_list:
        account_sid = os.environ.get("TWILIO_SID")
        auth_token = os.environ.get("TWILIO_TOKEN")
        twilio_number = os.environ.get("TWILIO_NUMBER")
        if account_sid and auth_token and twilio_number:
            client = Client(account_sid, auth_token)
            for m in matches_list:
                try:
                    client.messages.create(
                        body=f"Match found for {m[7]} donation!",
                        from_=twilio_number,
                        to=m[6]
                    )
                except:
                    pass

    return render_template("matches.html", matches=matches_list, user=current_user)

# ------------------ LOGOUT ------------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

# ------------------ RUN ------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)