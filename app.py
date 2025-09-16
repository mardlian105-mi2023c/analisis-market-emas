from flask import Flask, render_template, request
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import json
import os

app = Flask(__name__)

CACHE_FILE = "gold_cache.json"
CACHE_EXPIRY = timedelta(hours=6)  # refresh tiap 6 jam


# 🔹 Filter Jinja untuk format Rupiah
@app.template_filter("rupiah")
def rupiah_format(value):
    try:
        value = float(value)
        return "Rp{:,.0f}".format(value).replace(",", ".")
    except (ValueError, TypeError):
        return value


# 🔹 Ambil data dari cache / Yahoo Finance
def get_cached_data():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            cache = json.load(f)

        last_update = datetime.fromisoformat(cache["last_update"])
        if datetime.now() - last_update < CACHE_EXPIRY:
            # ✅ Gunakan cache kalau belum 6 jam
            return cache

    # 🔄 Fetch baru dari Yahoo Finance (6 bulan terakhir)
    gold = yf.Ticker("GC=F")
    hist = gold.history(period="6mo")  # hanya 6 bulan terakhir

    usd_idr = yf.Ticker("USDIDR=X")
    fx_hist = usd_idr.history(period="6mo")
    latest_usd_idr = float(fx_hist["Close"].dropna().iloc[-1])

    latest_usd_oz = float(hist["Close"].dropna().iloc[-1])
    latest_usd_g = latest_usd_oz / 31.1034768
    latest_idr_g = latest_usd_g * latest_usd_idr

    df = hist.dropna().copy()
    df["Gold_IDR_gram"] = (df["Close"] / 31.1034768) * latest_usd_idr
    df = df.reset_index()
    df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")

    df["Change"] = df["Gold_IDR_gram"].diff()
    df["Percent_Change"] = df["Gold_IDR_gram"].pct_change() * 100
    df["Status"] = df["Change"].apply(
        lambda x: "Naik" if x > 0 else ("Turun" if x < 0 else "Tetap")
    )

    cache = {
        "last_update": datetime.now().isoformat(),
        "latest_usd_oz": latest_usd_oz,
        "latest_usd_g": latest_usd_g,
        "latest_idr_g": latest_idr_g,
        "latest_usd_idr": latest_usd_idr,
        "data": df.to_dict(orient="records"),
    }

    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f)

    return cache


@app.route("/")
def index():
    cache = get_cached_data()
    df = pd.DataFrame(cache["data"])

    # Data chart (6 bulan terakhir)
    chart_labels = df["Date"].tolist()
    chart_values = df["Gold_IDR_gram"].round(2).tolist()

    # Analisis 2 bulan terakhir dari data 6 bulan
    two_months_df = df.tail(60)

    max_increase = two_months_df.loc[two_months_df["Change"].idxmax()].to_dict()
    max_decrease = two_months_df.loc[two_months_df["Change"].idxmin()].to_dict()
    max_percent_increase = two_months_df.loc[
        two_months_df["Percent_Change"].idxmax()
    ].to_dict()
    max_percent_decrease = two_months_df.loc[
        two_months_df["Percent_Change"].idxmin()
    ].to_dict()

    # Status pasar
    market_status = (
        "Naik"
        if df["Change"].iloc[-1] > 0
        else ("Turun" if df["Change"].iloc[-1] < 0 else "Tetap")
    )
    market_status_color = (
        "green"
        if market_status == "Naik"
        else ("red" if market_status == "Turun" else "gray")
    )
    market_trend = (
        "Bullish"
        if market_status == "Naik"
        else ("Bearish" if market_status == "Turun" else "Sideways")
    )

    # Pagination tabel (data 2 bulan terakhir)
    per_page = 10
    page = int(request.args.get("page", 1))
    two_months_sorted = two_months_df.sort_values(by="Date", ascending=False)

    total_rows = len(two_months_sorted)
    total_pages = (total_rows // per_page) + (1 if total_rows % per_page != 0 else 0)

    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    last_two_months = (
        two_months_sorted[
            ["Date", "Gold_IDR_gram", "Status", "Change", "Percent_Change"]
        ]
        .iloc[start_idx:end_idx]
        .round(2)
        .to_dict(orient="records")
    )

    return render_template(
        "index.html",
        latest_usd_oz=cache["latest_usd_oz"],
        latest_usd_g=cache["latest_usd_g"],
        latest_idr_g=cache["latest_idr_g"],
        update_time=datetime.fromisoformat(cache["last_update"]).strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
        chart_labels=chart_labels,
        chart_values=chart_values,
        max_increase=max_increase,
        max_decrease=max_decrease,
        max_percent_increase=max_percent_increase,
        max_percent_decrease=max_percent_decrease,
        market_status=market_status,
        market_status_color=market_status_color,
        market_trend=market_trend,
        last_two_months=last_two_months,
        current_page=page,
        total_pages=total_pages,
    )


if __name__ == "__main__":
    app.run(debug=True)
