from flask import Flask, render_template, request, jsonify
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

app = Flask(__name__)


# Filter Jinja untuk format Rupiah
@app.template_filter("rupiah")
def rupiah_format(value):
    try:
        value = float(value)
        return "Rp{:,.0f}".format(value).replace(",", ".")
    except (ValueError, TypeError):
        return value


def get_gold_data():
    """Ambil data emas 2 bulan terakhir"""
    end_date = datetime.today()
    start_date = end_date - timedelta(days=60)
    gold = yf.Ticker("GC=F")
    hist = gold.history(start=start_date, end=end_date, interval="1d")

    # Ambil kurs USD/IDR
    usd_idr = yf.Ticker("USDIDR=X").history(period="5d")
    latest_usd_idr = float(usd_idr["Close"].dropna().iloc[-1])

    # Konversi ke Rupiah/gram
    df = hist.dropna().copy()
    df["Gold_IDR_gram"] = (df["Close"] / 31.1034768) * latest_usd_idr

    df = df.reset_index()
    df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")

    # Hitung perubahan nominal & persen
    df["Change"] = df["Gold_IDR_gram"].diff()
    df["Percent_Change"] = df["Gold_IDR_gram"].pct_change() * 100
    df["Status"] = df["Change"].apply(
        lambda x: "Naik" if x > 0 else ("Turun" if x < 0 else "Tetap")
    )
    return df, latest_usd_idr


@app.route("/")
def index():
    df, usd_idr = get_gold_data()

    # Harga terbaru
    latest_usd_oz = float(df["Close"].iloc[-1])
    latest_usd_g = latest_usd_oz / 31.1034768
    latest_idr_g = df["Gold_IDR_gram"].iloc[-1]

    # Analisis 2 bulan
    max_increase = df.loc[df["Change"].idxmax()].to_dict()
    max_decrease = df.loc[df["Change"].idxmin()].to_dict()
    max_percent_increase = df.loc[df["Percent_Change"].idxmax()].to_dict()
    max_percent_decrease = df.loc[df["Percent_Change"].idxmin()].to_dict()

    # Pagination
    per_page = 10
    page = int(request.args.get("page", 1))
    two_months_sorted = df.sort_values(by="Date", ascending=False)
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
        latest_usd_oz=latest_usd_oz,
        latest_usd_g=latest_usd_g,
        latest_idr_g=latest_idr_g,
        update_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        chart_labels=df["Date"].tolist(),
        chart_values=df["Gold_IDR_gram"].round(2).tolist(),
        max_increase=max_increase,
        max_decrease=max_decrease,
        max_percent_increase=max_percent_increase,
        max_percent_decrease=max_percent_decrease,
        last_two_months=last_two_months,
        current_page=page,
        total_pages=total_pages,
    )


@app.route("/data")
def data():
    """Endpoint untuk grafik realtime"""
    df, _ = get_gold_data()
    return jsonify(
        {"dates": df["Date"].tolist(), "values": df["Gold_IDR_gram"].round(2).tolist()}
    )


if __name__ == "__main__":
    app.run(debug=True)
