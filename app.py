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
               symbol TEXT NOT NULL,
               shares REAL NOT NULL,
               price REAL NOT NULL,
               timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
               symbol_balance INTEGER NOT NULL,
               user_id INTEGER NOT NULL,
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
        c.execute("""INSERT INTO users (username, password_hash, cash) VALUES (?,?,10000)""", 
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
    
    
@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    
    # Get current user id
    user_id = session.get('user_id')

    # User reached route via POST (as by submitting a form via POST)
    if request.method == 'POST':

        # Ensure stock symbol was submitted
        if not request.form.get('symbol'):
            return apology('no stock entered', 403)
        else:
            symbol = request.form.get('symbol')

        # Ensure number of shares is an integer or float
        shares = request.form.get('shares')
        if not shares.isdigit():
            return apology('number of shares must be numerical', 400)

        # Ensure number of shares is a positive integer
        if float(shares) < 0:
            return apology('number of shares invalid', 400)

        # Ensure stock symbol is valid and look up stocks current price
        quote = lookup(symbol)
        if not quote:
            return apology('stock not found', 400)

        # If lookup succesfull
        price = quote['price']

        # Lookup how much cash the user has
        c.execute("SELECT cash FROM users WHERE user_id = ?", [user_id])
        cash = c.fetchall()

        # Ensure user has enough cash to purchase required shares
        value = float(shares) * float(price)
        if value > cash[0][0]:
            return apology('not enough cash')

        # Purchase shares
        cash = cash[0][0] - value
        c.execute("UPDATE users SET cash = ? WHERE user_id = ?", (cash, user_id))
        conn.commit()
        c.execute("SELECT symbol_balance FROM transactions WHERE symbol = ? AND user_id = ?", (symbol, user_id))
        symbol_balance = c.fetchone()
        if not symbol_balance:
            symbol_balance = 0
            new_symbol_balance = float(symbol_balance) + float(shares)
        else:
            symbol_balance = symbol_balance
            new_symbol_balance = float(symbol_balance[0]) + float(shares)
        c.execute("INSERT INTO transactions (user_id, symbol, shares, price, symbol_balance) VALUES (?,?,?,?,?)", 
                  (user_id, symbol, shares, price, new_symbol_balance))
        conn.commit()

        # # If succesfull, get user's transactions from database
        # c.execute("""SELECT * WHERE user_id = ? GROUP BY symbol HAVING symbol_balance > 0""", (user_id))
        # transactions = c.fetchall()
        # return jsonify(transactions)

        # # If no transactions, return apology
        # if not transactions:
        #     return apology('no transactions yet')

        # # Get user's cash from database
        # c.execute("SELECT cash FROM customers WHERE user_id = ?", user_id)
        # cash = c.fetchall()

        # # Get transaction data
        # portfolio_balance = cash
        # for transaction in transactions:
        #     name = lookup(transaction['symbol'])['name']
        #     price = lookup(transaction['symbol'])['price']
        #     value = transaction['SUM(shares)'] * price
        #     transaction.update({'name': name, 'price': usd(price), 'value': usd(value)})
        #     portfolio_balance += price * transaction['symbol_balance']

        # User reached route via GET (as by clicking a link or via redirect
        return render_template('index.html')#, transactions=transactions, cash=usd(cash), total_funds=usd(portfolio_balance))


    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template('buy.html')
    
    
@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    
    # Get current user id
    user_id = session.get('user_id')
    
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure stock symbol was submitted
        if not request.form.get("symbol"):
            return apology("must provide stock symbol", 403)
        else:
            symbol = request.form.get("symbol")

        # Ensure number of shares is a positive integer
        shares = request.form.get("shares")
        if float(shares) < 0:
            return apology("number of shares invalid")

        # Look up a stocks current price
        quote = lookup(symbol)

        # Ensure stock symbol is valid
        if not quote:
            return apology("stock not found")

        # If lookup succesfull
        price = quote["price"]

        # Value of sale
        sale_value = float(shares) * float(price)

        # Lookup how many units of stock the user has
        c.execute("SELECT symbol_balance FROM transactions WHERE user_id = ? AND symbol = ?", (user_id, symbol))
        symbol_balance = c.fetchone()

        # Ensure user has enough units of stock to sell
        if float(shares) > float(symbol_balance[0]):
            return apology("not enough stock")

        # Lookup how much cash the user has
        c.execute("SELECT cash FROM users WHERE user_id = ?", (user_id))
        cash = conn.commit()

        # Sell shares
        
        # This variable is to be used in the transaction ledger. It turns a positive integer into a negative integer.
        # Example: Selling 1 share would create a -1 entry in the transaction ledger.
        ledger_shares = 0 - float(shares)
        
        cash = cash[0] + sale_value
        c.execute("UPDATE customers SET cash = ? WHERE user_id = ?", (cash, user_id))
        conn.commit()
        symbol_balance = float(symbol_balance) - float(shares)
        c.execute("UPDATE transactions SET symbol_balance = ? WHERE symbol = ? AND user_id = ?", (symbol_balance, symbol, user_id))
        conn.commit()
        c.execute("INSERT INTO transactions (user_id, symbol, shares, price) VALUES (?,?,?,?)", (user_id, symbol, ledger_shares, price))
        conn.commit()
        
        # # If succesfull, get user's transactions from database
        # transactions = db.execute("SELECT symbol, SUM(shares), symbol_balance FROM transactions WHERE user_id = ? GROUP BY symbol HAVING symbol_balance > 0", user_id)

        # # If new user and/or no transactions, return apology
        # if not transactions:
        #     return apology("no transactions recorded")

        # # Get user's cash from database
        # query_cash = db.execute("SELECT cash FROM customers WHERE user_id = ?", user_id)
        # cash = query_cash[0]["cash"]

        # # Get transaction data
        # available_cash = cash
        # for transaction in transactions:
        #     name = lookup(transaction["symbol"])["name"]
        #     price = lookup(transaction["symbol"])["price"]
        #     value = transaction["SUM(shares)"] * price
        #     transaction.update({"name": name, "price": usd(price), "value": usd(value)})
        #     available_cash += price * transaction["current_shares_balance"]

        # User reached route via GET (as by clicking a link or via redirect
        return render_template("index.html")#, transactions=transactions, cash=usd(cash), total_funds=usd(available_cash))

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        # Lookup how many units of stock the user has
        c.execute("SELECT DISTINCT symbol FROM transactions WHERE user_id = ?", [user_id])
        transactions = c.fetchall()
        return render_template("sell.html", transactions=transactions)