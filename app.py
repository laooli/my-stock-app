    # ========== 新增模块：📊 资金与图表分析 ==========
    st.divider()
    st.subheader("📊 资金分布与可视化")

    if len(最新持仓) > 0:
        # 1. 饼图：持仓占比
        c1, c2 = st.columns(2)
        
        # 准备饼图数据
        饼图数据 = 结果_df[["名称", "市值"]].set_index("名称")["市值"]
        with c1:
            st.caption("💰 当前持仓市值占比")
            st.pyplot(plt.figure(figsize=(8, 6)))  # 这里需要配合 mplfinance 或 matplotlib 的 pie 函数
            # 简化处理，直接显示表格数据作为占位
            st.table(结果_df[["名称", "市值", "成本价", "现价"]])

        # 2. 柱状图：单笔盈亏排行
        柱状图数据 = 结果_df[["名称", "盈亏"]].set_index("名称")["盈亏"].sort_values()
        with c2:
            st.caption("📊 单只股票盈亏排行")
            st.bar_chart(柱状图_data)

    # 3. 深度复盘指标（基于所有交易记录）
    st.caption("📈 交易深度复盘指标")
    buy_records = 交易[交易["业务类型"] == "证券买入"]
    sell_records = 交易[交易["业务类型"] == "证券卖出"]
    
    if len(sell_records) > 0:
        单笔盈亏 = 交易.groupby("证券代码").apply(lambda x: abs(x[x["业务类型"]=="证券卖出"]["发生金额"].sum()) + x[x["业务类型"]=="证券买入"]["发生金额"].sum())
        盈利交易 = 单笔盈亏[单笔盈亏 > 0]
        亏损交易 = 单笔盈亏[单笔盈亏 < 0]
        
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
