from flask import Flask, render_template, request, redirect, session, flash
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.security import check_password_hash
import MySQLdb.cursors
import config
import random
# ---------------- ACCOUNT NUMBER GENERATOR ----------------
def generate_account_number():
    return str(random.randint(1000000000, 9999999999))  # 10 digits

app = Flask(__name__)
app.secret_key = config.SECRET_KEY

# MySQL Configuration
app.config['MYSQL_HOST'] = config.MYSQL_HOST
app.config['MYSQL_USER'] = config.MYSQL_USER
app.config['MYSQL_PASSWORD'] = config.MYSQL_PASSWORD
app.config['MYSQL_DB'] = config.MYSQL_DB
app.config['MYSQL_CURSORCLASS'] = config.MYSQL_CURSORCLASS

mysql = MySQL(app)

# ---------------- HOME ----------------
@app.route("/")
def home():
    return redirect("/login")

# ---------------- REGISTER ----------------
@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":
        username = request.form["username"]
        email = request.form["email"]
        password = generate_password_hash(request.form["password"])

        cursor = mysql.connection.cursor()
        cursor.execute(
            "INSERT INTO users (username, email, password) VALUES (%s, %s, %s)",
            (username, email, password),
        )
        mysql.connection.commit()

        account_number = generate_account_number()

        cursor.execute("""
            INSERT INTO accounts (user_id, balance, account_number)
            VALUES (LAST_INSERT_ID(), 0, %s)
        """, (account_number,))
        mysql.connection.commit()

        flash("Account created. Please login.", "success")
        return redirect("/login")

    return render_template("register.html")


# ---------------- LOGIN ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        pass
        password = request.form["password"]

        cursor = mysql.connection.cursor()
        cursor.execute("SELECT * FROM users WHERE username=%s", (username,))
        user = cursor.fetchone()

        if user and check_password_hash(user['password'], password):
            session["user_id"] = user["id"]
            return redirect("/dashboard")

        flash("Invalid username or password", "danger")

    return render_template("login.html")

# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect("/login")

    cursor = mysql.connection.cursor()
    cursor.execute("SELECT * FROM accounts WHERE user_id=%s", (session['user_id'],))
    account = cursor.fetchone()

    return render_template("dashboard.html", account=account)


# ---------------- WITHDRAW MONEY ----------------
@app.route("/withdraw", methods=["GET", "POST"])
def withdraw():
    if "user_id" not in session:
        return redirect("/login")

    cursor = mysql.connection.cursor()

    if request.method == "POST":
        amount = float(request.form["amount"])

        # Validate positive amount
        if amount <= 0:
            flash("Amount must be greater than 0!", "danger")
            return redirect("/withdraw")

        # Check user balance
        cursor.execute("SELECT balance FROM accounts WHERE user_id=%s", (session["user_id"],))
        user_balance = cursor.fetchone()['balance']

        if user_balance < amount:
            flash("Insufficient balance!", "danger")
            return redirect("/withdraw")

        # Deduct from user's balance
        cursor.execute("UPDATE accounts SET balance = balance - %s WHERE user_id=%s",
                       (amount, session["user_id"]))

        # Record withdrawal in transactions
        cursor.execute("""
            INSERT INTO transactions (sender_id, receiver_id, amount)
            VALUES (%s, NULL, %s)
        """, (session['user_id'], amount))

        mysql.connection.commit()
        flash(f"You successfully withdrew ${amount}.", "success")
        return redirect("/dashboard")

    return render_template("withdraw.html")




# ---------------- TRANSFER MONEY ----------------
@app.route("/transfer", methods=["GET", "POST"])
def transfer():
    if "user_id" not in session:
        return redirect("/login")

    cursor = mysql.connection.cursor()

    if request.method == "POST":
        receiver = request.form["receiver_id"]
        amount = float(request.form["amount"])

        # Check positive amount
        if amount <= 0:
            flash("Amount must be greater than 0!", "danger")
            return redirect("/transfer")

        # Check sender balance
        cursor.execute("SELECT balance FROM accounts WHERE user_id=%s", (session["user_id"],))
        sender_balance = cursor.fetchone()['balance']
        if sender_balance < amount:
            flash("Insufficient funds!", "danger")
            return redirect("/transfer")

        # Check if receiver exists
        cursor.execute("SELECT * FROM accounts WHERE user_id=%s", (receiver,))
        receiver_account = cursor.fetchone()
        if not receiver_account:
            flash("Receiver does not exist!", "danger")
            return redirect("/transfer")

        # Deduct from sender
        cursor.execute("UPDATE accounts SET balance = balance - %s WHERE user_id=%s",
                       (amount, session["user_id"]))

        # Add to receiver
        cursor.execute("UPDATE accounts SET balance = balance + %s WHERE user_id=%s",
                       (amount, receiver))

        # Record transaction
        cursor.execute("""
                    INSERT INTO transactions (sender_id, receiver_id, amount)
                    VALUES (%s, %s, %s)
                """, (session['user_id'], receiver, amount))

        mysql.connection.commit()
        flash(f"${amount} transferred successfully!", "success")
        return redirect("/dashboard")

    return render_template("transfer.html")

# ---------------- VIEW TRANSACTIONS ----------------
@app.route("/transactions")
def transactions():
    if "user_id" not in session:
        return redirect("/login")

    cursor = mysql.connection.cursor()
    cursor.execute("""
        SELECT * FROM transactions 
        WHERE sender_id=%s OR receiver_id=%s 
        ORDER BY timestamp DESC
    """, (session["user_id"], session["user_id"]))

    tx = cursor.fetchall()
    return render_template("transactions.html", tx=tx)

# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

@app.route("/add_funds/<int:amount>")
def add_funds(amount):
    if "user_id" not in session:
        return redirect("/login")
    cursor = mysql.connection.cursor()
    cursor.execute("UPDATE accounts SET balance = balance + %s WHERE user_id=%s", (amount, session["user_id"]))
    mysql.connection.commit()
    flash(f"${amount} added to your account.", "success")
    return redirect("/dashboard")


# ---------------- RUN APP ----------------
if __name__ == "__main__":
    app.run(debug=True)
