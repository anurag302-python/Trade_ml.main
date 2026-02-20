from flask import Flask, render_template, request, redirect, jsonify
import sqlite3
import pandas as pd
import yfinance as yf
import plotly.graph_objs as go
from plotly.subplots import make_subplots
from sklearn.linear_model import LogisticRegression
import ta

app = Flask(__name__)

# -------- DATABASE --------
def get_db():
    return sqlite3.connect("trades.db")


# -------- HOME --------
@app.route("/")
def index():
    return render_template("index.html")


# -------- HISTORY --------
@app.route("/history")
def history():
    db = get_db()
    trades = db.execute("SELECT * FROM trades").fetchall()
    db.close()
    return render_template("history.html", trades=trades)


# -------- MARKET ANALYSIS (INTERACTIVE) --------
@app.route("/market")
def market():

    stock = request.args.get("stock", "").upper()
    period = request.args.get("period", "6mo")

    if not stock:
        return "Enter Stock Symbol"

    if not stock.endswith(".NS") and not stock.endswith(".BO"):
        stock = stock + ".NS"

    df = yf.download(stock, period=period)

    if df.empty:
        return "Invalid Stock Symbol"

    df.columns = df.columns.get_level_values(0)

    # ===== TECHNICAL INDICATORS =====

    # Moving Averages
    df["MA20"] = df["Close"].rolling(20).mean()
    df["MA50"] = df["Close"].rolling(50).mean()

    # RSI
    delta = df["Close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()
    rs = avg_gain / avg_loss
    df["RSI"] = 100 - (100 / (1 + rs))

    # MACD
    exp1 = df["Close"].ewm(span=12, adjust=False).mean()
    exp2 = df["Close"].ewm(span=26, adjust=False).mean()
    df["MACD"] = exp1 - exp2
    df["MACD_SIGNAL"] = df["MACD"].ewm(span=9, adjust=False).mean()

    # Bollinger Bands
    df["BB_MIDDLE"] = df["Close"].rolling(20).mean()
    std = df["Close"].rolling(20).std()
    df["BB_UPPER"] = df["BB_MIDDLE"] + (2 * std)
    df["BB_LOWER"] = df["BB_MIDDLE"] - (2 * std)
    signal = generate_signal(df)

    # ---- TECHNICAL INDICATORS CALCULATION ----

    # Moving Averages
    df["MA20"] = df["Close"].rolling(window=20).mean()
    df["MA50"] = df["Close"].rolling(window=50).mean()

    # RSI
    df["RSI"] = ta.momentum.RSIIndicator(df["Close"], window=14).rsi()

    # MACD
    macd = ta.trend.MACD(df["Close"])
    df["MACD"] = macd.macd()
    df["MACD_SIGNAL"] = macd.macd_signal()

    # Bollinger Bands
    bb = ta.volatility.BollingerBands(df["Close"])
    df["BB_HIGH"] = bb.bollinger_hband()
    df["BB_LOW"] = bb.bollinger_lband()

    # ---- PLOTTING ----

    fig = make_subplots(
        rows=4, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.5, 0.2, 0.15, 0.15]
    )

    # --- CANDLESTICK ---
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df['Open'],
            high=df['High'],
            low=df['Low'],
            close=df['Close'],
            name="Price"
        ),
        row=1, col=1
    )

    # Moving Averages on Price Chart
    fig.add_trace(go.Scatter(x=df.index, y=df["MA20"], name="MA 20"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["MA50"], name="MA 50"), row=1, col=1)

    # Bollinger Bands
    fig.add_trace(go.Scatter(x=df.index, y=df["BB_HIGH"], name="BB Upper"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["BB_LOW"], name="BB Lower"), row=1, col=1)

    # --- VOLUME ---
    fig.add_trace(
        go.Bar(
            x=df.index,
            y=df['Volume'],
            name="Volume"
        ),
        row=2, col=1
    )

    # --- RSI ---
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df["RSI"],
            name="RSI"
        ),
        row=3, col=1
    )

    # --- MACD ---
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df["MACD"],
            name="MACD"
        ),
        row=4, col=1
    )

    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df["MACD_SIGNAL"],
            name="Signal Line"
        ),
        row=4, col=1
    )

    fig.update_layout(
        title=f"{stock} Advanced Technical Analysis",
        template="plotly_dark",
        height=1000,
        xaxis_rangeslider_visible=False
    )

    chart_html = fig.to_html(full_html=False)

    info = yf.Ticker(stock).info

    details = {
        "price": info.get("currentPrice", "N/A"),
        "market_cap": info.get("marketCap", "N/A"),
        "52_week_high": info.get("fiftyTwoWeekHigh", "N/A"),
        "52_week_low": info.get("fiftyTwoWeekLow", "N/A")
    }

    return render_template(
        "index.html",
        chart=chart_html,
        details=details,
        signal=signal
    )


# -------- STOCK SEARCH API --------
# ------------- SIMPLE STABLE STOCK SEARCH API --------------

@app.route("/search_stock")
def search_stock():

    query = request.args.get("q", "").upper()

    STOCK_LIST = [
        "RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK",
        "SBIN", "AXISBANK", "ITC", "WIPRO", "LT",
        "BAJFINANCE", "HCLTECH", "MARUTI", "TATAMOTORS",
        "ADANIENT", "ADANIPORTS", "TITAN", "SUNPHARMA",
        "ONGC", "COALINDIA", "NTPC", "POWERGRID",
        "BPCL", "IOC", "BHARTIARTL", "ASIANPAINT",
        "HINDUNILVR", "ULTRACEMCO", "JSWSTEEL", "VEDL"
    ]

    if not query:
        return jsonify([])

    results = []

    for stock in STOCK_LIST:
        if query in stock:
            results.append(stock)

    return jsonify(results)


def generate_signal(df):

    latest = df.iloc[-1]

    buy_score = 0
    sell_score = 0

    # RSI
    if latest["RSI"] < 30:
        buy_score += 1
    elif latest["RSI"] > 70:
        sell_score += 1

    # MACD
    if latest["MACD"] > latest["MACD_SIGNAL"]:
        buy_score += 1
    else:
        sell_score += 1

    # Moving Average Trend
    if latest["Close"] > latest["MA20"] and latest["Close"] > latest["MA50"]:
        buy_score += 1
    else:
        sell_score += 1

    # Bollinger
    if latest["Close"] <= latest["BB_LOWER"]:
        buy_score += 1
    elif latest["Close"] >= latest["BB_UPPER"]:
        sell_score += 1

    if buy_score > sell_score:
        return "BUY"
    elif sell_score > buy_score:
        return "SELL"
    else:
        return "HOLD"

# -------- ML PREDICTION --------
@app.route("/prediction")
def prediction():

    stock = request.args.get("stock", "RELIANCE")

    db = get_db()
    df = pd.read_sql_query(
        "SELECT buy, sell, profit, result FROM trades WHERE stock=?",
        db,
        params=(stock,)
    )
    db.close()

    if len(df) < 5:
        result = "Not enough data for prediction."
    else:
        X = df[["buy", "sell", "profit"]]
        y = df["result"]

        model = LogisticRegression()
        model.fit(X, y)

        prob = model.predict_proba(X.tail(1))[0][1] * 100

        result = f"Profit Probability for {stock}: {round(prob,2)}%"

    return render_template("prediction.html", result=result)


if __name__ == "__main__":
    app.run(debug=True)