import os
import sqlite3
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from flask import jsonify
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd


# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config['TEMPLATES_AUTO_RELOAD'] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

# Connect to database and create a cursor
conn = sqlite3.connect('finance.db', check_same_thread=False)
c = conn.cursor()

# Create a customers table
c.execute("""CREATE TABLE IF NOT EXISTS users
           (
               user_id INTEGER PRIMARY KEY,
               username TEXT NOT NULL,
               password_hash TEXT NOT NULL,
               cash REAL
           )
           """)
conn.commit()

# Create a transactions table
# c.execute("""CREATE TABLE IF NOT EXISTS transactions
#            (
#                transaction_id INTEGER PRIMARY KEY,
#                symbol TEXT,
#                shares REAL,
#                price REAL,
#                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
#                symbol_balance INTEGER,
#                FOREIGN KEY (user_id) REFERENCES customers (user_id)
#            )
#            """)
# conn.commit()


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Expires'] = 0
    response.headers['Pragma'] = 'no-cache'
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    
    # User reached route via GET (as by clicking a link or via redirect
    return render_template('register.html')
                           
                           
@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == 'POST':

        # Ensure username was submitted
        if not request.form.get('username'):
            return apology("must provide username", 400)

        # Query database for username
        c.execute("SELECT * FROM users WHERE username = ?", [request.form.get('username')])
        data = c.fetchall()
        
        # Ensure username is not already taken
        if len(data) != 0:
             return apology('username already taken', 400)

        # Ensure password field is not left blank
        if not request.form.get('password'):
            return apology("password field cannot be left blank", 400)

        # Ensure password and confirmation match
        if request.form.get('password') != request.form.get('confirmation'):
            return apology('password and confirmation do not match')

        # Insert new users login credentials into database
        c.execute("""INSERT INTO users (username, password_hash, cash) VALUES(?,?,10000)""", 
                   (request.form.get('username'), generate_password_hash(request.form.get('password'))))
        conn.commit()
        
        # Confirm registration
        return redirect('index.html', 200)

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template('register.html')