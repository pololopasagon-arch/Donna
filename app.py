from flask import Flask, render_template, jsonify, request
import yfinance as yf
import feedparser
from groq import Groq
import json
import time
import os

app = Flask(__name__)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

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
CACHE_TTL     = 300

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/markets")
def markets():
    global markets_cache
    if markets_cache["data"] and (time.time() - markets_cache["timestamp"]) < CACHE_TTL:
        return jsonify(markets_cache["data"])
    data = []
    for name, symbol in INDICES.items():
        try:
            t     = yf.Ticker(symbol)
            info  = t.fast_info
            price = round(info.last_price, 2)
            prev  = round(info.previous_close, 2)
            pct   = round((price - prev) / prev * 100, 2)
            data.append({"name": name, "pct": pct})
        except:
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
        except:
            pass

    articles = articles[:24]

    try:
        client = Groq(api_key=GROQ_API_KEY)
        titles_text = "\n".join([
            f"{i+1}. [{a['source']}] {a['title']}"
            for i, a in enumerate(articles)
        ])
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{
                "role": "user",
                "content": f"""Transforma estos titulares en frases informativas en español (máximo 15 palabras). Incluye SIEMPRE el sujeto concreto: qué empresa, país, índice o activo, y el hecho clave con cifras si las hay. Ejemplo bueno: "Las tecnológicas de EE.UU. caen un 3% por el auge de la IA china DeepSeek". Ejemplo malo: "Las acciones caen por la IA". Traduce los que estén en inglés.

{titles_text}

Responde SOLO con JSON válido, sin texto adicional ni backticks:
[{{"improved": "titular aquí"}}, ...]"""
            }],
            max_tokens=2000,
            temperature=0.3,
        )
        improved = json.loads(response.choices[0].message.content)
        for i, imp in enumerate(improved):
            if i < len(articles):
                articles[i]["title"] = imp.get("improved", articles[i]["title"])
    except:
        pass

    news_cache["data"]      = articles
    news_cache["timestamp"] = time.time()
    return jsonify(articles)

@app.route("/api/article", methods=["POST"])
def article():
    data    = request.get_json()
    title   = data.get("title", "")
    summary = data.get("summary", "")
    source  = data.get("source", "")

    client   = Groq(api_key=GROQ_API_KEY)
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{
            "role": "user",
            "content": f"""Eres un periodista económico. Escribe un análisis completo de esta noticia para Gonzalo, estudiante de bachillerato que empieza Economía en CUNEF en septiembre. Nivel básico pero con ganas de aprender.

Titular: {title}
Resumen disponible: {summary}
Fuente: {source}

Usa EXACTAMENTE estos encabezados en este orden, sin asteriscos ni símbolos:

CONTEXTO
QUÉ HA PASADO
POR QUÉ IMPORTA
QUÉ VIGILAR

Escribe 2-3 párrafos por sección. En español, directo, sin relleno."""
        }],
        max_tokens=1200,
        temperature=0.5,
    )
    return jsonify({"content": response.choices[0].message.content})

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=5001)
