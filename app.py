from flask import Flask, render_template, jsonify
import yfinance as yf
import feedparser
import time
import os

app = Flask(__name__)

INDICES = {
    "IBEX 35":    "^IBEX",
    "S&P 500":    "^GSPC",
    "NASDAQ":     "^IXIC",
    "Euro Stoxx": "^STOXX50E",
    "FTSE 100":   "^FTSE",
    "Nikkei":     "^N225",
    "DAX":        "^GDAXI",
}

RSS_FEEDS = [
    ("Expansión",       "https://e00-expansion.uecdn.es/rss/portada.xml"),
    ("El Confidencial", "https://rss.elconfidencial.com/economia/"),
    ("WSJ",             "https://feeds.a.dj.com/rss/RSSMarketsMain.xml"),
    ("El Mundo",        "https://www.elmundo.es/rss/economia.xml"),
]

news_cache    = {"data": None, "timestamp": 0}
markets_cache = {"data": None, "timestamp": 0}
CACHE_TTL = 300

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/config")
def config():
    return jsonify({"groq_key": os.environ.get("GROQ_API_KEY", "")})

@app.route("/api/markets")
def markets():
    global markets_cache
    if markets_cache["data"] and (time.time() - markets_cache["timestamp"]) < CACHE_TTL:
        return jsonify(markets_cache["data"])

    data = []
    for name, symbol in INDICES.items():
        try:
            t = yf.Ticker(symbol)
            hist = t.history(period="5d", interval="1d")
            hist = hist[hist["Close"].notna()]
            if len(hist) >= 2:
                prev  = float(hist["Close"].iloc[-2])
                price = float(hist["Close"].iloc[-1])
                pct   = round((price - prev) / prev * 100, 2)
            else:
                pct = None
            data.append({"name": name, "pct": pct})
        except Exception:
            data.append({"name": name, "pct": None})

    markets_cache["data"]      = data
    markets_cache["timestamp"] = time.time()
    return jsonify(data)

@app.route("/api/news")
def news():
    global news_cache
    if news_cache["data"] and (time.time() - news_cache["timestamp"]) < CACHE_TTL:
        return jsonify(news_cache["data"])

    articles = []
    for source, url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:6]:
                articles.append({
                    "source":  source,
                    "title":   entry.get("title", ""),
                    "link":    entry.get("link", "#"),
                    "summary": entry.get("summary", "")
                })
        except Exception:
            pass

    articles = articles[:24]
    news_cache["data"]      = articles
    news_cache["timestamp"] = time.time()
    return jsonify(articles)

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=5001)
