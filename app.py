# -*- coding: utf-8 -*-
"""
微信盒子代理商奖励分析平台
==========================
Streamlit Web 应用
启动方式：
  /Users/fournine/.workbuddy/binaries/python/envs/wb-analysis/bin/streamlit run app.py
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

# 允许 `streamlit run app.py` 时也能找到 core 包
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from core import analyzer, data_loader, policy as P

# ---------------------------------------------------------------------------
# 页面配置
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="微信盒子代理商奖励分析",
    page_icon="📦",
    layout="wide",
)

st.title("📦 微信盒子代理商奖励分析平台")
st.caption("基于发货数据 + 微信后台激活数据，匹配每个代理商的拿货量与三类奖励达标情况")


# ---------------------------------------------------------------------------
# 侧边栏 - 政策摘要与参数调整
# ---------------------------------------------------------------------------

with st.sidebar:
    st.header("📜 政策摘要")
    with st.expander("查看完整政策", expanded=False):
        st.markdown(P.POLICY_SUMMARY)

    st.divider()
    st.header("⚙️ 政策参数")
    with st.expander("调整政策门槛", expanded=False):
        st.caption("参数调整后需重新运行分析")
        c1, c2 = st.columns(2)
        landing_min_orders = c1.number_input(
            "落地 - 最低订单数", value=P.LANDING_MIN_ORDERS, step=50
        )
        landing_min_users = c2.number_input(
            "落地 - 最低月活用户", value=P.LANDING_MIN_ACTIVE_USERS, step=5
        )
        activity_min_orders = c1.number_input(
            "活跃/激活达标 - 最低订单数", value=P.ACTIVATION_MIN_ORDERS, step=50
        )
        activity_min_users = c2.number_input(
            "活跃/激活达标 - 最低月活用户", value=P.ACTIVATION_MIN_ACTIVE_USERS, step=5
        )
        activity_min_days = c1.number_input(
            "激活达标 - 最低有效天数", value=P.ACTIVATION_MIN_ACTIVE_DAYS, step=1
        )
        inst_th = c2.number_input(
            "机构激活总数门槛", value=P.INSTITUTION_ACTIVATION_THRESHOLD, step=1000
        )
        non_inst_th = c1.number_input(
            "非机构激活总数门槛", value=P.NON_INSTITUTION_ACTIVATION_THRESHOLD, step=1000
        )
        activity_rate = c2.number_input(
            "活跃抽成比例 (%)", value=P.ACTIVITY_FEE_RATE * 100, step=0.01, format="%.2f"
        ) / 100.0

        # 写回 policy 模块
        P.LANDING_MIN_ORDERS = landing_min_orders
        P.LANDING_MIN_ACTIVE_USERS = landing_min_users
        P.ACTIVATION_MIN_ORDERS = activity_min_orders
        P.ACTIVATION_MIN_ACTIVE_USERS = activity_min_users
        P.ACTIVATION_MIN_ACTIVE_DAYS = activity_min_days
        P.INSTITUTION_ACTIVATION_THRESHOLD = inst_th
        P.NON_INSTITUTION_ACTIVATION_THRESHOLD = non_inst_th
        P.ACTIVITY_FEE_RATE = activity_rate


# ---------------------------------------------------------------------------
# 数据上传
# ---------------------------------------------------------------------------

st.subheader("1️⃣ 上传数据文件")

col1, col2 = st.columns(2)

with col1:
    st.markdown("**📋 发货数据** （含 SN + 备注）")
    shipping_file = st.file_uploader(
        "上传发货 Excel/CSV",
        type=["xlsx", "xls", "csv"],
        key="shipping",
    )

with col2:
    st.markdown("**📡 微信后台激活数据** （每日下载的激活明细）")
    activation_file = st.file_uploader(
        "上传激活 Excel/CSV",
        type=["xlsx", "xls", "csv"],
        key="activation",
    )
    snapshot_mode = st.radio(
        "日数据聚合方式",
        options=["latest", "sum"],
        format_func=lambda x: {
            "latest": "📸 取最新一天（每日快照型）",
            "sum": "➕ 全部行累加（每日增量型）",
        }[x],
        index=0,
        help=(
            "若每日下载的是「设备当前累计状态」快照,选 latest；"
            "若是「每日新发生订单/激活」事件,选 sum。"
        ),
        horizontal=True,
        key="snapshot_mode",
    )

# 加载示例数据
st.markdown("—")
col3, col4, col5 = st.columns([1, 1, 4])
with col3:
    use_sample = st.button("🧪 使用示例数据演示", use_container_width=True)
with col4:
    clear_cache = st.button("🗑️ 清除缓存", use_container_width=True)

if clear_cache:
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()


# ---------------------------------------------------------------------------
# 加载数据
# ---------------------------------------------------------------------------

shipping_df = None
activation_df = None
shipping_msg = None
activation_msg = None

if use_sample:
    sample_dir = Path(__file__).parent / "sample_data"
    shipping_path = sample_dir / "发货数据-示例.csv"
    activation_path = sample_dir / "激活数据-示例.csv"
    if shipping_path.exists() and activation_path.exists():
        shipping_df = data_loader.load_shipping_data(str(shipping_path))
        activation_df = data_loader.load_activation_data(
            str(activation_path), snapshot_mode=snapshot_mode
        )
        shipping_msg = f"✅ 已加载示例发货数据 {len(shipping_df)} 行"
        activation_msg = f"✅ 已加载示例激活数据 {len(activation_df)} 行"
    else:
        st.error(f"示例数据不存在：{sample_dir}")

if shipping_file is not None:
    try:
        shipping_df = data_loader.load_shipping_data(shipping_file)
        shipping_msg = f"✅ 发货数据：{len(shipping_df)} 行，列：{list(shipping_df.columns)}"
    except Exception as e:
        st.error(f"❌ 发货数据加载失败：{e}")

if activation_file is not None:
    try:
        activation_df = data_loader.load_activation_data(
            activation_file, snapshot_mode=snapshot_mode
        )
        activation_msg = f"✅ 激活数据：{len(activation_df)} 行"
    except Exception as e:
        st.error(f"❌ 激活数据加载失败：{e}")

if shipping_msg:
    st.success(shipping_msg)
if activation_msg:
    st.success(activation_msg)


# ---------------------------------------------------------------------------
# 调试：列识别提示
# ---------------------------------------------------------------------------

if shipping_file or activation_file or use_sample:
    with st.expander("🔍 已识别的列（调试用）", expanded=False):
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**发货数据**")
            try:
                if shipping_file:
                    shipping_file.seek(0)
                if shipping_df is not None and not shipping_df.empty:
                    raw = pd.read_excel(shipping_file) if (shipping_file and shipping_file.name.endswith(('xlsx', 'xls'))) else None
                    if raw is not None:
                        st.json(data_loader.detect_columns(raw))
                elif use_sample:
                    raw = pd.read_csv(Path(__file__).parent / "sample_data" / "发货数据-示例.csv")
                    st.json(data_loader.detect_columns(raw))
            except Exception as e:
                st.write(str(e))
        with c2:
            st.markdown("**激活数据**")
            try:
                if activation_file:
                    activation_file.seek(0)
                if activation_df is not None and not activation_df.empty:
                    raw = pd.read_excel(activation_file) if (activation_file and activation_file.name.endswith(('xlsx', 'xls'))) else None
                    if raw is not None:
                        st.json(data_loader.detect_columns(raw))
                elif use_sample:
                    raw = pd.read_csv(Path(__file__).parent / "sample_data" / "激活数据-示例.csv")
                    st.json(data_loader.detect_columns(raw))
            except Exception as e:
                st.write(str(e))


# ---------------------------------------------------------------------------
# 运行分析
# ---------------------------------------------------------------------------

st.subheader("2️⃣ 运行分析")

run_btn = st.button(
    "🚀 开始分析",
    type="primary",
    disabled=(shipping_df is None or activation_df is None),
)

if run_btn and shipping_df is not None and activation_df is not None:
    with st.spinner("正在分析中..."):
        try:
            per_device, per_agent, summary = analyzer.analyze(
                shipping_df, activation_df
            )
            st.session_state["per_device"] = per_device
            st.session_state["per_agent"] = per_agent
            st.session_state["summary"] = summary
        except Exception as e:
            st.error(f"❌ 分析失败：{e}")
            st.exception(e)

# 从缓存中取结果
per_device = st.session_state.get("per_device")
per_agent = st.session_state.get("per_agent")
summary = st.session_state.get("summary")


# ---------------------------------------------------------------------------
# 展示结果
# ---------------------------------------------------------------------------

if summary is not None:

    st.subheader("3️⃣ 全局汇总")

    # 漏斗图
    fig_funnel = go.Figure(go.Funnel(
        y=["拿货总数", "已激活数量", "落地达标数量", "活跃达标数量", "激活达标奖励数量"],
        x=[
            summary["拿货总数"],
            summary["已激活数量"],
            summary["落地达标数量"],
            summary["活跃达标数量"],
            summary["激活达标奖励数量"],
        ],
        textinfo="value+text",
        marker_color=["#4C9AFF", "#36B37E", "#FFAB00", "#FF6B6B", "#9B59B6"],
    ))
    fig_funnel.update_layout(height=360, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig_funnel, use_container_width=True)

    # 配对数据（4 行漏斗）
    _c1, _c2 = st.columns(2)
    _c1.metric("📦 总拿货数", f"{summary['拿货总数']:,}")
    _c2.metric("👥 代理商数", f"{summary['代理商数量']:,}")

    _c3, _c4 = st.columns(2)
    _c3.metric("🟢 已激活数", f"{summary['已激活数量']:,}")
    _c4.metric("🔴 未激活数", f"{summary['未激活数量']:,}")

    _c5, _c6 = st.columns(2)
    _c5.metric("🎯 落地达标数", f"{summary['落地达标数量']:,}")
    _c6.metric("📈 活跃达标数", f"{summary['活跃达标数量']:,}")

    _c7, _ = st.columns(2)
    _c7.metric("🏆 激活达标奖励数", f"{summary['激活达标奖励数量']:,}")

    # ---------- 图表区 ----------
    st.divider()
    st.subheader("4️⃣ 可视化分析")

    tab0, tab1, tab2, tab3 = st.tabs([
        "📊 代理商汇总概览",
        "🎯 三项奖励达标分布",
        "📊 代理商排行",
        "💰 奖励金额构成",
    ])

    # ---- 代理商汇总概览（含达标率） ----
    with tab0:
        # 全局达标率概览
        st.markdown("**全局达标率概览**")
        _total = max(summary["拿货总数"], 1)
        _act = max(summary["已激活数量"], 1)
        rc1, rc2, rc3 = st.columns(3)
        rc1.metric(
            "激活率",
            f"{summary['已激活数量']/_total*100:.1f}%",
            f"{summary['已激活数量']:,} / {summary['拿货总数']:,}",
        )
        rc2.metric(
            "落地达标率",
            f"{summary['落地达标数量']/_act*100:.1f}%",
            f"{summary['落地达标数量']:,} / {summary['已激活数量']:,}",
        )
        rc3.metric(
            "活跃达标率",
            f"{summary['活跃达标数量']/_act*100:.1f}%",
            f"{summary['活跃达标数量']:,} / {summary['已激活数量']:,}",
        )

        st.divider()

        # 每个代理商的达标率
        agent_view = per_agent.copy()
        agent_view["激活率(%)"] = (
            agent_view["已激活数量"] / agent_view["拿货数量"].clip(lower=1) * 100
        ).round(1)
        agent_view["落地达标率(%)"] = (
            agent_view["落地达标数量"] / agent_view["已激活数量"].clip(lower=1) * 100
        ).round(1)
        agent_view["活跃达标率(%)"] = (
            agent_view["活跃达标数量"] / agent_view["已激活数量"].clip(lower=1) * 100
        ).round(1)

        rate_display_cols = [
            "代理商", "代理商编号", "业务线", "销售",
            "拿货数量", "已激活数量", "激活率(%)",
            "落地达标数量", "落地达标率(%)",
            "活跃达标数量", "活跃达标率(%)",
        ]
        st.markdown("**代理商达标率明细**")
        st.dataframe(
            agent_view[rate_display_cols],
            use_container_width=True,
            hide_index=True,
        )

        st.divider()

        # 达标率排行图表
        top_n_rate = st.slider("图表显示 Top N", 5, 50, 15, key="rate_top_n")

        cc1, cc2 = st.columns(2)
        with cc1:
            st.markdown("**激活率排行**（已激活 / 拿货）")
            d1 = agent_view.sort_values("激活率(%)", ascending=False).head(top_n_rate)
            fig_r1 = px.bar(
                d1, x="激活率(%)", y="代理商", orientation="h",
                color="激活率(%)", color_continuous_scale="Greens",
                height=max(380, top_n_rate * 22),
            )
            fig_r1.update_layout(yaxis=dict(autorange="reversed"))
            st.plotly_chart(fig_r1, use_container_width=True)

        with cc2:
            st.markdown("**落地达标率排行**（落地达标 / 已激活）")
            d2 = agent_view[agent_view["已激活数量"] > 0].sort_values(
                "落地达标率(%)", ascending=False
            ).head(top_n_rate)
            fig_r2 = px.bar(
                d2, x="落地达标率(%)", y="代理商", orientation="h",
                color="落地达标率(%)", color_continuous_scale="Blues",
                height=max(380, top_n_rate * 22),
            )
            fig_r2.update_layout(yaxis=dict(autorange="reversed"))
            st.plotly_chart(fig_r2, use_container_width=True)

        st.markdown("**活跃达标率排行**（活跃达标 / 已激活）")
        d3 = agent_view[agent_view["已激活数量"] > 0].sort_values(
            "活跃达标率(%)", ascending=False
        ).head(top_n_rate)
        fig_r3 = px.bar(
            d3, x="活跃达标率(%)", y="代理商", orientation="h",
            color="活跃达标率(%)", color_continuous_scale="Oranges",
            height=max(380, top_n_rate * 22),
        )
        fig_r3.update_layout(yaxis=dict(autorange="reversed"))
        st.plotly_chart(fig_r3, use_container_width=True)

    with tab1:
        st.markdown("**三项奖励达标数量对比**")
        fig = go.Figure(data=[
            go.Bar(
                name="达标数量",
                x=["落地技术服务费", "活跃技术服务费", "激活达标技术服务费"],
                y=[
                    summary['落地达标数量'],
                    summary['活跃达标数量'],
                    summary['激活达标奖励数量'],
                ],
                text=[
                    f"{summary['落地达标数量']:,}",
                    f"{summary['活跃达标数量']:,}",
                    f"{summary['激活达标奖励数量']:,}",
                ],
                textposition="outside",
                marker_color=["#4C9AFF", "#36B37E", "#FFAB00"],
            ),
        ])
        fig.update_layout(
            yaxis_title="达标设备数（台）",
            showlegend=False,
            height=420,
        )
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("**达标率（占已激活数量）**")
        activated = max(summary['已激活数量'], 1)
        rates = {
            "落地达标率": summary['落地达标数量'] / activated,
            "活跃达标率": summary['活跃达标数量'] / activated,
            "激活达标率": summary['激活达标奖励数量'] / activated,
        }
        rdf = pd.DataFrame(
            [{"奖励": k, "达标率": f"{v*100:.1f}%"} for k, v in rates.items()]
        )
        st.dataframe(rdf, use_container_width=True, hide_index=True)

    with tab2:
        st.markdown("**代理商奖励排行**（按预计总奖励排序）")
        top_n = st.slider("显示 Top N", 5, 50, 20, key="top_n")
        sort_col = st.selectbox(
            "排序依据",
            ["预计总奖励", "拿货数量", "落地达标数量",
             "活跃达标数量", "激活达标实际奖励数量"],
        )
        if not per_agent.empty:
            top_df = per_agent.sort_values(sort_col, ascending=False).head(top_n)
            fig = px.bar(
                top_df,
                x=sort_col,
                y=top_df["代理商"],
                orientation="h",
                color=sort_col,
                color_continuous_scale="Blues",
                height=max(380, top_n * 22),
            )
            fig.update_layout(yaxis=dict(autorange="reversed"))
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(
                per_agent.sort_values(sort_col, ascending=False),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("无代理商数据")

    with tab3:
        st.markdown("**奖励金额构成（饼图）**")
        fig = go.Figure(data=[go.Pie(
            labels=["落地费", "活跃费", "激活达标费"],
            values=[
                summary['落地费总额'],
                summary['活跃费总额'],
                summary['激活达标费总额'],
            ],
            hole=.5,
            marker=dict(colors=["#4C9AFF", "#36B37E", "#FFAB00"]),
        )])
        fig.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig, use_container_width=True)

    # ---------- 明细数据 ----------
    st.divider()
    st.subheader("5️⃣ 明细数据 & 下载")

    tab_d1, tab_d2 = st.tabs(["按代理商", "按设备明细"])

    with tab_d1:
        st.dataframe(per_agent, use_container_width=True, hide_index=True)

    with tab_d2:
        show_cols = [
            "sn", "agent_name", "biz_line", "sales",
            "agent_id", "iccid", "imei",
            "is_activated", "monthly_orders", "monthly_amount",
            "monthly_active_users", "monthly_active_days",
            "is_landing_eligible", "landing_fee",
            "activity_fee",
            "is_activation_eligible", "is_institution",
            "activation_threshold_open", "activation_fee",
            "total_reward",
            "batch_no",
        ]
        existing = [c for c in show_cols if c in per_device.columns]
        st.dataframe(per_device[existing], use_container_width=True, hide_index=True)

        # 过滤
        f1, f2 = st.columns(2)
        with f1:
            eligible_options = st.multiselect(
                "筛选达标奖励",
                ["落地达标", "活跃达标", "激活达标", "未激活"],
                default=[],
            )
        with f2:
            agents_filter = st.multiselect(
                "按代理商筛选",
                options=sorted(per_device["agent_name"].dropna().unique().tolist()),
                default=[],
            )

        filtered = per_device.copy()
        if agents_filter:
            filtered = filtered[filtered["agent_name"].isin(agents_filter)]
        if eligible_options:
            mask = pd.Series(False, index=filtered.index)
            if "落地达标" in eligible_options:
                mask |= filtered["is_landing_eligible"]
            if "活跃达标" in eligible_options:
                mask |= filtered["is_activation_eligible"]
            if "激活达标" in eligible_options:
                mask |= (filtered["activation_fee"] > 0)
            if "未激活" in eligible_options:
                mask |= ~filtered["is_activated"]
            filtered = filtered[mask]

        st.dataframe(
            filtered[[c for c in existing if c in filtered.columns]],
            use_container_width=True,
            hide_index=True,
        )

    # ---------- 下载 ----------
    st.divider()
    st.subheader("6️⃣ 下载分析结果")

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        per_agent.to_excel(writer, sheet_name="按代理商", index=False)
        per_device[existing].to_excel(writer, sheet_name="设备明细", index=False)
        pd.DataFrame([summary]).T.rename(columns={0: "值"}).to_excel(
            writer, sheet_name="全局汇总"
        )
    st.download_button(
        label="📥 下载完整分析结果（Excel）",
        data=buffer.getvalue(),
        file_name=f"微信盒子奖励分析_{pd.Timestamp.now():%Y%m%d_%H%M}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

    # 单独下载按代理商
    buf2 = io.BytesIO()
    per_agent.to_csv(buf2, index=False, encoding="utf-8-sig")
    st.download_button(
        "📥 下载按代理商汇总（CSV）",
        data=buf2.getvalue(),
        file_name=f"代理商奖励汇总_{pd.Timestamp.now():%Y%m%d_%H%M}.csv",
        mime="text/csv",
    )


else:
    st.info("👆 请上传发货数据和激活数据，或点击「使用示例数据演示」查看效果。")
