import streamlit as st
import pandas as pd
from io import StringIO
from google.colab import files

# ================= 1. 页面美化模板（加在最前面） =================
st.set_page_config(
    page_title="我的股票复盘分析系统",
    page_icon="📈",
    layout="wide"  # 使用宽屏，避免两边留白太多
)
hide_st_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)
st.title("📈 我的专属股票复盘工具")
st.caption("数据来源：通达信交割单 | 个人使用")
# ==============================================================

# ================= 2. 你的上传和解析代码（不用动） =================
uploaded_fund = st.sidebar.file_uploader("上传资金明细", type=["txt"])

if uploaded_fund is not None:
    try:
        fund_raw = uploaded_fund.read().decode("gbk")
    except UnicodeDecodeError:
        fund_raw = uploaded_fund.read().decode("gb18030")

    fund_df = pd.read_csv(StringIO(fund_raw), sep=r"\s+", dtype=str)
    fund_df = fund_df.dropna(how="all").reset_index(drop=True)

    # ====== 3. 这里就是美化过的“账户总览” ======
    with st.expander("🏦 点击查看账户资产总览（来自资金明细）"):
        st.dataframe(fund_df, use_container_width=True, hide_index=True)

else:
    st.info("👈 请在左侧侧边栏上传【通达信交割单.txt】文件，系统将自动为您进行多维分析")
    st.info("可选：同时上传【资金明细查询.txt】以查看账户资产总览")
股票分析系统 v3.0 - 增强版
新增功能：
  1. 交易费用明细分析（佣金/印花税/过户费）
  2. 资金余额曲线追踪
  3. 银证转账记录汇总
  4. 个股盈亏明细（含所有费用）
  5. 分红扣税记录
  6. 更强大的 pandas 数据分析
"""
import streamlit as st
import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime
import time
import random
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from io import StringIO

# 设置 matplotlib 支持中文显示
plt.rcParams['font.sans-serif'] = ['SimHei', 'WenQuanYi Zen Hei', 'Arial Unicode MS', 'sans-serif']
plt.rcParams['axes.unicode_minus'] = False

# 设置页面配置
st.set_page_config(layout="wide", page_title="我的股票分析系统", page_icon="📊")
st.title("📊 我的股票分析系统 v3.0")

# ===================================================================
# 1. 带缓存的行情获取函数（指数退避重试）
# ===================================================================
@st.cache_data(ttl=600)
def get_stock_hist(code: str, start_date: str, end_date: str) -> pd.DataFrame | None:
    """获取A股历史数据，带重试机制"""
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


# ===================================================================
# 2. 侧边栏：上传文件
# ===================================================================
st.sidebar.header("📂 上传文件")
uploaded_file = st.sidebar.file_uploader(
    "上传通达信交割单（txt）", type=["txt"]
)
uploaded_fund = st.sidebar.file_uploader(
    "上传资金明细（txt，可选）", type=["txt"]
)

if uploaded_file is not None:
    # ========== 解析交割单 ==========
    try:
        raw = uploaded_file.read().decode("gbk")
    except UnicodeDecodeError:
        try:
            raw = uploaded_file.read().decode("gb18030")
        except Exception:
            st.error("无法解析文件编码，请检查是否为通达信标准格式")
            st.stop()

    df = pd.read_csv(StringIO(raw), sep=r"\s+", skiprows=1, dtype=str)
    df = df.dropna(how="all").reset_index(drop=True)

    # 统一列名映射
    列名映射 = {
        "日期": "交割日期", "交易日期": "交割日期",
        "代码": "证券代码", "股票代码": "证券代码",
        "名称": "证券名称", "股票名称": "证券名称",
        "买卖标志": "业务类型", "买卖方向": "业务类型",
        "成交价格": "成交价格", "成交价": "成交价格",
        "成交数量": "成交数量", "成交量": "成交数量",
        "成交金额": "成交金额",
        "发生金额": "发生金额", "实际发生金额": "发生金额",
        "证券数量": "证券数量", "当前持仓": "证券数量",
        "佣金": "佣金", "印花税": "印花税", "过户费": "过户费",
        "剩余金额": "剩余金额",
    }
    df.rename(columns=列名映射, inplace=True)

    # 强制数值转换
    num_cols = ["成交价格", "成交数量", "成交金额", "发生金额", "证券数量"]
    # 费用列（可能不存在）
    fee_cols = ["佣金", "印花税", "过户费"]
    all_num_cols = num_cols + fee_cols
    for col in all_num_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
        else:
            df[col] = 0

    # 剩余金额列
    if "剩余金额" in df.columns:
        df["剩余金额"] = pd.to_numeric(df["剩余金额"], errors="coerce").fillna(0)
    else:
        df["剩余金额"] = 0

    # 交割日期转换
    if "交割日期" in df.columns:
        df["交割日期"] = pd.to_datetime(df["交割日期"], errors="coerce")
    df = df.sort_values("交割日期", na_position="last").reset_index(drop=True)

    # 筛选交易记录
    交易 = df[df["业务类型"].isin(["证券买入", "证券卖出", "买", "卖"])].copy()
    if len(交易) == 0:
        st.info("未检测到有效的证券买入/卖出交易记录")
        st.stop()

    # 统一业务类型名称
    交易["业务类型"] = 交易["业务类型"].replace({"买": "证券买入", "卖": "证券卖出"})
    交易 = 交易.sort_values("交割日期").reset_index(drop=True)

    # 筛选非交易记录
    非交易 = df[~df["业务类型"].isin(["证券买入", "证券卖出", "买", "卖"])].copy()

    # ========== 计算真实持仓和加权成本（含费用摊薄）==========
    持仓列表 = []
    for code in 交易["证券代码"].unique():
        sub = 交易[交易["证券代码"] == code].sort_values("交割日期")
        买入记录 = sub[sub["业务类型"] == "证券买入"]
        卖出记录 = sub[sub["业务类型"] == "证券卖出"]

        买入总量 = 买入记录["成交数量"].sum()
        卖出总量 = 卖出记录["成交数量"].sum()
        净持仓 = 买入总量 - 卖出总量

        if 净持仓 > 0:
            # 加权平均成本（含买入费用摊入成本）
            买入总成交金额 = (买入记录["成交价格"] * 买入记录["成交数量"]).sum()
            买入总费用 = 买入记录.get("佣金", pd.Series([0]*len(买入记录))).sum() + \
                         买入记录.get("印花税", pd.Series([0]*len(买入记录))).sum() + \
                         买入记录.get("过户费", pd.Series([0]*len(买入记录))).sum()
            买入总成本 = 买入总成交金额 + 买入总费用
            加权成本 = 买入总成本 / 买入总量 if 买入总量 > 0 else 0

            持仓列表.append({
                "证券代码": str(code).zfill(6),
                "证券名称": sub.iloc[-1]["证券名称"],
                "净持仓": int(净持仓),
                "加权成本": round(加权成本, 3),
                "买入总费用": round(买入总费用, 2),
            })

    最新持仓 = pd.DataFrame(持仓列表) if 持仓列表 else pd.DataFrame()

    # ========== 账户总览 ==========
    st.subheader("📈 账户总览")

    # 总盈亏 = 卖出总收入 + 买入总支出（发生金额：买入为负，卖出为正）
    买入总金额 = 交易[交易["业务类型"] == "证券买入"]["发生金额"].sum()
    卖出总金额 = 交易[交易["业务类型"] == "证券卖出"]["发生金额"].sum()
    已实现盈亏 = 卖出总金额 + 买入总金额

    # 胜率计算
    盈利次数 = 0
    交易标的数 = 0
    for code in 交易["证券代码"].unique():
        sub = 交易[交易["证券代码"] == code]
        buys = sub[sub["业务类型"] == "证券买入"]
        sells = sub[sub["业务类型"] == "证券卖出"]
        if len(buys) > 0 and len(sells) > 0:
            交易标的数 += 1
            avg_buy = abs(buys["发生金额"].sum()) / buys["成交数量"].sum()
            avg_sell = sells["发生金额"].sum() / sells["成交数量"].sum()
            if avg_sell > avg_buy:
                盈利次数 += 1

    胜率 = (盈利次数 / 交易标的数 * 100) if 交易标的数 > 0 else 0

    # 总费用统计
    总佣金 = 交易["佣金"].sum()
    总印花税 = 交易["印花税"].sum()
    总过户费 = 交易["过户费"].sum()
    总交易费用 = 总佣金 + 总印花税 + 总过户费

    c1, c2, c3, c4 = st.columns(4)
    delta_color = "normal" if 已实现盈亏 >= 0 else "inverse"
    c1.metric("已实现盈亏", f"¥{已实现盈亏:,.2f}", delta=f"{已实现盈亏:+,.2f}", delta_color=delta_color)
    c2.metric("交易笔数", f"{len(交易)} 笔")
    c3.metric("胜率", f"{胜率:.1f}%")
    c4.metric("当前持仓", f"{len(最新持仓)} 只")

    # 费用概览行
    st.caption(f"📊 本期交易总费用：佣金 ¥{总佣金:.2f} | 印花税 ¥{总印花税:.2f} | 过户费 ¥{总过户费:.2f} | 合计 ¥{总交易费用:.2f}")

    # ========== 5维评分与行情获取 ==========
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
            s1 = 1 if hist["最低"].tail(20).min() > hist["最低"].tail(40).head(20).min() else 0
            s2 = 1 if latest["收盘"] > bbi.iloc[-1] else 0
            drop_rate = (prev["收盘"] - prev["开盘"]) / prev["开盘"]
            is_vol_spike = prev["成交量"] > hist["成交量"].tail(5).mean() * 1.5
            s3 = 0 if (drop_rate < -0.03 and is_vol_spike) else 1
            s4 = 1 if latest["收盘"] > hist["收盘"].tail(20).mean() else 0
            s5 = 1 if K.iloc[-1] > D.iloc[-1] else 0

            total_score = s1 + s2 + s3 + s4 + s5

            # 计算当前盈亏（基于含费用的成本价）
            price = latest["收盘"]
            market_value = price * qty
            profit = market_value - (cost * qty)
            profit_rate = (profit / (cost * qty) * 100) if cost > 0 else 0

            if total_score >= 4:
                signal = "🔥 重点观察"
            elif total_score >= 3:
                signal = "👀 观察"
            else:
                signal = "⚠️ 回避"

            score_list.append({
                "代码": code, "名称": name, "数量": qty, "成本价": round(cost, 2),
                "现价": round(price, 2), "市值": round(market_value, 2),
                "盈亏": round(profit, 2), "盈亏率": round(profit_rate, 2),
                "5维评分": total_score, "信号": signal
            })
            bar.progress((i + 1) / len(最新持仓))

        结果_df = pd.DataFrame(score_list)

        # 优化表格显示
        def color_pnl(val):
            if pd.isna(val):
                return ""
            if val > 0:
                return "color:#00cc00;font-weight:bold"
            elif val < 0:
                return "color:#ff3333;font-weight:bold"
            return ""

        st.dataframe(
            结果_df.style.format(precision=2, subset=["成本价", "现价", "市值", "盈亏", "盈亏率"])
                      .map(color_pnl, subset=["盈亏", "盈亏率"]),
            use_container_width=True, hide_index=True
        )

        # ===================================================================
        # 新增模块：资金分布与可视化
        # ===================================================================
        st.divider()
        st.subheader("📊 资金分布与可视化")

        c_chart1, c_chart2 = st.columns(2)

        # 1. 饼图：持仓占比
        with c_chart1:
            st.caption("💰 当前持仓市值占比")
            持仓有效 = 结果_df[结果_df["市值"] > 0]
            if not 持仓有效.empty:
                饼图数据 = 持仓有效.set_index("名称")["市值"]
                fig1, ax1 = plt.subplots(figsize=(7, 5))
                colors = plt.cm.Set3(np.linspace(0, 1, len(饼图数据)))
                wedges, texts, autotexts = ax1.pie(
                    饼图数据, labels=饼图数据.index, autopct='%1.1f%%',
                    startangle=90, colors=colors,
                    textprops={'fontsize': 11}
                )
                ax1.set_title('持仓市值占比')
                st.pyplot(fig1)
                plt.close(fig1)
            else:
                st.write("暂无有效市值数据")

        # 2. 柱状图：持仓盈亏排行
        with c_chart2:
            st.caption("📊 持仓盈亏排行")
            持仓有效2 = 结果_df[结果_df["市值"] > 0]
            if not 持仓有效2.empty:
                盈亏数据 = 持仓有效2.set_index("名称")["盈亏"].sort_values()
                fig2, ax2 = plt.subplots(figsize=(7, 5))
                bar_colors = ['#00cc00' if v >= 0 else '#ff3333' for v in 盈亏数据]
                ax2.barh(盈亏数据.index, 盈亏数据.values, color=bar_colors)
                ax2.set_xlabel('盈亏（元）')
                ax2.set_title('持仓盈亏排行')
                ax2.axvline(x=0, color='gray', linestyle='--', alpha=0.5)
                st.pyplot(fig2)
                plt.close(fig2)
            else:
                st.write("暂无有效数据")

        # ===================================================================
        # 新增模块：交易费用深度分析
        # ===================================================================
        st.divider()
        st.subheader("💸 交易费用深度分析")

        # 费用明细表
        费用明细 = 交易[["交割日期", "证券名称", "业务类型", "成交价格", "成交数量", "佣金", "印花税", "过户费"]].copy()
        费用明细["单笔总费用"] = 费用明细["佣金"] + 费用明细["印花税"] + 费用明细["过户费"]
        费用明细 = 费用明细.sort_values("交割日期", ascending=False).reset_index(drop=True)

        st.write("**逐笔费用明细：**")
        st.dataframe(
            费用明细.style.format(precision=2),
            use_container_width=True, hide_index=True
        )

        # 费用占比分析
        st.write("**费用占比分析：**")
        c_fee1, c_fee2 = st.columns(2)
        with c_fee1:
            买入交易 = 交易[交易["业务类型"] == "证券买入"]
            卖出交易 = 交易[交易["业务类型"] == "证券卖出"]

            买入总成交 = (买入交易["成交价格"] * 买入交易["成交数量"]).sum()
            卖出总成交 = (卖出交易["成交价格"] * 卖出交易["成交数量"]).sum()

            买入费用率 = 总佣金 / 买入总成交 * 100 if 买入总成交 > 0 else 0
            卖出费用率 = (卖出交易["佣金"].sum() + 卖出交易["印花税"].sum() + 卖出交易["过户费"].sum()) / 卖出总成交 * 100 if 卖出总成交 > 0 else 0

            st.metric("买入平均费用率", f"{买入费用率:.3f}%")
            st.metric("卖出平均费用率", f"{卖出费用率:.3f}%")

        with c_fee2:
            # 各股票费用排行
            个股费用 = 交易.groupby("证券名称").agg(
                总佣金=("佣金", "sum"),
                总印花税=("印花税", "sum"),
                总过户费=("过户费", "sum"),
            ).reset_index()
            个股费用["总费用"] = 个股费用["总佣金"] + 个股费用["总印花税"] + 个股费用["总过户费"]
            个股费用 = 个股费用.sort_values("总费用", ascending=False).reset_index(drop=True)

            if not 个股费用.empty:
                st.dataframe(
                    个股费用.style.format(precision=2),
                    use_container_width=True, hide_index=True
                )

        # ===================================================================
        # 新增模块：资金余额曲线
        # ===================================================================
        st.divider()
        st.subheader("📉 资金余额变化曲线")

        if "剩余金额" in df.columns and df["剩余金额"].notna().sum() > 2:
            # 过滤有剩余金额的行
            资金曲线 = df[df["剩余金额"] > 0][["交割日期", "剩余金额", "业务类型"]].copy()
            资金曲线 = 资金曲线.sort_values("交割日期").reset_index(drop=True)

            if len(资金曲线) > 1:
                fig3, ax3 = plt.subplots(figsize=(10, 5))
                ax3.plot(资金曲线["交割日期"], 资金曲线["剩余金额"], marker='o', linewidth=2, color='#2196F3')
                ax3.fill_between(资金曲线["交割日期"], 资金曲线["剩余金额"], alpha=0.1, color='#2196F3')
                ax3.set_xlabel('日期')
                ax3.set_ylabel('剩余金额（元）')
                ax3.set_title('账户剩余金额变化趋势')
                ax3.grid(True, alpha=0.3)
                # 标注特殊事件
                for _, row in 资金曲线.iterrows():
                    bt = str(row.get("业务类型", ""))
                    if "转银行" in bt or "股息" in str(row.get("业务类型", "")):
                        ax3.annotate(f'{bt}', xy=(row["交割日期"], row["剩余金额"]),
                                     textcoords="offset points", xytext=(0, 15),
                                     ha='center', fontsize=9, color='red')
                st.pyplot(fig3)
                plt.close(fig3)

                st.write(f"**当前剩余金额：¥{资金曲线.iloc[-1]['剩余金额']:,.2f}**")
            else:
                st.info("剩余金额数据不足，无法绘制曲线")
        else:
            st.info("交割单中未包含剩余金额列，无法绘制资金曲线")

        # ===================================================================
        # 新增模块：银证转账与非交易记录
        # ===================================================================
        st.divider()
        st.subheader("🏦 银证转账与非交易记录")

        # 银证转账
        转账记录 = 非交易[非交易["业务类型"].str.contains("转银行", na=False)].copy() if len(非交易) > 0 else pd.DataFrame()
        if len(转账记录) > 0:
            st.write("**银证转账记录：**")
            转账展示 = 转账记录[["交割日期", "发生金额", "剩余金额"]].copy()
            转账展示.columns = ["日期", "转账金额", "转账后余额"]
            转账展示["转账金额"] = 转账展示["转账金额"].apply(lambda x: f"¥{x:,.2f}" if not pd.isna(x) else "")
            st.dataframe(转账展示, use_container_width=True, hide_index=True)

            # 转账汇总
            转入总额 = 转账记录[转账记录["发生金额"] > 0]["发生金额"].sum()
            转出总额 = abs(转账记录[转账记录["发生金额"] < 0]["发生金额"].sum())
            st.caption(f"累计转入：¥{转入总额:,.2f} | 累计转出：¥{转出总额:,.2f} | 净额：¥{转入总额 - 转出总额:,.2f}")
        else:
            st.caption("本期无银证转账记录")

        # 分红/扣税/利息
        其他记录 = 非交易[~非交易["业务类型"].str.contains("转银行", na=False)].copy() if len(非交易) > 0 else pd.DataFrame()
        if len(其他记录) > 0:
            st.write("**其他资金变动（分红/扣税/利息等）：**")
            其他展示 = 其他记录[["交割日期", "证券名称", "业务类型", "发生金额"]].copy()
            st.dataframe(其他展示, use_container_width=True, hide_index=True)

        # ===================================================================
        # 新增模块：个股盈亏明细（含费用）
        # ===================================================================
        st.divider()
        st.subheader("📋 个股盈亏明细（含交易费用）")

        个股明细列表 = []
        for code in 交易["证券代码"].unique():
            sub = 交易[交易["证券代码"] == code].sort_values("交割日期")
            名称 = sub.iloc[-1]["证券名称"]
            buys = sub[sub["业务类型"] == "证券买入"]
            sells = sub[sub["业务类型"] == "证券卖出"]

            if len(buys) > 0 and len(sells) > 0:
                买入总成交 = (buys["成交价格"] * buys["成交数量"]).sum()
                买入总费用 = buys.get("佣金", pd.Series([0]*len(buys))).sum() + \
                             buys.get("印花税", pd.Series([0]*len(buys))).sum() + \
                             buys.get("过户费", pd.Series([0]*len(buys))).sum()
                买入总成本 = 买入总成交 + 买入总费用
                买入均价 = 买入总成本 / buys["成交数量"].sum() if buys["成交数量"].sum() > 0 else 0

                卖出总成交 = (sells["成交价格"] * sells["成交数量"]).sum()
                卖出总费用 = sells.get("佣金", pd.Series([0]*len(sells))).sum() + \
                             sells.get("印花税", pd.Series([0]*len(sells))).sum() + \
                             sells.get("过户费", pd.Series([0]*len(sells))).sum()
                卖出净收入 = 卖出总成交 - 卖出总费用
                卖出均价 = 卖出净收入 / sells["成交数量"].sum() if sells["成交数量"].sum() > 0 else 0

                盈亏 = 卖出净收入 - 买入总成本
                盈亏率 = 盈亏 / 买入总成本 * 100 if 买入总成本 > 0 else 0
                总费用 = 买入总费用 + 卖出总费用

                个股明细列表.append({
                    "证券代码": str(code).zfill(6),
                    "证券名称": 名称,
                    "买入总成本": round(买入总成本, 2),
                    "买入总费用": round(买入总费用, 2),
                    "卖出净收入": round(卖出净收入, 2),
                    "卖出总费用": round(卖出总费用, 2),
                    "净盈亏": round(盈亏, 2),
                    "盈亏率": round(盈亏率, 2),
                    "总交易费用": round(总费用, 2),
                })

        if 个股明细列表:
            个股明细_df = pd.DataFrame(个股明细列表)
            st.dataframe(
                个股明细_df.style.format(precision=2)
                         .map(color_pnl, subset=["净盈亏", "盈亏率"]),
                use_container_width=True, hide_index=True
            )
        else:
            st.info("暂无完整的买卖闭环数据")

        # ===================================================================
        # 新增模块：智能操作建议
        # ===================================================================
        st.divider()
        st.subheader("💡 智能操作建议")
        建议 = []
        if len(结果_df) > 0:
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

    # ===================================================================
    # 交易记录展示
    # ===================================================================
    st.subheader("📝 核心交易记录")
    展示列 = ["交割日期", "证券名称", "业务类型", "成交价格", "成交数量", "发生金额", "佣金", "印花税", "过户费"]
    可用列 = [c for c in 展示列 if c in 交易.columns]
    交易展示 = 交易[可用列].copy()
    交易展示 = 交易展示.sort_values("交割日期", ascending=False).reset_index(drop=True)

    st.dataframe(交易展示, use_container_width=True, hide_index=True)

    # ===================================================================
    # 可选：读取资金明细文件
    # ===================================================================
    if uploaded_fund is not None:
        try:
            fund_raw = uploaded_fund.read().decode("gbk")
        except UnicodeDecodeError:
            fund_raw = uploaded_fund.read().decode("gb18030")

        fund_df = pd.read_csv(StringIO(fund_raw), sep=r"\s+", dtype=str)
        fund_df = fund_df.dropna(how="all").reset_index(drop=True)

        st.divider()
        st.subheader("🏦 账户资产总览（来自资金明细）")
        st.dataframe(fund_df, use_container_width=True, hide_index=True)

else:
    st.info("👈 请在左侧侧边栏上传【通达信交割单.txt】文件，系统将自动为您进行多维分析")
    st.info("可选：同时上传【资金明细查询.txt】以查看账户资产总览")
st.divider()
st.subheader("📊 本月盈亏比分析（自动计算）")

# 把数据按股票代码和名称分组，算出总买入和总卖出
df["发生金额"] = df["发生金额"].astype(float)

# 找出所有买入和卖出的记录
buy_df = df[df["业务类型"].str.contains("买入")].groupby("证券名称")["发生金额"].sum().abs()
sell_df = df[df["业务类型"].str.contains("卖出")].groupby("证券名称")["发生金额"].sum()

# 算出每只股票的盈亏（卖出 - 买入）
profit_df = pd.DataFrame({"总买入": buy_df, "总卖出": sell_df}).fillna(0)
profit_df["盈亏"] = profit_df["总卖出"] - profit_df["总买入"]

st.dataframe(profit_df, use_container_width=True)

# 统计盈利和亏损
wins = profit_df[profit_df["盈亏"] > 0]["盈亏"]
losses = profit_df[profit_df["盈亏"] < 0]["盈亏"]

if len(wins) > 0 and len(losses) > 0:
    avg_win = wins.mean()
    avg_loss = abs(losses.mean())
    ratio = avg_win / avg_loss
    st.success(f"✅ 本月平均盈利：{avg_win:.2f} 元")
    st.error(f"❌ 本月平均亏损：{avg_loss:.2f} 元")
    st.info(f"📈 本月盈亏比：{ratio:.2f} （平均盈利 ÷ 平均亏损）")
else:
    st.warning("数据不够，暂时无法计算盈亏比（需要至少一笔盈利和一笔亏损）")
