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

# Create a users table
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
c.execute("""CREATE TABLE IF NOT EXISTS transactions
           (
               transaction_id INTEGER PRIMARY KEY,
               symbol TEXT,
               shares REAL,
               price REAL,
               timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
               symbol_balance INTEGER,
               user_id INTEGER,
               FOREIGN KEY (user_id) REFERENCES users (user_id)
           )
           """)
conn.commit()


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
    return render_template('index.html')
                           
                           
@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

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

    
@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == 'POST':

        # Ensure username was submitted
        if not request.form.get('username'):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get('password'):
            return apology("must provide password", 400)

        # Query database for username
        c.execute("SELECT * FROM users WHERE username = ?", [request.form.get('username')])
        data = c.fetchall()

        # Ensure username exists and password is correct
        if len(data) != 1 or not check_password_hash(data[0][2], request.form.get('password')):
            return apology("invalid username and/or password", 400)

        # Remember which user has logged in
        session['user_id'] = data[0][0]

        # Redirect user to index page
        return redirect('/', 200)

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template('login.html')
    
    
@app.route('/logout')
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect('/')


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == 'POST':

        # Ensure quote field is not blank
        if not request.form.get('symbol'):
            return apology('must enter a stock symbol')

        # Lookup stock symbol and get quote
        quote = lookup(request.form.get('symbol'))

        # Ensure stock symbol is valid
        if not quote:
            return apology('stock not found')

        # If lookup succesfull
        name = quote['name']
        symbol = quote['symbol']
        price = quote['price']
        return render_template('quoted.html', name=name, price=usd(price), symbol=symbol)

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template('quote.html')