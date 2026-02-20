import yfinance as yf

data = yf.download("RELIANCE.NS", period="1y")
print(data.head())