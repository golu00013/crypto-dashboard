import time, json, requests, threading, os
from datetime import datetime
from flask import Flask, render_template_string

TELEGRAM_TOKEN = "8399826357:AAFw3sGXnFAwfkAoFsJ1pJVdiabJNC93wy4"
TELEGRAM_CHAT_ID = "6211724721"
GAMMA = "https://gamma-api.polymarket.com"
TIMEFRAMES = {"5m": 300, "15m": 900, "1h": 3600, "4h": 14400}

app = Flask(__name__)
results = []
history = {}
alerted = set()
last_check = {}

def send(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=10)
    except:
        pass

def get_markets():
    try:
        r = requests.get(f"{GAMMA}/markets",
            params={"limit": 50, "active": "true", "closed": "false", "order": "volume24hr"}, timeout=10)
        data = r.json()
        return data if isinstance(data, list) else data.get("markets", [])
    except:
        return []

def is_crypto(name):
    cryptos = ["bitcoin", "ethereum", "solana", "bnb", "doge", "cardano", "xrp", "ada", "litecoin", "btc", "eth", "sol"]
    return any(c in name.lower() for c in cryptos)

def get_coin_name(market_name):
    coins = {"bitcoin": "BTC", "ethereum": "ETH", "solana": "SOL", "bnb": "BNB", "doge": "DOGE", "cardano": "ADA", "xrp": "XRP", "litecoin": "LTC"}
    name_lower = market_name.lower()
    for key, val in coins.items():
        if key in name_lower:
            return val
    return market_name[:10]

def monitor():
    global results
    while True:
        try:
            new_results = []
            for m in get_markets():
                mid = m.get("id") or m.get("conditionId", "")
                name = m.get("question", "?")[:60]
                vol = float(m.get("volume", 0))
                if not is_crypto(name) or vol < 30000:
                    continue
                try:
                    prices = json.loads(m.get("outcomePrices", "[0.5,0.5]"))
                    yes = round(float(prices[0]) * 100, 1)
                except:
                    continue
                d = "UP" if yes > 52 else ("DOWN" if yes < 48 else None)
                if not d:
                    continue
                coin = get_coin_name(name)
                if mid not in history:
                    history[mid] = {tf: [] for tf in TIMEFRAMES}
                    last_check[mid] = {tf: time.time() for tf in TIMEFRAMES}
                for tf, interval in TIMEFRAMES.items():
                    if time.time() - last_check[mid][tf] >= interval:
                        history[mid][tf].append(d)
                        if len(history[mid][tf]) > 3:
                            history[mid][tf].pop(0)
                        last_check[mid][tf] = time.time()
                        h = history[mid][tf]
                        if len(h) == 3 and len(set(h)) == 1:
                            key = f"{mid}_{tf}_{d}"
                            if key not in alerted:
                                alerted.add(key)
                                e = "🟢" if d == "UP" else "🔴"
                                send(f"{e}{e}{e} <b>3x {d} {tf}!</b>\n\n📊 {coin}\n💰 {yes}¢")
                        new_results.insert(0, {
                            "coin": coin,
                            "tf": tf,
                            "direction": d,
                            "price": yes,
                            "time": datetime.now().strftime("%H:%M:%S"),
                            "status": "✅ 3x" if (len(h) == 3 and len(set(h)) == 1) else f"{len(h)}/3"
                        })
            results = new_results[:100]
            time.sleep(300)
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(30)

@app.route("/")
def index():
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Crypto Dashboard</title>
        <meta http-equiv="refresh" content="60">
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { background: #0d0d0d; color: #fff; font-family: Arial; padding: 20px; }
            h1 { color: #00ff88; margin-bottom: 20px; }
            .info { color: #888; font-size: 12px; margin-bottom: 20px; }
            table { width: 100%; border-collapse: collapse; }
            th { background: #1a1a2e; padding: 12px; text-align: left; font-weight: bold; }
            tr { border-bottom: 1px solid #222; }
            td { padding: 12px; }
            tr:hover { background: #1a1a2e; }
            .coin { font-weight: bold; font-size: 14px; }
            .dot { width: 12px; height: 12px; border-radius: 50%; display: inline-block; margin-right: 8px; }
            .dot-up { background: #00ff88; }
            .dot-down { background: #ff4444; }
            .up { color: #00ff88; }
            .down { color: #ff4444; }
            .tf { color: #888; font-size: 12px; }
            .status { color: #ffaa00; font-weight: bold; }
            .time { color: #666; font-size: 11px; }
        </style>
    </head>
    <body>
        <h1>🤖 Crypto UP/DOWN Dashboard</h1>
        <div class="info">
            ⏰ Auto refresh: 60s | 📊 Timeframes: 5m, 15m, 1h, 4h | 🔔 Live data
        </div>
        <table>
            <tr>
                <th>Coin</th>
                <th>TimeFrame</th>
                <th>Direction</th>
                <th>Price</th>
                <th>Status</th>
                <th>Time</th>
            </tr>
            {% for r in results %}
            <tr>
                <td class="coin">{{ r.coin }}</td>
                <td class="tf">{{ r.tf }}</td>
                <td>
                    <span class="dot dot-{{ 'up' if r.direction == 'UP' else 'down' }}"></span>
                    <span class="{{ 'up' if r.direction == 'UP' else 'down' }}">{{ r.direction }}</span>
                </td>
                <td>{{ r.price }}¢</td>
                <td class="status">{{ r.status }}</td>
                <td class="time">{{ r.time }}</td>
            </tr>
            {% endfor %}
        </table>
    </body>
    </html>
    """
    return render_template_string(html, results=results)

if __name__ == "__main__":
    t = threading.Thread(target=monitor, daemon=True)
    t.start()
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
