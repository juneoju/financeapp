import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    rows = db.execute("SELECT * from portfolios WHERE id = :id", id = session["user_id"])
    
    portfolio_total = 0 
    
    for row in rows: 
        row["name"] = lookup(row["symbol"])['name']
        row["price"] = usd(lookup(row["symbol"])['price'])
        row["total"] = lookup(row["symbol"])['price'] * int(row["shares_num"])
        portfolio_total += row["total"]
        row["total"] = usd(row["total"])
    
    cash = db.execute("SELECT cash from users WHERE id=:id", id = session["user_id"])
    cash = float(cash[0]['cash'])
    portfolio_total = portfolio_total + cash
    portfolio_total = usd(portfolio_total)
    cash = usd(cash)
    
    return render_template("index.html", portfolio_total = portfolio_total, cash = cash, rows = rows )


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "GET":
        return render_template("buy.html")
    else: 
        symbol = request.form.get("symbol")
        if not symbol: 
            return render_template("apology.html", message = "The symbol you provided does not exist. Please double check and try again")
        shares = int(request.form.get("shares"))
        if (int(shares) < 1): 
            return render_template("apology.html", message = "You have not entered a valid number of shares, try again")
        
        stock_info = lookup(symbol)
        stock_price = float(stock_info['price'])
        symbol = stock_info['symbol']
        transaction_cost = stock_price * int(shares)
        
        user_cashInfo = db.execute("SELECT cash FROM users where id = :id", id = session["user_id"])
        cash_balance = float(user_cashInfo[0]['cash'])
        
        if(cash_balance > transaction_cost):
            cash = cash_balance - transaction_cost
            db.execute("UPDATE users SET cash = :cash WHERE id = :id",cash=cash, id=session["user_id"])
            db.execute("INSERT into purchases (id, symbol, stock_price, shares_num) VALUES (:id, :symbol, :stock_price, :shares_num)", id = session["user_id"], symbol= symbol,  stock_price = stock_price, shares_num = shares)
            
            symbol_check = db.execute("SELECT symbol from portfolios WHERE symbol = :symbol AND id = :id", symbol = symbol, id=session["user_id"])
            if symbol_check:
                existing_shares = db.execute("SELECT shares_num from portfolios WHERE symbol = :symbol AND id = :id", symbol = symbol, id=session["user_id"])
                existing_shares = int(existing_shares[0]['shares_num'])
                shares_num = existing_shares + shares
                db.execute("UPDATE portfolios SET shares_num = :shares_num WHERE symbol = :symbol AND id = :id ", symbol = symbol, id=session["user_id"], shares_num = shares_num)
                
            else: 
                db.execute("INSERT into portfolios (id, symbol, shares_num) VALUES (:id, :symbol, :shares_num)", id =session["user_id"], symbol = symbol, shares_num = shares)
            
        else:
            return render_template("apology.html", message  = "Sorry, you do not have enough cash to complete this purchase.")
    return redirect("/")
     

        
        


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    
    
    rows = db.execute("SELECT * from purchases WHERE id = :id", id = session["user_id"])
    for row in rows: 
        row['stock_price'] = usd(row["stock_price"])
    
    return render_template("history.html", rows = rows)
    
    


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "GET":
        return render_template("quote.html")
        
    else:
        symbol = request.form.get("symbol")
        symbol_info = lookup(symbol)
        symbol_name = symbol_info['name']
        symbol_symbol = symbol_info['symbol']
        symbol_price = usd(symbol_info['price'])
        return render_template("quoted.html", symbol_name = symbol_name, symbol_symbol= symbol_symbol, symbol_price = symbol_price )



@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")
    else: 
        username = request.form.get("username")
        if not username: 
            return render_template("apology.html", message = "Error: you must provide a username.")
        
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")
        
        if not password: 
            return render_template("apology.html", message = "Error: you must provide a password.")
            
        if not confirmation: 
            return render_template("apology.html", message = "Error: you must provide a confirmation.")
        hash = generate_password_hash(password, method = 'pbkdf2:sha256', salt_length=8)
        
        if password != confirmation: 
            return render_template("apology.html", message = "Error: your paswords do not match")
        
        hash = generate_password_hash(password, method = 'pbkdf2:sha256', salt_length=8)
        db.execute("INSERT INTO users (username, hash) VALUES (:username, :hash)", username = username, hash = hash)
        return redirect("/")
        


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "GET":
        rows = db.execute("SELECT symbol from portfolios WHERE id = :id", id = session["user_id"])
        return render_template("sell.html", rows = rows)
    else:    
        
        symbol = request.form.get("symbol")
        if not symbol: 
            return render_template("apology.html", message = "Error: the symbol you provided does not exist. Please double check and try again")
        shares = int(request.form.get("shares"))
        
        available_shares = db.execute("SELECT shares_num from portfolios WHERE id = :id AND symbol = :symbol", id = session["user_id"], symbol = symbol)
        available_shares = int(available_shares[0]["shares_num"])
        
        if (int(shares) < 1 or available_shares < shares): 
            return render_template("apology.html", message = "Error: you have not entered a valid number of shares, try again.")
        
        shares_num = available_shares - int(shares)
        
        if shares_num >0: 
            db.execute("UPDATE portfolios SET shares_num = :shares_num WHERE symbol = :symbol AND id = :id ", symbol = symbol, id=session["user_id"], shares_num = shares_num)
        else: 
            db.execute("DELETE from portfolios WHERE symbol= :symbol AND id = :id", symbol = symbol, id=session["user_id"])
        
        stock_info = lookup(symbol)
        stock_price = float(stock_info['price'])
        transaction_cost = stock_price * int(shares)
        
        user_cashInfo = db.execute("SELECT cash FROM users where id = :id", id = session["user_id"])
        cash_balance = float(user_cashInfo[0]['cash'])
        cash = cash_balance + transaction_cost
        db.execute("UPDATE users SET cash = :cash WHERE id = :id",cash=cash, id=session["user_id"])
        shares *= -1
        
        db.execute("INSERT into purchases (id, symbol, stock_price, shares_num) VALUES (:id, :symbol, :stock_price, :shares_num)", id = session["user_id"], symbol= symbol,  stock_price = stock_price, shares_num = shares)
            
        return redirect ("/")
        
@app.route("/password", methods=["GET", "POST"])
@login_required
def password():
    if request.method == "GET":
        return render_template("password.html")
    else: 
        original = request.form.get("original")
        if not original: 
            return render_template("apology.html", message = "Error: please provide the original password.")
        
        original_check = db.execute("SELECT hash from users WHERE id = :id", id = session["user_id"])
        original_check = original_check[0]['hash']
      
        if check_password_hash(original_check, original) == 'False': 
            return render_template("apology.html", message = "Error: you entered the incorrect original password. Try again.")

        password = request.form.get("password")
        confirmation = request.form.get("confirmation")
        
        if not password: 
            return render_template("apology.html", message = "Error: you must provide a password.")
            
        if not confirmation: 
            return render_template("apology.html", message = "Error: you must provide a confirmation.")

        if password != confirmation: 
            return render_template("apology.html", message = "Error: your paswords do not match.")
        
        else: 
            hash = generate_password_hash(password, method = 'pbkdf2:sha256', salt_length=8)
            db.execute("UPDATE users SET hash = :hash WHERE id = :id ", id=session["user_id"], hash = hash)

        return redirect("/login")
        


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
