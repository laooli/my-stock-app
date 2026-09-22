import streamlit as st
import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime
import time
import random

st.set_page_config(layout="wide", page_title="我的股票分析系统")
st.title("📊 我的股票分析系统")


# ========== 带缓存+重试的数据获取函数 ==========
@st.cache_data(ttl=300, show_spinner="正在获取行情数据...")
def get_stock_hist(code: str, start_date: str, end_date: str) -> pd.DataFrame | None:
    """指数退避重试 + 缓存，避免批量请求被封"""
    for attempt in range(3):
        try:
            df = ak.stock_zh_a_hist(
                symbol=code, period="daily",
                start_date=start_date, end_date=end_date, adjust="qfq"
            )
            if df is not None and len(df) > 0:
                return df
        except Exception:
            time.sleep((2 ** attempt) + random.uniform(0, 1))
    return None


# ========== 侧边栏：上传交割单 ==========
st.sidebar.header("📂 上传交割单")
上传文件 = st.sidebar.file_uploader("上传通达信交割单（txt）", type=["txt"])

if 上传文件 is not None:
    # ---------- 1. 解析交割单（适配真实格式）----------
    try:
        raw = 上传文件.read().decode("gbk")
    except UnicodeDecodeError:
        raw = 上传文件.read().decode("gb18030")

    from io import StringIO
    df = pd.read_csv(StringIO(raw), sep=r"\s+", skiprows=1, dtype=str)
    df = df.dropna(how="all").reset_index(drop=True)

    # 校验必要列
    必要列 = ["交割日期", "证券代码", "证券名称", "业务类型", "成交价格", "成交数量", "发生金额", "证券数量"]
    missing = [c for c in 必要列 if c not in df.columns]
    if missing:
        st.error(f"交割单缺少必要列：{missing}，请检查文件格式")
        st.stop()

    # 数值列转换（原始数据为字符串，避免科学计数法问题）
    num_cols = ["成交价格", "成交数量", "发生金额", "证券数量"]
    for col in num_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # ---------- 2. 筛选交易记录 & 计算真实持仓 ----------
    交易 = df[df["业务类型"].isin(["证券买入", "证券卖出"])].copy()
    交易["交割日期"] = pd.to_datetime(交易["交割日期"])
    交易 = 交易.sort_values("交割日期").reset_index(drop=True)

    # 真实持仓 = 累计买入数量 - 累计卖出数量（而非取最后一笔记录）
    持仓汇总 = 交易.groupby("证券代码").agg(
        证券名称=("证券名称", "last"),
        买入总量=("成交数量", lambda x: x[交易.loc[x.index, "业务类型"] == "证券买入"].sum()),
        卖出总量=("成交数量", lambda x: x[交易.loc[x.index, "业务类型"] == "证券卖出"].sum()),
        买入总成本=("发生金额", lambda x: x[交易.loc[x.index, "业务类型"] == "证券买入"].sum()),
    ).reset_index()
    持仓汇总["净持仓"] = 持仓汇总["买入总量"] - 持仓汇总["卖出总量"]
    最新持仓 = 持仓汇总[持仓汇总["净持仓"] > 0].copy()
    # 计算加权成本价（仅基于买入记录）
    最新持仓["成本价"] = np.where(
        最新持仓["买入总量"] > 0,
        abs(最新持仓["买入总成本"]) / 最新持仓["买入总量"],
        0
    )

    # ---------- 3. 账户总览（修正盈亏&胜率）----------
    st.subheader("📈 账户总览")

    # 总盈亏 = 所有卖出收入 + 所有买入支出（买入发生金额为负）
    买入总额 = 交易[交易["业务类型"] == "证券买入"]["发生金额"].sum()
    卖出总额 = 交易[交易["业务类型"] == "证券卖出"]["发生金额"].sum()
    已实现盈亏 = 卖出总额 + 买入总额  # 仅统计已完成买卖的标的

    # 胜率：按标的完整买卖周期计算（卖出均价 > 买入均价）
    盈利笔数 = 0
    总完成笔数 = 0
    for code in 交易["证券代码"].unique():
        sub = 交易[交易["证券代码"] == code]
        buys = sub[sub["业务类型"] == "证券买入"]
        sells = sub[sub["业务类型"] == "证券卖出"]
        if len(buys) == 0 or len(sells) == 0:
            continue
        总完成笔数 += 1
        buy_avg = abs(buys["发生金额"].sum()) / buys["成交数量"].sum()
        sell_avg = sells["发生金额"].sum() / sells["成交数量"].sum()
        if sell_avg > buy_avg:
            盈利笔数 += 1

    胜率 = (盈利笔数 / 总完成笔数 * 100) if 总完成笔数 > 0 else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("已实现盈亏", f"¥{已实现盈亏:.2f}", delta=f"{已实现盈亏:+.2f}")
    c2.metric("交易笔数", f"{len(交易)} 笔")
    c3.metric("胜率", f"{胜率:.1f}%")
    c4.metric("当前持仓", f"{len(最新持仓)} 只")

    # ---------- 4. 5维评分（动态日期 + 进度条）----------
    st.subheader("🎯 当前持仓 5 维评分")
    today = datetime.now().strftime("%Y%m%d")
    start_date = "20240101"

    if len(最新持仓) > 0:
        results = []
        bar = st.progress(0, text="正在分析持仓...")
        for i, (_, row) in enumerate(最新持仓.iterrows()):
            code = str(row["证券代码"]).zfill(6)
            bar.progress((i + 1) / len(最新持仓))

            hist = get_stock_hist(code, start_date, today)
            if hist is None or len(hist) < 30:
                results.append({
                    "代码": code, "名称": row["证券名称"], "数量": int(row["净持仓"]),
                    "成本价": round(row["成本价"], 2), "现价": None, "市值": 0,
                    "盈亏": 0, "盈亏率": 0, "5维评分": 0, "信号": "❌ 数据不足"
                })
                continue

            hist["日期"] = pd.to_datetime(hist["日期"])
            hist = hist.sort_values("日期").reset_index(drop=True)

            # BBI
            bbi = (hist["收盘"].rolling(3).mean() + hist["收盘"].rolling(6).mean() +
                   hist["收盘"].rolling(12).mean() + hist["收盘"].rolling(24).mean()) / 4
            # KDJ
            low9 = hist["最低"].rolling(9).min()
            high9 = hist["最高"].rolling(9).max()
            rsv = (hist["收盘"] - low9) / (high9 - low9) * 100
            K = rsv.ewm(com=2).mean()
            D = K.ewm(com=2).mean()

            latest = hist.iloc[-1]
            prev = hist.iloc[-2]

            # 5维打分
            d1 = 1 if hist["最低"].tail(20).min() > hist["最低"].tail(40).head(20).min() else 0
            d2 = 1 if latest["收盘"] > bbi.iloc[-1] else 0
            drop = (prev["收盘"] - prev["开盘"]) / prev["开盘"]
            vol_spike = prev["成交量"] > hist["成交量"].tail(5).mean() * 1.5
            d3 = 0 if (drop < -0.03 and vol_spike) else 1
            d4 = 1 if latest["收盘"] > hist["收盘"].tail(20).mean() else 0
            d5 = 1 if K.iloc[-1] > D.iloc[-1] else 0
            score = d1 + d2 + d3 + d4 + d5

            price = latest["收盘"]
            qty = int(row["净持仓"])
            cost = row["成本价"] * qty
            mv = price * qty
            pnl = mv - cost
            pnl_pct = (pnl / cost * 100) if cost > 0 else 0

            signal = "🔥 重点观察" if score >= 4 else ("👀 观察" if score >= 3 else "⚠️ 回避")
            results.append({
                "代码": code, "名称": row["证券名称"], "数量": qty,
                "成本价": round(cost / qty, 2), "现价": round(price, 2),
                "市值": round(mv, 2), "盈亏": round(pnl, 2),
                "盈亏率": round(pnl_pct, 2), "5维评分": score, "信号": signal
            })

        result_df = pd.DataFrame(results)

        def color_pnl(val):
            if pd.isna(val):
                return ""
            if val > 0:
                return "color:#00cc00;font-weight:bold"
            if val < 0:
                return "color:#ff3333;font-weight:bold"
            return ""

        st.dataframe(
            result_df.style.map(color_pnl, subset=["盈亏", "盈亏率"]),
            use_container_width=True, hide_index=True
        )
    else:
        st.info("当前无持仓")

    # ---------- 5. 交易记录 ----------
    st.subheader("📝 交易记录")
    st.dataframe(交易, use_container_width=True, hide_index=True)

else:
    st.info("👈 请在左侧上传通达信交割单（txt 文件）开始分析")
