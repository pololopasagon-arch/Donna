from flask import Flask, render_template, jsonify
import yfinance as yf
import feedparser
import time
import os
from datetime import datetime

app = Flask(__name__)

INDICES = {
    "IBEX 35":       "^IBEX",
    "S&P 500":       "^GSPC",
    "Nasdaq 100":    "^NDX",
    "Dow Jones 30":  "^DJI",
    "Euro Stoxx 50": "^STOXX50E",
    "FTSE 100":      "^FTSE",
    "DAX 40":        "^GDAXI",
    "CAC 40":        "^FCHI",
    "Nikkei 225":    "^N225",
}

COMMODITIES = {
    "Oro":      "GC=F",
    "Petróleo": "CL=F",
    "Bitcoin":  "BTC-USD",
}

RSS_FEEDS = [
    ("Expansión",       "https://e00-expansion.uecdn.es/rss/portada.xml"),
    ("El Confidencial", "https://rss.elconfidencial.com/economia/"),
    ("WSJ",             "https://feeds.a.dj.com/rss/RSSMarketsMain.xml"),
    ("El Mundo",        "https://www.elmundo.es/rss/economia.xml"),
    ("FT",              "https://www.ft.com/rss/home/spanish"),
]

news_cache       = {"data": None, "timestamp": 0}
markets_cache    = {"data": None, "timestamp": 0}
commodities_cache = {"data": None, "timestamp": 0}

CACHE_TTL         = 60
CACHE_TTL_WEEKEND = 3600

def get_ttl():
    dow = datetime.now().weekday()  # 5=sábado, 6=domingo
    return CACHE_TTL_WEEKEND if dow >= 5 else CACHE_TTL

def fetch_pct(symbol):
    t = yf.Ticker(symbol)
    hist = t.history(period="5d", interval="1d")
    hist = hist[hist["Close"].notna()]
    if len(hist) >= 2:
        prev  = float(hist["Close"].iloc[-2])
        price = float(hist["Close"].iloc[-1])
        return round((price - prev) / prev * 100, 2)
    return None

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/config")
def config():
    return jsonify({"groq_key": os.environ.get("GROQ_API_KEY", "")})

@app.route("/api/status")
def status():
    def age(cache):
        if not cache["data"]:
            return None
        return round(time.time() - cache["timestamp"])
    return jsonify({
        "markets_age":    age(markets_cache),
        "commodities_age": age(commodities_cache),
        "news_age":       age(news_cache),
        "is_weekend":     datetime.now().weekday() >= 5,
    })

@app.route("/api/refresh")
def refresh():
    global news_cache, markets_cache, commodities_cache
    news_cache       = {"data": None, "timestamp": 0}
    markets_cache    = {"data": None, "timestamp": 0}
    commodities_cache = {"data": None, "timestamp": 0}
    return jsonify({"ok": True})

@app.route("/api/markets")
def markets():
    global markets_cache
    ttl = get_ttl()
    if markets_cache["data"] and (time.time() - markets_cache["timestamp"]) < ttl:
        return jsonify(markets_cache["data"])
    data = []
    for name, symbol in INDICES.items():
        try:
            pct = fetch_pct(symbol)
            data.append({"name": name, "pct": pct})
        except Exception:
            data.append({"name": name, "pct": None})
    markets_cache["data"]      = data
    markets_cache["timestamp"] = time.time()
    return jsonify(data)

@app.route("/api/commodities")
def commodities():
    global commodities_cache
    ttl = get_ttl()
    if commodities_cache["data"] and (time.time() - commodities_cache["timestamp"]) < ttl:
        return jsonify(commodities_cache["data"])
    data = []
    for name, symbol in COMMODITIES.items():
        try:
            pct = fetch_pct(symbol)
            data.append({"name": name, "pct": pct})
        except Exception:
            data.append({"name": name, "pct": None})
    commodities_cache["data"]      = data
    commodities_cache["timestamp"] = time.time()
    return jsonify(data)

@app.route("/api/news")
def news():
    global news_cache
    ttl = get_ttl()
    if news_cache["data"] and (time.time() - news_cache["timestamp"]) < ttl:
        return jsonify(news_cache["data"])

    # Recoge hasta 6 por fuente
    buckets = {}
    for source, url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            buckets[source] = []
            for entry in feed.entries[:6]:
                buckets[source].append({
                    "source":  source,
                    "title":   entry.get("title", ""),
                    "link":    entry.get("link", "#"),
                    "summary": entry.get("summary", "")
                })
        except Exception:
            buckets[source] = []

    # Intercala: 1 de cada fuente rotando hasta 24
    sources = list(buckets.keys())
    articles = []
    i = 0
    while len(articles) < 24:
        added = False
        for src in sources:
            if buckets[src]:
                articles.append(buckets[src].pop(0))
                added = True
                if len(articles) >= 24:
                    break
        if not added:
            break

    news_cache["data"]      = articles
    news_cache["timestamp"] = time.time()
    return jsonify(articles)

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=5001)
