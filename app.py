
import streamlit as st
import requests
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from sklearn.linear_model import LinearRegression

# 🎨 Configuration
st.set_page_config(page_title="Crypto Assistant Pro", layout="wide")

@st.cache_data
def get_price_data(coin, days=30):
    url = f"https://api.coingecko.com/api/v3/coins/{coin}/market_chart"
    params = {
        "vs_currency": "usd",
        "days": days,
        "interval": "daily"
    }
    res = requests.get(url, params=params)
    data = res.json()
    prices = data["prices"]
    df = pd.DataFrame(prices, columns=["Timestamp", "Price"])
    df["Date"] = pd.to_datetime(df["Timestamp"], unit="ms")
    df["Price"] = df["Price"].astype(float)
    return df

# RSI
def calculate_rsi(data, window=14):
    delta = data.diff()
    gain = delta.where(delta > 0, 0).rolling(window=window).mean()
    loss = -delta.where(delta < 0, 0).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# MACD
def calculate_macd(data):
    exp1 = data.ewm(span=12, adjust=False).mean()
    exp2 = data.ewm(span=26, adjust=False).mean()
    macd = exp1 - exp2
    signal = macd.ewm(span=9, adjust=False).mean()
    return macd, signal

# 🔮 Prédiction linéaire
def predict_next_prices(df, days=7):
    df["Index"] = np.arange(len(df))
    model = LinearRegression()
    model.fit(df[["Index"]], df["Price"])
    future_indexes = np.arange(len(df), len(df) + days).reshape(-1, 1)
    predictions = model.predict(future_indexes)
    future_dates = pd.date_range(df["Date"].iloc[-1] + pd.Timedelta(days=1), periods=days)
    return pd.DataFrame({"Date": future_dates, "Predicted Price": predictions})

# 💡 Sélection auto de cryptos performantes
@st.cache_data
def get_top_crypto_suggestions():
    coins = ["bitcoin", "ethereum", "solana", "ripple", "cardano", "dogecoin", "avalanche","tether"]
    suggestions = []
    for coin in coins:
        try:
            df = get_price_data(coin, days=30)
            start, end = df["Price"].iloc[0], df["Price"].iloc[-1]
            growth = (end - start) / start * 100
            suggestions.append((coin.capitalize(), growth))
        except:
            continue
    sorted_list = sorted(suggestions, key=lambda x: x[1], reverse=True)
    return sorted_list[:3]

# 🎯 Interface
st.title("📊 Crypto Assistant Pro")

tab1, tab2, tab3 = st.tabs(["🔍 Analyse d'une crypto", "🤖 Conseils d'investissement", "📈 Espace trader"])

with tab1:
    coin = st.text_input("Entrez une crypto (ex: bitcoin, ethereum)", "bitcoin")
    try:
        df = get_price_data(coin)
        last_price = df['Price'].iloc[-1]
        variation = df['Price'].iloc[-1] - df['Price'].iloc[0]
        variation_pct = (variation / df['Price'].iloc[0]) * 100

        col1, col2, col3 = st.columns(3)
        col1.metric("💰 Prix actuel", f"${last_price:,.2f} USD")
        col2.metric("📈 Variation (USD)", f"${variation:,.2f}", delta=f"{variation_pct:.2f}%")
        col3.metric("🕒 Période", "30 jours")

        st.subheader(f"📉 Évolution de {coin.capitalize()}")
        st.line_chart(df.set_index("Date")["Price"])

        st.subheader("🔮 Prédiction du prix (7 jours)")
        pred_df = predict_next_prices(df)
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df["Date"], y=df["Price"], name="Historique"))
        fig.add_trace(go.Scatter(x=pred_df["Date"], y=pred_df["Predicted Price"], name="Prévision", line=dict(dash='dash')))
        fig.update_layout(template="plotly_white")
        st.plotly_chart(fig, use_container_width=True)
    except:
        st.error("Crypto non reconnue ou problème de données.")

with tab2:
    st.subheader("🤖 Cryptos les plus performantes (30 derniers jours)")
    suggestions = get_top_crypto_suggestions()
    for name, growth in suggestions:
        st.markdown(f"✅ **{name}** : +{growth:.2f}%")

with tab3:
    coin_trader = st.text_input("Choisir une crypto pour trader", "bitcoin")
    try:
        df = get_price_data(coin_trader)
        df["RSI"] = calculate_rsi(df["Price"])
        df["MACD"], df["Signal"] = calculate_macd(df["Price"])

        st.subheader("RSI - Relative Strength Index")
        fig_rsi = go.Figure()
        fig_rsi.add_trace(go.Scatter(x=df["Date"], y=df["RSI"], line=dict(color="orange")))
        fig_rsi.update_layout(yaxis=dict(range=[0, 100]), template="plotly_white")
        st.plotly_chart(fig_rsi, use_container_width=True)

        st.subheader("MACD - Moyennes Mobiles")
        fig_macd = go.Figure()
        fig_macd.add_trace(go.Scatter(x=df["Date"], y=df["MACD"], name="MACD", line=dict(color="blue")))
        fig_macd.add_trace(go.Scatter(x=df["Date"], y=df["Signal"], name="Signal", line=dict(color="red")))
        fig_macd.update_layout(template="plotly_white")
        st.plotly_chart(fig_macd, use_container_width=True)
    except:
        st.error("Crypto non reconnue ou problème de données.")
