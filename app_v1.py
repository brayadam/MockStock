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

connection = sqlite3.connect('database.db', check_same_thread=False)
db = connection.cursor()

@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Expires'] = 0
    response.headers['Pragma'] = 'no-cache'
    return response


# Create a customers table

db.execute("""CREATE TABLE IF NOT EXISTS customers
           (
               user_id INTEGER PRIMARY KEY,
               first_name TEXT NOT NULL,
               last_name TEXT NOT NULL,
               username TEXT NOT NULL,
               password_hash TEXT NOT NULL,
               cash REAL
           )
           """)

# Create a transactions table

db.execute("""CREATE TABLE IF NOT EXISTS transactions
           (
               transaction_id INTEGER PRIMARY KEY,
               symbol TEXT,
               shares REAL,
               price REAL,
               timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
               symbol_balance INTEGER,
               FOREIGN KEY (user_id) REFERENCES customers (user_id)
           )
           """)


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    
    # Get current user id
    user_id = session.get('user_id')

    # Get user's transactions from database
    transactions = db.execute('SELECT symbol, SUM(shares), symbol_balance FROM transactions WHERE user_id = ? GROUP BY symbol HAVING symbol_balance > 0', user_id)

    # If new user and/or no transactions, return apology
    if not transactions:
        return apology('no transactions history', 200)

    # Get user's cash from database
    query_cash = db.execute('SELECT cash FROM customers WHERE user_id = ?', user_id)
    cash = query_cash[0]['cash']

    # Get transaction data
    available_cash = cash
    for transaction in transactions:
        name = lookup(transaction['symbol'])['name']
        price = lookup(transaction['symbol'])['price']
        value = transaction['SUM(shares)'] * price
        transaction.update({'name': name, 'price': usd(price), 'value': usd(value)})
        available_cash += price * transaction['symbol_balance']

    # User reached route via GET (as by clicking a link or via redirect
    return render_template('index.html', transactions=transactions, cash=usd(cash), total_funds=usd(available_cash))


@app.route('/buy', methods=['GET', 'POST'])
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
        else: symbol = request.form.get('symbol')

        # Ensure number of shares is numerical
        shares = request.form.get('shares')
        if not shares.isdigit():
            return apology('number of shares invalid', 400)

        # Ensure number of shares is a positive integer
        shares = request.form.get('shares')
        if float(shares) < 0:
            return apology('number of shares invalid', 400)

        # Look up a stocks current price
        quote = lookup(symbol)

        # Ensure stock symbol is valid
        if not quote:
            return apology('stock not found', 400)

        # If lookup succesfull
        price = quote['price']

        # Lookup how much cash the user has
        cash = db.execute('SELECT cash FROM customers WHERE user_id = ?', session.get('user_id'))

        # Ensure user has enough cash to purchase required shares
        value = float(shares) * float(price)
        if value > cash[0]['cash']:
            return apology('not enough cash')

        # Purchase shares
        db.execute('INSERT INTO transactions (user_id, symbol, shares, price) VALUES (?,?,?,?)', user_id, symbol, shares, price)
        cash = cash[0]['cash'] - value
        db.execute('UPDATE customers SET cash = ? WHERE user_id = ?', cash, user_id)
        shares_balance = db.execute('SELECT symbol_balance FROM transactions WHERE symbol = ? AND user_id = ?', symbol, user_id)
        current_shares_balance = float(shares_balance[0]['symbol_balance']) + float(shares)
        db.execute('UPDATE transactions SET symbol_balance = ? WHERE symbol = ? AND user_id = ?', current_shares_balance, symbol, user_id)

        # If succesfull, get user's transactions from database
        transactions = db.execute('SELECT symbol, SUM(shares), symbol_balance FROM transactions WHERE user_id = ? GROUP BY symbol HAVING symbol_balance > 0', user_id)

        # If no transactions, return apology
        if not transactions:
            return apology('no transactions yet')

        # Get user's cash from database
        query_cash = db.execute('SELECT cash FROM customers WHERE user_id = ?', user_id)
        cash = query_cash[0]['cash']

        # Get transaction data
        available_cash = cash
        for transaction in transactions:
            name = lookup(transaction['symbol'])['name']
            price = lookup(transaction['symbol'])['price']
            value = transaction['SUM(shares)'] * price
            transaction.update({'name': name, 'price': usd(price), 'value': usd(value)})
            available_cash += price * transaction['symbol_balance']

        # User reached route via GET (as by clicking a link or via redirect
        return render_template('index.html', transactions=transactions, cash=usd(cash), total_funds=usd(available_cash))


    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template('buy.html')


@app.route('/history')
@login_required
def history():
    """Show history of transactions"""
    
    # Get current user id
    user_id = session.get('user_id')

    # Query database for historical transactions
    transactions = db.execute('SELECT symbol, shares, price, timestamp FROM transactions WHERE user_id = ?', user_id)

    # User reached route via GET (as by clicking a link or via redirect
    return render_template('history.html', transactions=transactions)



@app.route('/login', methods=['GET', 'POST'])
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
            return apology('must provide password', 400)

        # Query database for username
        rows = db.execute('SELECT * FROM customers WHERE username = ?', request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]['hash'], request.form.get("password")):
            return apology('invalid username and/or password', 400)

        # Remember which user has logged in
        session['user_id'] = rows[0]['user_id']
        return redirect('/', 200)

        # Redirect user to buy page

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


@app.route('/quote', methods=['GET', 'POST'])
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


@app.route("/deposit", methods=["GET", "POST"])
@login_required
def deposit():
    """Deposit funds."""
    
    # Get current user id
    user_id = session.get('user_id')

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure all input fields are not blank
        if not request.form.get("cardholder_name"):
            return apology("must provide cardholder name", 403)

        if not request.form.get("card_number"):
            return apology("must provide card number", 403)

        if not request.form.get("expiry_date"):
            return apology("must provide expiry date", 403)

        if not request.form.get("cvc"):
            return apology("must provide cvc", 403)

        if not request.form.get("zip_code"):
            return apology("must provide zip code", 403)

        if not request.form.get("deposit_amount"):
            return apology("must provide deposit amount", 403)

        # Ensure deposit amount is a positive integer
        if float(request.form.get("deposit_amount")) < 100:
            return apology("deposit amount must be over $100")

        # If successfull deposit, update user funds
        query_cash = db.execute("SELECT cash FROM customers WHERE user_id = ?", user_id)
        current_cash = float(query_cash[0]["cash"])
        new_deposit = float(request.form.get("deposit_amount"))
        updated_balance = current_cash + new_deposit
        db.execute("UPDATE customers SET cash = ? WHERE user_id = ?", updated_balance, user_id)
        return render_template("buy.html")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("deposit.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Query database for username
        rows = db.execute("SELECT username FROM customers WHERE username = ?", [request.form.get("username")])

        # Ensure username is not already taken
        if len(rows) != 0:
            return apology("username already taken", 400)

        # Ensure password field is not left blank
        if not request.form.get("password"):
            return apology("password field cannot be left blank", 400)

        # Ensure password and confirmation match
        if request.form.get("password") != request.form.get("confirmation"):
            return apology("password and confirmation do not match")

        # Insert new users login credentials into database
        db.execute("INSERT INTO customers (username, password_hash) VALUES(?, ?)", request.form.get("username"), generate_password_hash(request.form.get("password")))

        # Confirm registration
        return redirect("buy.html", 200)

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")



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
        else: symbol = request.form.get("symbol")

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
        value = float(shares) * float(price)

        # Lookup how many units of stock the user has
        query_shares = db.execute("SELECT SUM(shares) FROM transactions WHERE user_id = ? AND symbol = ?", user_id, symbol)

        # Ensure user has enough units of stock to sell
        if float(shares) > float(query_shares[0]["SUM(shares)"]):
            return apology("not enough stock")

        # Lookup how much cash the user has
        query_cash = db.execute("SELECT cash FROM users WHERE user_id = ?", user_id)

        # Sell shares
        negative_shares = 0 - float(shares)
        cash = query_cash[0]["cash"] + value
        db.execute("UPDATE customers SET cash = ? WHERE user_id = ?", cash, user_id)
        db.execute("INSERT INTO transactions (user_id, symbol, shares, price) VALUES (?,?,?,?)", user_id, symbol, negative_shares, price)
        symbol_balance = db.execute("SELECT symbol_balance FROM transactions WHERE symbol = ? AND user_id = ?", symbol, user_id)
        new_symbol_balance = float(symbol_balance[0]["symbol_balance"]) + float(negative_shares)
        db.execute("UPDATE transactions SET symbol_balance = ? WHERE symbol = ? AND user_id = ?", new_symbol_balance, symbol, user_id)

        # If succesfull, get user's transactions from database
        transactions = db.execute("SELECT symbol, SUM(shares), symbol_balance FROM transactions WHERE user_id = ? GROUP BY symbol HAVING symbol_balance > 0", user_id)

        # If new user and/or no transactions, return apology
        if not transactions:
            return apology("no transactions recorded")

        # Get user's cash from database
        query_cash = db.execute("SELECT cash FROM customers WHERE user_id = ?", user_id)
        cash = query_cash[0]["cash"]

        # Get transaction data
        available_cash = cash
        for transaction in transactions:
            name = lookup(transaction["symbol"])["name"]
            price = lookup(transaction["symbol"])["price"]
            value = transaction["SUM(shares)"] * price
            transaction.update({"name": name, "price": usd(price), "value": usd(value)})
            available_cash += price * transaction["current_shares_balance"]

        # User reached route via GET (as by clicking a link or via redirect
        return render_template("index.html", transactions=transactions, cash=usd(cash), total_funds=usd(available_cash))

    # User reached route via GET (as by clicking a link or via redirect)
    else:

        # Lookup how many units of stock the user has
        transactions = db.execute("SELECT DISTINCT symbol FROM transactions WHERE user_id = ?", user_id)

        return render_template("sell.html", transactions=transactions)