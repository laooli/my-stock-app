
import streamlit as st
import akshare as ak
import pandas as pd
import mplfinance as mpf
import matplotlib.pyplot as plt
import io

st.title("我的 A 股技术分析")

code = st.text_input("股票代码", "600519")

if st.button("开始分析"):
    df = ak.stock_zh_a_hist(
        symbol=code, period="daily",
        start_date="20240101", end_date="20260922",
        adjust="qfq"
    )
    df["日期"] = pd.to_datetime(df["日期"])
    df = df.set_index("日期")
    df["MA20"] = df["收盘"].rolling(20).mean()
    df["MA60"] = df["收盘"].rolling(60).mean()
    df["MA200"] = df["收盘"].rolling(200).mean()

    ema12 = df["收盘"].ewm(span=12, adjust=False).mean()
    ema26 = df["收盘"].ewm(span=26, adjust=False).mean()
    df["DIF"] = ema12 - ema26
    df["DEA"] = df["DIF"].ewm(span=9, adjust=False).mean()
    df["MACD"] = (df["DIF"] - df["DEA"]) * 2

    delta = df["收盘"].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss
    df["RSI"] = 100 - 100 / (1 + rs)

    last = df.iloc[-1]
    trend = 0
    if last["收盘"] > last["MA200"]: trend += 2
    if last["MA20"] > last["MA60"]: trend += 2
    if last["收盘"] > last["MA20"]: trend += 1

    momentum = 0
    if last["MACD"] > 0: momentum += 3
    if last["MACD"] > df["MACD"].iloc[-2]: momentum += 2

    vol5 = df["成交量"].rolling(5).mean().iloc[-1]
    vol20 = df["成交量"].rolling(20).mean().iloc[-1]
    volume = 5 if vol5 > vol20 else 2

    total = trend * 6 + momentum * 4 + volume * 4

    st.write(f"趋势：{trend}")
    st.write(f"动量：{momentum}")
    st.write(f"量能：{volume}")
    st.write(f"总分：{total} / 70")

    df2 = df.rename(columns={
        "开盘": "Open", "收盘": "Close",
        "最高": "High", "最低": "Low",
        "成交量": "Volume"
    })
    buf = io.BytesIO()
    mpf.plot(df2.tail(120), type="candle", volume=True,
             mav=(20, 60), style="yahoo", figsize=(14, 8),
             savefig=dict(fname=buf, dpi=100, bbox_inches="tight"))
    st.image(buf.getvalue())
