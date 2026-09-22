import streamlit as st
import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime
import time
import random
import matplotlib.pyplot as plt

# 设置页面配置
st.set_page_config(layout="wide", page_title="我的股票分析系统", page_icon="📊")
st.title("📊 我的股票分析系统")

# ========== 1. 带缓存的行情获取函数 ==========
@st.cache_data(ttl=600)  # 缓存10分钟
def get_stock_hist(code: str, start_date: str, end_date: str) -> pd.DataFrame | None:
    """获取A股历史数据"""
    for attempt in range(3):
        try:
            df = ak.stock_zh_a_hist(symbol=code, period="daily", 
                                    start_date=start_date, end_date=end_date, adjust="qfq")
            if df is not None and len(df) > 0:
                return df
        except Exception:
            time.sleep((2 ** attempt) + random.uniform(0, 1))
    return None

# ========== 2. 侧边栏：上传文件 ==========
st.sidebar.header("📂 上传交割单")
uploaded_file = st.sidebar.file_uploader("上传通达信/券商交割单（txt 或 csv）", type=["txt", "csv"])

if uploaded_file is not None:
    # ---------- 解析文件 ----------
    try:
        raw = uploaded_file.read().decode("gbk")
    except UnicodeDecodeError:
        try:
            raw = uploaded_file.read().decode("gb18030")
        except Exception:
            st.error("无法解析文件编码，请检查是否为通达信标准格式")
            st.stop()

    from io import StringIO
    df = pd.read_csv(StringIO(raw), sep=r"\s+", skiprows=1, dtype=str)
    df = df.dropna(how="all").reset_index(drop=True)

    # 统一列名（防止不同券商导出的列名微调导致报错）
    列名映射 = {
        "日期": "交割日期", "交易日期": "交割日期",
        "代码": "证券代码", "股票代码": "证券代码",
        "名称": "证券名称", "股票名称": "证券名称",
        "买卖标志": "业务类型", "买卖方向": "业务类型",
        "成交价格": "成交价格", "成交价": "成交价格",
        "成交数量": "成交数量", "成交量": "成交数量",
        "成交金额": "成交金额",
        "发生金额": "发生金额", "实际发生金额": "发生金额",
        "证券数量": "证券数量", "当前持仓": "证券数量"
    }
    df.rename(columns=列名映射, inplace=True)

    # 强制要求包含的列
    必要列 = ["交割日期", "证券代码", "证券名称", "业务类型", "成交价格", "成交数量", "发生金额", "证券数量"]
    missing = [c for c in 必要列 if c not in df.columns]
    if missing:
        st.error(f"交割单缺少必要列，请检查文件格式：{missing}")
        st.stop()

    # 类型转换
    df["交割日期"] = pd.to_datetime(df["交割日期"], errors="coerce")
    for col in ["成交价格", "成交数量", "发生金额", "证券数量"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # 排序
    df = df.sort_values("交割日期").reset_index(drop=True)

    # 筛选纯买卖交易（剔除利息、分红、转账等非交易记录）
    交易 = df[df["业务类型"].isin(["证券买入", "证券卖出", "买", "卖"])].copy()
    if len(交易) == 0:
        st.info("未检测到有效的证券买入/卖出交易记录")
        st.stop()

    # 统一业务类型名称
    交易["业务类型"] = 交易["业务类型"].replace({"买": "证券买入", "卖": "证券卖出"})

    # ========== 3. 计算真实持仓和加权成本 ==========
    持仓列表 = []
    for code in 交易["证券代码"].unique():
        sub = 交易[交易["证券代码"] == code].sort_values("交割日期")
        买入记录 = sub[sub["业务类型"] == "证券买入"]
        卖出记录 = sub[sub["业务类型"] == "证券卖出"]
        
        买入总量 = 买入记录["成交数量"].sum()
        卖出总量 = 卖出记录["成交数量"].sum()
        净持仓 = 买入总量 - 卖出总量

        if 净持仓 > 0:
            # 加权平均成本 = 总买入金额 / 总买入数量 (发生金额为负，取绝对值)
            买入总成本 = abs(买入记录["发生金额"].sum())
            加权成本 = 买入总成本 / 买入总量 if 买入总量 > 0 else 0
            持仓列表.append({
                "证券代码": str(code).zfill(6),
                "证券名称": sub.iloc[-1]["证券名称"],
                "净持仓": int(净持仓),
                "加权成本": round(加权成本, 3)
            })
    
    最新持仓 = pd.DataFrame(持仓列表)

    # ========== 4. 账户总览 & 胜率计算 ==========
    st.subheader("📈 账户总览")
    
    # 总盈亏 = 卖出总收入 + 买入总支出
    买入总金额 = 交易[交易["业务类型"] == "证券买入"]["发生金额"].sum()
    卖出总金额 = 交易[交易["业务类型"] == "证券卖出"]["发生金额"].sum()
    总盈亏 = 卖出总金额 + 买入总金额

    # 胜率计算：按标的完整闭环计算
    盈利次数 = 0
    交易标的数 = 0
    for code in 交易["证券代码"].unique():
        sub = 交易[交易["证券代码"] == code]
        buys = sub[sub["业务类型"] == "证券买入"]
        sells = sub[sub["业务类型"] == "证券卖出"]
        if len(buys) > 0 and len(sells) > 0:
            交易标的数 += 1
            # 简单判断：单笔平均卖出价 > 单笔平均买入价
            avg_buy = abs(buys["发生金额"].sum()) / buys["成交数量"].sum()
            avg_sell = sells["发生金额"].sum() / sells["成交数量"].sum()
            if avg_sell > avg_buy:
                盈利次数 += 1
    
    胜率 = (盈利次数 / 交易标的数 * 100) if 交易标的数 > 0 else 0

    c1, c2, c3, c4 = st.columns(4)
    delta_color = "normal" if 总盈亏 >= 0 else "inverse"
    c1.metric("已实现盈亏", f"¥{总盈亏:,.2f}", delta=f"{总盈亏:+,.2f}", delta_color=delta_color)
    c2.metric("交易笔数", f"{len(交易)} 笔")
    c3.metric("胜率", f"{胜率:.1f}%")
    c4.metric("当前持仓", f"{len(最新持仓)} 只")

    # ========== 5. 5维评分与行情获取 ==========
    st.subheader("🎯 当前持仓 5 维评分")
    today_str = datetime.now().strftime("%Y%m%d")
    start_str = "20240101"

    if len(最新持仓) > 0:
        score_list = []
        bar = st.progress(0, text="正在获取行情数据并进行5维分析...")

        for i, row in 最新持仓.iterrows():
            code = row["证券代码"]
            cost = row["加权成本"]
            qty = row["净持仓"]
            name = row["证券名称"]

            hist = get_stock_hist(code, start_str, today_str)
            
            if hist is None or len(hist) < 40:
                score_list.append({
                    "代码": code, "名称": name, "数量": qty, "成本价": cost,
                    "现价": None, "市值": 0, "盈亏": 0, "盈亏率": 0, "5维评分": 0, "信号": "❌ 数据不足"
                })
                continue

            hist["日期"] = pd.to_datetime(hist["日期"])
            hist = hist.sort_values("日期").reset_index(drop=True)

            # 计算技术指标
            bbi = (hist["收盘"].rolling(3).mean() + hist["收盘"].rolling(6).mean() + 
                   hist["收盘"].rolling(12).mean() + hist["收盘"].rolling(24).mean()) / 4
            
            low_9 = hist["最低"].rolling(9).min()
            high_9 = hist["最高"].rolling(9).max()
            rsv = (hist["收盘"] - low_9) / (high_9 - low_9) * 100
            K = rsv.ewm(com=2).mean()
            D = K.ewm(com=2).mean()

            latest = hist.iloc[-1]
            prev = hist.iloc[-2]

            # 5维评分算法
            s1 = 1 if hist["最低"].tail(20).min() > hist["最低"].tail(40).head(20).min() else 0 # 趋势方向
            s2 = 1 if latest["收盘"] > bbi.iloc[-1] else 0 # 生命线
            drop_rate = (prev["收盘"] - prev["开盘"]) / prev["开盘"]
            is_vol_spike = prev["成交量"] > hist["成交量"].tail(5).mean() * 1.5
            s3 = 0 if (drop_rate < -0.03 and is_vol_spike) else 1 # 量价健康
            s4 = 1 if latest["收盘"] > hist["收盘"].tail(20).mean() else 0 # 均线向上
            s5 = 1 if K.iloc[-1] > D.iloc[-1] else 0 # KDJ健康
            
            total_score = s1 + s2 + s3 + s4 + s5
            
            # 计算当前盈亏
            price = latest["收盘"]
            market_value = price * qty
            profit = market_value - (cost * qty)
            profit_rate = (profit / (cost * qty) * 100) if cost > 0 else 0

            if total_score >= 4: signal = "🔥 重点观察"
            elif total_score >= 3: signal = "👀 观察"
            else: signal = "⚠️ 回避"

            score_list.append({
                "代码": code, "名称": name, "数量": qty, "成本价": round(cost, 2),
                "现价": round(price, 2), "市值": round(market_value, 2),
                "盈亏": round(profit, 2), "盈亏率": round(profit_rate, 2),
                "5维评分": total_score, "信号": signal
            })
            bar.progress((i + 1) / len(最新持仓))

        结果_df = pd.DataFrame(score_list)

        # 优化表格显示：正绿负红
        def color_pnl(val):
            if pd.isna(val): return ""
            color = "#00cc00" if val > 0 else ("#ff3333" if val < 0 else "black")
            return f"color: {color}; font-weight: bold; font-size: 14px;"

        st.dataframe(
            结果_df.style.format(precision=2, subset=["成本价", "现价", "市值", "盈亏", "盈亏率"])
                      .map(color_pnl, subset=["盈亏", "盈亏率"]),
            use_container_width=True, hide_index=True
        )

        # ========== 新增模块：📊 资金与图表分析 ==========
        st.divider()
        st.subheader("📊 资金分布与可视化")
        
        c1, c2 = st.columns(2)
        
        # 1. 饼图：持仓占比
        with c1:
            st.caption("💰 当前持仓市值占比")
            if not 结果_df[结果_df["市值"] > 0].empty:
                饼图数据 = 结果_df[结果_df["市值"] > 0][["名称", "市值"]].set_index("名称")["市值"]
                fig1, ax1 = plt.subplots(figsize=(8, 5))
                ax1.pie(饼图数据, labels=饼图_data.index, autopct='%1.1f%%', startangle=90)
                ax1.axis('equal')
                st.pyplot(fig1)
                plt.close(fig1)
            else:
                st.write("暂无有效市值数据")

        # 2. 柱状图：单笔盈亏排行
        with c2:
            st.caption("📊 单只股票盈亏排行")
            柱状图数据 = 结果_df[["名称", "盈亏"]].set_index("名称")["盈亏"].sort_values()
            st.bar_chart(柱状图数据, color="#FF0000" if 柱状图数据.min() < 0 else "#008000")

        # 3. 深度复盘指标（基于所有交易记录）
        st.caption("📈 交易深度复盘指标")
        buy_records = 交易[交易["业务类型"] == "证券买入"]
        sell_records = 交易[交易["业务类型"] == "证券卖出"]
        
        if len(sell_records) > 0:
            # 计算每个标的的总盈亏
            标的盈亏 = 交易.groupby("证券名称").apply(lambda x: x[x["业务类型"]=="证券卖出"]["发生金额"].sum() + x[x["业务类型"]=="证券买入"]["发生金额"].sum())
            
            盈利交易 = 标的盈亏[标的盈亏 > 0]
            亏损交易 = 标的盈亏[标的盈亏 < 0]
            
            平均盈利 = 盈利交易.mean() if len(盈利交易) > 0 else 0
            平均亏损 = abs(亏损交易.mean()) if len(亏损交易) > 0 else 0
            盈亏比 = 平均盈利 / 平均亏损 if 平均亏损 > 0 else float('inf')

            m1, m2, m3 = st.columns(3)
            m1.metric("平均单笔盈利", f"¥{平均盈利:,.2f}")
            m2.metric("平均单笔亏损", f"¥{平均亏损:,.2f}")
            m3.metric("盈亏比", f"{盈亏比:.2f}", help="大于1.5通常意味着交易系统较为健康")

        # ========== 新增模块：💡 智能操作建议 ==========
        st.divider()
        st.subheader("💡 智能操作建议")
        建议 = []
        for _, row in 结果_df.iterrows():
            code, name, score, pnl = row["代码"], row["名称"], row["5维评分"], row["盈亏"]
            
            if score >= 5 and pnl < 0:
                建议.append(f"🔔 **{name} ({code})**：5维满分但目前亏损，属于【左侧抄底】信号，可考虑分批加仓摊低成本。")
            elif score <= 2 and pnl > 0:
                建议.append(f"⚠️ **{name} ({code})**：5维低分但当前盈利，属于【高位预警】，建议设置移动止盈保护利润。")
            elif score >= 4:
                建议.append(f"🔥 **{name} ({code})**：多项指标共振向好，可列为重点观察对象，等待量能配合突破。")
                
        if not 建议:
            建议.append("👀 当前持仓均处于正常波动范围，暂无特殊操作建议，建议多看少动。")

        for msg in 建议:
            st.markdown(msg)

    else:
        st.success("当前账户无持仓，空仓状态，请继续寻找机会！")

    # ========== 6. 优化交易记录展示 ==========
    st.subheader("📝 核心交易记录")
    展示列 = ["交割日期", "证券名称", "业务类型", "成交价格", "成交数量", "发生金额"]
    交易展示 = 交易[展示列].copy()
    交易展示 = 交易展示.sort_values("交割日期", ascending=False) # 倒序排列
    交易展示 = 交易展示.reset_index(drop=True)
    
    st.dataframe(交易展示, use_container_width=True, hide_index=True)

else:
    st.info("👈 请在左侧侧边栏上传【通达信交割单.txt】文件，系统将自动为您进行多维分析")
