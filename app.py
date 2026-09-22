
import streamlit as st
import akshare as ak
import pandas as pd
import mplfinance as mpf
import matplotlib.pyplot as plt
import io
import numpy as np

st.title("我的 A 股技术分析")

股票代码 = st.text_input("股票代码", "600519")

if st.button("开始分析"):
    # 1. 抓数据
    df = ak.stock_zh_a_hist(
        symbol=股票代码, period="daily",
        start_date="20240101", end_date="20260922",
        adjust="qfq"
    )
    df["日期"] = pd.to_datetime(df["日期"])
    df = df.sort_values("日期").reset_index(drop=True)

    # 2. 计算 BBI 线
    bbi = (df["收盘"].rolling(3).mean() + df["收盘"].rolling(6).mean() +
           df["收盘"].rolling(12).mean() + df["收盘"].rolling(24).mean()) / 4
    df["BBI"] = bbi

    # 3. 计算均线
    df["MA20"] = df["收盘"].rolling(20).mean()
    df["MA60"] = df["收盘"].rolling(60).mean()

    # 4. 计算 KDJ
    最低 = df["最低"].rolling(9).min()
    最高 = df["最高"].rolling(9).max()
    RSV = (df["收盘"] - 最低) / (最高 - 最低) * 100
    K = RSV.ewm(com=2).mean()
    D = K.ewm(com=2).mean()
    df["K"] = K
    df["D"] = D

    # 5. 计算成交量均线
    df["量均5"] = df["成交量"].rolling(5).mean()

    # ===== 5 个维度打分 =====
    最新 = df.iloc[-1]
    昨日 = df.iloc[-2]

    # 维度1：趋势方向（低点比前一个低点高）
    # 取最近 20 天的最低点，和再前 20 天的最低点比较
    近20日最低 = df["最低"].tail(20).min()
    前20日最低 = df["最低"].tail(40).head(20).min()
    趋势方向 = 1 if 近20日最低 > 前20日最低 else 0

    # 维度2：收盘价不破 BBI
    生命线 = 1 if 最新["收盘"] > 最新["BBI"] else 0

    # 维度3：无巨量阴线
    # 定义：当日跌幅 > 3% 且 成交量 > 5日均量 1.5 倍
    昨日跌幅 = (昨日["收盘"] - 昨日["开盘"]) / 昨日["开盘"]
    昨日放量 = 昨日["成交量"] > 昨日["量均5"] * 1.5
    巨量阴线 = (昨日跌幅 < -0.03) and 昨日放量
    量价健康 = 0 if 巨量阴线 else 1

    # 维度4：均线向上
    均线向上 = 1 if 最新["MA20"] > 昨日["MA20"] else 0

    # 维度5：KDJ 没死叉
    KDJ健康 = 1 if 最新["K"] > 最新["D"] else 0

    # 总分
    总分 = 趋势方向 + 生命线 + 量价健康 + 均线向上 + KDJ健康

    # ===== 显示结果 =====
    st.subheader("五维度评分")
    st.write(f"1. 趋势方向（低点抬高）：{'✅ 通过' if 趋势方向 else '❌ 不通过'}")
    st.write(f"2. 收盘价不破 BBI：{'✅ 通过' if 生命线 else '❌ 不通过'}")
    st.write(f"3. 无巨量阴线：{'✅ 通过' if 量价健康 else '❌ 不通过'}")
    st.write(f"4. 均线向上：{'✅ 通过' if 均线向上 else '❌ 不通过'}")
    st.write(f"5. KDJ 没死叉：{'✅ 通过' if KDJ健康 else '❌ 不通过'}")
    st.write(f"### 总分：{总分} / 5")

    if 总分 >= 4:
        st.success("评级：重点观察")
    elif 总分 >= 3:
        st.warning("评级：观察")
    else:
        st.error("评级：回避")

    # ===== 画 K 线图 =====
    df2 = df.set_index("日期").rename(columns={
        "开盘": "Open", "收盘": "Close",
        "最高": "High", "最低": "Low",
        "成交量": "Volume"
    })
    buf = io.BytesIO()
    mpf.plot(df2.tail(120), type="candle", volume=True,
             mav=(20, 60), style="yahoo", figsize=(14, 8),
             savefig=dict(fname=buf, dpi=100, bbox_inches="tight"))
    st.image(buf.getvalue())
