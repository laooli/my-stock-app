import streamlit as st
import akshare as ak
import pandas as pd
import mplfinance as mpf
import matplotlib.pyplot as plt
import io
import numpy as np

st.set_page_config(layout="wide", page_title="我的股票分析")
st.title("📊 我的股票分析系统")

# ========== 第一部分：上传交割单 ==========
st.sidebar.header("📂 上传交割单")
上传文件 = st.sidebar.file_uploader("上传通达信交割单（txt）", type=["txt"])

if 上传文件 is not None:
    # 读文件
    try:
        df = pd.read_csv(上传文件, sep=r"\s+", skiprows=1, encoding="gbk")
    except:
        df = pd.read_csv(上传文件, sep=r"\s+", skiprows=1, encoding="gb18030")

    df = df.dropna(how="all")
    df = df[["交割日期", "证券代码", "证券名称", "业务类型", "成交价格", "成交数量", "成交金额", "发生金额", "证券数量"]]

    # 强制把数字列变成数字
    df["证券数量"] = pd.to_numeric(df["证券数量"], errors="coerce").fillna(0)
    df["成交价格"] = pd.to_numeric(df["成交价格"], errors="coerce").fillna(0)
    df["发生金额"] = pd.to_numeric(df["发生金额"], errors="coerce").fillna(0)
    df["成交数量"] = pd.to_numeric(df["成交数量"], errors="coerce").fillna(0)
    df["成交金额"] = pd.to_numeric(df["成交金额"], errors="coerce").fillna(0)

    # ========== 第二部分：账户总览 ==========
    st.subheader("📈 账户总览")

    交易 = df[df["业务类型"].isin(["证券买入", "证券卖出"])].copy()
    最新持仓 = df.groupby("证券代码").last().reset_index()
    最新持仓 = 最新持仓[最新持仓["证券数量"] > 0]

    买入总额 = 交易[交易["业务类型"] == "证券买入"]["发生金额"].sum()
    卖出总额 = 交易[交易["业务类型"] == "证券卖出"]["发生金额"].sum()
    总盈亏 = 卖出总额 + 买入总额

    盈利笔数 = 0
    总卖出笔数 = 0
    for 代码 in 交易["证券代码"].unique():
        子表 = 交易[交易["证券代码"] == 代码]
        买入 = 子表[子表["业务类型"] == "证券买入"]
        卖出 = 子表[子表["业务类型"] == "证券卖出"]
        if len(买入) > 0 and len(卖出) > 0:
            买入均价 = (买入["成交价格"] * 买入["成交数量"]).sum() / 买入["成交数量"].sum()
            卖出均价 = (卖出["成交价格"] * 卖出["成交数量"]).sum() / 卖出["成交数量"].sum()
            总卖出笔数 += 1
            if 卖出均价 > 买入均价:
                盈利笔数 += 1

    胜率 = 盈利笔数 / 总卖出笔数 * 100 if 总卖出笔数 > 0 else 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("总盈亏", f"¥{总盈亏:.2f}")
    col2.metric("交易笔数", f"{len(交易)} 笔")
    col3.metric("胜率", f"{胜率:.1f}%")
    col4.metric("当前持仓", f"{len(最新持仓)} 只")

    # ========== 第三部分：当前持仓 5 维评分 ==========
    st.subheader("🎯 当前持仓 5 维评分")

    if len(最新持仓) > 0:
        结果 = []
        for i in range(len(最新持仓)):
            代码 = str(最新持仓.iloc[i]["证券代码"]).zfill(6)
            名称 = 最新持仓.iloc[i]["证券名称"]
            数量 = 最新持仓.iloc[i]["证券数量"]
            成本价 = 最新持仓.iloc[i]["成交价格"]

            try:
                行情 = ak.stock_zh_a_hist(
                    symbol=代码, period="daily",
                    start_date="20240101", end_date="20260922",
                    adjust="qfq"
                )
                行情["日期"] = pd.to_datetime(行情["日期"])
                行情 = 行情.sort_values("日期").reset_index(drop=True)

                bbi = (行情["收盘"].rolling(3).mean() + 行情["收盘"].rolling(6).mean() +
                       行情["收盘"].rolling(12).mean() + 行情["收盘"].rolling(24).mean()) / 4

                最低 = 行情["最低"].rolling(9).min()
                最高 = 行情["最高"].rolling(9).max()
                RSV = (行情["收盘"] - 最低) / (最高 - 最低) * 100
                K = RSV.ewm(com=2).mean()
                D = K.ewm(com=2).mean()

                最新 = 行情.iloc[-1]
                昨日 = 行情.iloc[-2]

                近20日最低 = 行情["最低"].tail(20).min()
                前20日最低 = 行情["最低"].tail(40).head(20).min()
                趋势方向 = 1 if 近20日最低 > 前20日最低 else 0

                生命线 = 1 if 最新["收盘"] > bbi.iloc[-1] else 0

                昨日跌幅 = (昨日["收盘"] - 昨日["开盘"]) / 昨日["开盘"]
                昨日放量 = 昨日["成交量"] > 行情["成交量"].tail(5).mean() * 1.5
                巨量阴线 = (昨日跌幅 < -0.03) and 昨日放量
                量价健康 = 0 if 巨量阴线 else 1

                均线向上 = 1 if 最新["收盘"] > 行情["收盘"].tail(20).mean() else 0
                KDJ健康 = 1 if K.iloc[-1] > D.iloc[-1] else 0

                总分 = 趋势方向 + 生命线 + 量价健康 + 均线向上 + KDJ健康

                现价 = 最新["收盘"]
                市值 = 现价 * 数量
                成本 = 成本价 * 数量
                盈亏 = 市值 - 成本
                盈亏率 = 盈亏 / 成本 * 100 if 成本 > 0 else 0

                结果.append({
                    "代码": 代码,
                    "名称": 名称,
                    "数量": 数量,
                    "成本价": 成本价,
                    "现价": round(现价, 2),
                    "市值": round(市值, 2),
                    "盈亏": round(盈亏, 2),
                    "盈亏率": f"{盈亏率:.2f}%",
                    "5维评分": 总分,
                    "信号": "🔥 重点观察" if 总分 >= 4 else ("👀 观察" if 总分 >= 3 else "⚠️ 回避")
                })
            except Exception as e:
                结果.append({
                    "代码": 代码, "名称": 名称, "数量": 数量,
                    "成本价": 成本价, "现价": "获取失败", "市值": 0,
                    "盈亏": 0, "盈亏率": "0%", "5维评分": 0, "信号": "❌ 无法分析"
                })

        结果表 = pd.DataFrame(结果)

        def 着色(val):
            if isinstance(val, (int, float)):
                if val > 0:
                    return "color: #00ff00"
                elif val < 0:
                    return "color: #ff4444"
            return ""

        st.dataframe(
            结果表.style.applymap(着色, subset=["盈亏"]),
            use_container_width=True
        )

    # ========== 第四部分：交易记录 ==========
    st.subheader("📝 交易记录")
    st.dataframe(交易, use_container_width=True)

else:
    st.info("请先在左边上传通达信交割单（txt 文件）")
