from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session
from passlib.apps import custom_app_context as pwd_context
from tempfile import mkdtemp
from helpers import *

import datetime
import time
import hashlib

# configure application
app = Flask(__name__)

# ensure responses aren't cached
if app.config["DEBUG"]:
    @app.after_request
    def after_request(response):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Expires"] = 0
        response.headers["Pragma"] = "no-cache"
        return response

# custom filter
app.jinja_env.filters["usd"] = usd

# configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

@app.route("/")
@login_required
def index():
    portfolio_symbols = db.execute("SELECT amount, symbol \
                                    FROM portfolio WHERE name = :name", \
                                    name=session["user_id"])
    
    # create a temporary variable to store TOTAL worth ( cash + share)
    total_cash = 0
    
    # update each symbol prices and total
    for portfolio_symbol in portfolio_symbols:
        symbol = portfolio_symbol["symbol"]
        shares = portfolio_symbol["amount"]
        stock = lookup(symbol)
        total = float(shares) * stock["price"]
        total_cash += total
        db.execute("UPDATE portfolio SET price=:price, \
                    total=:total WHERE name=:name AND symbol=:symbol", \
                    price=usd(stock["price"]), \
                    total=usd(total), name=session["user_id"], symbol=symbol)
    
    # # update user's cash in portfolio
    updated_cash = db.execute("SELECT cash FROM users \
                               WHERE id=:id", id=session["user_id"])

    # update total cash -> cash + shares worth
    total_cash += float(updated_cash[0]["cash"])
    
    # print portfolio in index homepage
    updated_portfolio = db.execute("SELECT * from portfolio \
                                    WHERE name=:name", name=session["user_id"])

#    symbol = updated_portfolio["symbol"])
#    price = lookup(request.form.get(updated_portfolio[3]["symbol"]))
    
    return render_template("index.html", stocks=updated_portfolio, \
                            cash=usd(updated_cash[0]["cash"]), \
                            total= usd(total_cash) )

#    return render_template("index.html")
#    return apology("TODO")

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock."""
    if request.method == "GET":
        return render_template("buy.html")
    else:
        # ensure proper symbol
        stock = lookup(request.form.get("symbol"))
        if not stock:
            return apology("Invalid Symbol")
        
        # ensure proper number of shares
        try:
            shares = int(request.form.get("shares"))
            if shares < 0:
                return apology("Shares must be positive integer")
        except:
            return apology("Shares must be positive integer")
        
        # select user's cash
        money = db.execute("SELECT cash FROM users WHERE id = :id", \
                            id=session["user_id"])
        
        # check if enough money to buy
        if not money or float(money[0]["cash"]) < stock["price"] * shares:
            return apology("Not enough money")
        now = datetime.datetime.now()
        # update history
        db.execute("INSERT INTO buy (symbol, amount, price, name, hist) \
                    VALUES(:symbol, :amount, :price, :name, :hist)", \
                    symbol=stock["symbol"], amount=shares, \
                    price=usd(stock["price"]), name=session["user_id"], hist=str(now))
                       
        # update user cash               
        db.execute("UPDATE users SET cash = cash - :purchase WHERE id = :id", \
                    id=session["user_id"], \
                    purchase=stock["price"] * float(shares))
        
                        
        # Select user shares of that symbol
        user_shares = db.execute("SELECT amount FROM portfolio \
                           WHERE name = :name AND symbol=:symbol", \
                           name=session["user_id"], symbol=stock["symbol"])
                           
        # if user doesn't has shares of that symbol, create new stock object
        if not user_shares:
            db.execute("INSERT INTO portfolio (name, amount, symbol) \
                        VALUES(:name, :amount, :symbol)", \
                        name=session["user_id"], amount=shares, symbol=stock["symbol"])
                        
        # Else increment the shares count
        else:
            shares_total = int(user_shares[0]["amount"]) + shares
            db.execute("UPDATE portfolio SET amount=:amount \
                         WHERE name=:name AND symbol=:symbol", \
                         amount=shares_total, name=session["user_id"], \
                         symbol=stock["symbol"])
        
        # return to index
        return redirect(url_for("index"))
#   return render_template("buy.html")
#   return apology("TODO")

@app.route("/history")
@login_required
def history():
    """Show history of transactions."""
    histories = db.execute("SELECT * from sell WHERE name=:id", id=session["user_id"])
    historieb = db.execute("SELECT * from buy WHERE name=:id", id=session["user_id"])
    
    return render_template("history.html", histories=histories, historieb=historieb)

#  return apology("TODO")

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in."""

    # forget any user_id
    session.clear()

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")

        # query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))

        # ensure username exists and password is correct
        if len(rows) != 1 or not pwd_context.verify(request.form.get("password"), rows[0]["hash"]):
            return apology("invalid username and/or password")

        # remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # redirect user to home page
        return redirect(url_for("index"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

@app.route("/logout")
def logout():
    """Log user out."""

    # forget any user_id
    session.clear()

    # redirect user to login form
    return redirect(url_for("login"))

@app.route("/quote", methods=["GET", "POST"])

@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        rows = lookup(request.form.get("symbol"))

        if not rows:
            return apology("Invalid Symbol")

        return render_template("quote2.html", stock=rows)

    else:
        return render_template("quote.html")

#  return apology("TODO")

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user."""

    if request.method == "POST":
        if not request.form.get("username"):
            return apology("You must provide a username")
        elif not request.form.get("password"):
            return apology("You must provide a password")
        elif not request.form.get("password2"):
            return apology("You must confirm your password")
        else:
            if request.form.get("password") != request.form.get("password2"):
                return apology("Password don\'t match")
            else:
                db.execute("INSERT INTO users (hash, username) Values(:hash_obj, :username)",
                hash_obj = pwd_context.hash(request.form.get("password")),
                username = request.form.get("username"))
                return render_template("login.html")
    else:
        return render_template("register.html")

@app.route("/password", methods=["GET", "POST"])
def password():
    """Change Password."""

    if request.method == "POST":
        if not request.form.get("password"):
            return apology("You must provide a password")
        elif not request.form.get("password2"):
            return apology("You must confirm your password")
        else:
            if request.form.get("password") != request.form.get("password2"):
                return apology("Password don\'t match")
            else:
                db.execute("UPDATE users SET hash=:hash_obj WHERE id=:id", id=session["user_id"], hash_obj = pwd_context.hash(request.form.get("password")))
                return redirect(url_for("login"))
    else:
        return render_template("password.html")


#   return apology("TODO")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock."""
    if request.method == "GET":
        return render_template("sell.html")
    else:
        # ensure proper symbol
        stock = lookup(request.form.get("symbol"))
        if not stock:
            return apology("Invalid Symbol")
        
        # ensure proper number of shares
        try:
            shares = int(request.form.get("shares"))
            if shares < 0:
                return apology("Shares must be positive integer")
        except:
            return apology("Shares must be positive integer")
        
        # select the symbol shares of that user
        user_shares = db.execute("SELECT amount FROM portfolio \
                                  WHERE name = :name AND symbol=:symbol", \
                                  name=session["user_id"], symbol=stock["symbol"])
        
        # check if enough shares to sell
        if not user_shares or int(user_shares[0]["amount"]) < shares:
            return apology("Not enough shares")
        
        now = datetime.datetime.now()
        # update history
        db.execute("INSERT INTO sell (symbol, amount, price, name, hist) \
                    VALUES(:symbol, :amount, :price, :name, :hist)", \
                    symbol=stock["symbol"], amount=shares, \
                    price=usd(stock["price"]), name=session["user_id"], hist=str(now))
                    
        # update user cash (increase)              
        db.execute("UPDATE users SET cash = cash + :purchase WHERE id = :id", \
                    id=session["user_id"], \
                    purchase=stock["price"] * float(shares))
                        
        # decrement the shares count
        shares_total = int(user_shares[0]["amount"]) - shares
        
        # if after decrement is zero, delete shares from portfolio
        if shares_total == 0:
            db.execute("DELETE FROM portfolio \
                        WHERE name=:name AND symbol=:symbol", \
                        name=session["user_id"], \
                        symbol=stock["symbol"])
        # otherwise, update portfolio shares count
        else:
            db.execute("UPDATE portfolio SET amount=:amount \
                    WHERE name=:name AND symbol=:symbol", \
                    amount=shares_total, name=session["user_id"], \
                    symbol=stock["symbol"])
        return redirect(url_for("index"))

#   return apology("TODO")
