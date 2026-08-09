# -*- coding: utf-8 -*-
"""
渠道商激活数据看板（对外）- 数据隔离版 + 卡片化UI
=================================================
每个渠道商通过自己的代理商编号登录，登录后只能看到自己的拿货设备激活状态、
奖励达标情况，无法查看其他代理商数据。

UI 参考：
- 2×2 数字摘要网格（带百分比徽章）
- 红色数据更新日期提示
- SN 查询卡片化
- 紧凑筛选区（下拉+搜索+按钮）

启动方式：
  /Users/fournine/.workbuddy/binaries/python/envs/wb-analysis/bin/streamlit run dashboard.py --server.port 8502
"""

from __future__ import annotations

import io
import re as _re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd
import streamlit as st

from core import analyzer, data_loader

# ---------------------------------------------------------------------------
# 页面配置
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="渠道商激活数据看板",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# 自定义样式（橙色主品牌色 + 卡片化视觉）
# ---------------------------------------------------------------------------

_CUSTOM_CSS = """
<style>
/* 主品牌色：橙色 */
:root {
    --primary-orange: #ff8c00;
    --primary-orange-light: #fff3e0;
    --primary-orange-dark: #e67e00;
    --success-green: #07c160;
    --danger-red: #fa5151;
    --warning-yellow: #ffc53d;
}

/* 卡片数字摘要 */
.stat-card {
    background: #ffffff;
    border: 1px solid #f0f0f0;
    border-radius: 12px;
    padding: 18px 20px;
    margin-bottom: 12px;
    transition: all 0.2s ease;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}
.stat-card:hover {
    box-shadow: 0 4px 16px rgba(255, 140, 0, 0.12);
    border-color: var(--primary-orange);
}
.stat-card .label {
    color: #8c8c8c;
    font-size: 13px;
    margin-bottom: 6px;
    font-weight: 400;
}
.stat-card .value {
    color: #262626;
    font-size: 30px;
    font-weight: 600;
    line-height: 1.2;
    display: inline-block;
}
.stat-card .badge {
    display: inline-block;
    margin-left: 10px;
    padding: 2px 10px;
    border-radius: 10px;
    font-size: 13px;
    font-weight: 500;
    vertical-align: middle;
}
.badge-green { background: #e7f8ee; color: var(--success-green); }
.badge-orange { background: var(--primary-orange-light); color: var(--primary-orange-dark); }
.badge-red { background: #ffeded; color: var(--danger-red); }
.badge-gray { background: #f5f5f5; color: #595959; }

/* 数据更新日期 */
.update-date {
    color: var(--danger-red);
    font-size: 13px;
    margin: 8px 0 16px 0;
    font-weight: 500;
}

/* 登录页 */
.login-box {
    max-width: 420px;
    margin: 60px auto;
    padding: 32px 36px;
    border-radius: 16px;
    background: #ffffff;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.08);
}

/* 设备卡片 */
.device-card {
    background: #ffffff;
    border: 1px solid #f0f0f0;
    border-radius: 10px;
    padding: 16px 20px;
    margin-bottom: 10px;
    transition: all 0.2s ease;
}
.device-card:hover {
    border-color: var(--primary-orange);
    box-shadow: 0 2px 12px rgba(255, 140, 0, 0.1);
}
.device-card .sn {
    color: #8c8c8c;
    font-size: 12px;
    font-family: monospace;
}
.device-card .row {
    display: flex;
    gap: 24px;
    margin-top: 8px;
}
.device-card .cell {
    flex: 1;
}
.device-card .cell-label {
    color: #8c8c8c;
    font-size: 12px;
}
.device-card .cell-value {
    color: #262626;
    font-size: 18px;
    font-weight: 600;
    margin-top: 2px;
}

/* 按钮主色 */
.stButton > button[kind="primary"] {
    background-color: var(--primary-orange);
    border-color: var(--primary-orange);
}

/* 顶部导航栏 */
.nav-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 0 16px 0;
    border-bottom: 1px solid #f0f0f0;
    margin-bottom: 16px;
}
.nav-bar .title {
    font-size: 20px;
    font-weight: 600;
    color: #262626;
}
.nav-bar .user {
    color: #8c8c8c;
    font-size: 13px;
}

/* section 标题 */
.section-title {
    font-size: 16px;
    font-weight: 600;
    color: #262626;
    margin: 24px 0 12px 0;
    display: flex;
    align-items: center;
    gap: 8px;
}
.section-title::before {
    content: "";
    display: inline-block;
    width: 4px;
    height: 16px;
    background: var(--primary-orange);
    border-radius: 2px;
}
</style>
"""
st.markdown(_CUSTOM_CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def _stat_card(label: str, value: str, badge: str = None,
                 badge_class: str = "badge-gray") -> str:
    """渲染数字摘要卡片 HTML。"""
    badge_html = (
        f'<span class="badge {badge_class}">{badge}</span>' if badge else ""
    )
    return f"""
<div class="stat-card">
    <div class="label">{label}</div>
    <div class="value">{value}{badge_html}</div>
</div>
"""


def _device_card_html(row: pd.Series) -> str:
    """渲染单台设备卡片（SN + 三列核心数据 + 状态徽章）。"""
    activated = bool(row.get("is_activated", False))
    status_badge = (
        '<span class="badge badge-green">已激活</span>'
        if activated
        else '<span class="badge badge-red">未激活</span>'
    )
    return f"""
<div class="device-card">
    <div style="display:flex; justify-content:space-between; align-items:center;">
        <span class="sn">SN: {row.get("sn", "")}</span>
        {status_badge}
    </div>
    <div class="row">
        <div class="cell">
            <div class="cell-label">累计订单数</div>
            <div class="cell-value">{row.get("monthly_orders", 0):.0f}</div>
        </div>
        <div class="cell">
            <div class="cell-label">累计交易额</div>
            <div class="cell-value">¥{row.get("monthly_amount", 0):,.0f}</div>
        </div>
        <div class="cell">
            <div class="cell-label">交易用户数</div>
            <div class="cell-value">{row.get("monthly_active_users", 0):.0f}</div>
        </div>
    </div>
</div>
"""


# ---------------------------------------------------------------------------
# Session State 初始化
# ---------------------------------------------------------------------------

if "dash_logged_in" not in st.session_state:
    st.session_state["dash_logged_in"] = False
if "dash_agent_name" not in st.session_state:
    st.session_state["dash_agent_name"] = None
if "dash_agent_id" not in st.session_state:
    st.session_state["dash_agent_id"] = None

# ---------------------------------------------------------------------------
# 数据加载
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def _load_and_analyze(shipping_path: str, activation_path: str):
    """加载数据并分析，返回全部设备明细和代理商汇总。"""
    shipping_df = data_loader.load_shipping_data(shipping_path)
    activation_df = data_loader.load_activation_data(
        activation_path, snapshot_mode="latest"
    )
    per_device, per_agent, _summary = analyzer.analyze(shipping_df, activation_df)
    return per_device, per_agent


def _get_data():
    """加载数据，优先用预设路径。"""
    preset_dir = Path(__file__).parent / "data"
    preset_shipping = preset_dir / "发货数据.xlsx"
    preset_activation = preset_dir / "激活数据.csv"

    if preset_shipping.exists() and preset_activation.exists():
        return _load_and_analyze(str(preset_shipping), str(preset_activation))

    # 没有预设数据时支持上传
    with st.sidebar:
        st.header("📁 数据导入")
        shipping_file = st.file_uploader(
            "发货数据 (xlsx/csv)", type=["xlsx", "xls", "csv"], key="dash_ship"
        )
        activation_file = st.file_uploader(
            "激活数据 (xlsx/csv)", type=["xlsx", "xls", "csv"], key="dash_act"
        )
    if shipping_file and activation_file:
        shipping_df = data_loader.load_shipping_data(shipping_file)
        activation_df = data_loader.load_activation_data(
            activation_file, snapshot_mode="latest"
        )
        per_device, per_agent, _ = analyzer.analyze(shipping_df, activation_df)
        return per_device, per_agent
    return None, None


# ---------------------------------------------------------------------------
# 获取所有合法的代理商编号（用于登录验证）
# ---------------------------------------------------------------------------

def _get_valid_agent_ids(per_device: pd.DataFrame) -> dict:
    """返回 {agent_id: [agent_name, ...]} 映射。

    一个编号可能对应多个代理商名，登录后需二次确认。
    """
    if per_device is None or per_device.empty:
        return {}
    pairs = (
        per_device[["agent_id", "agent_name"]]
        .drop_duplicates()
        .dropna()
    )
    result: dict[str, list[str]] = {}
    for aid, aname in zip(pairs["agent_id"].astype(str), pairs["agent_name"]):
        result.setdefault(aid, [])
        if aname not in result[aid]:
            result[aid].append(aname)
    return result


# ---------------------------------------------------------------------------
# 登录页面
# ---------------------------------------------------------------------------

def show_login_page(per_device: pd.DataFrame):
    """代理商登录页面。"""
    st.markdown(
        """
<div class="login-box">
    <div style="text-align:center; margin-bottom: 24px;">
        <div style="font-size: 48px;">📊</div>
        <div style="font-size: 22px; font-weight: 600; margin-top: 8px;">
            渠道商激活数据看板
        </div>
        <div style="color: #8c8c8c; font-size: 13px; margin-top: 6px;">
            请输入您的代理商编号登录
        </div>
    </div>
</div>
""",
        unsafe_allow_html=True,
    )

    valid_map = _get_valid_agent_ids(per_device)

    if not valid_map:
        st.warning("数据中未识别到代理商信息，请联系管理员。")
        return

    _, mid, _ = st.columns([1, 2, 1])
    with mid:
        with st.form("login_form"):
            agent_id_input = st.text_input(
                "代理商编号",
                placeholder="请输入您的代理商编号",
                help="代理商编号由管理员分配",
            )
            submitted = st.form_submit_button(
                "登录", use_container_width=True, type="primary"
            )

        # 编号对应多个代理商时，二次确认
        if submitted:
            agent_id_input = agent_id_input.strip()
            if not agent_id_input:
                st.error("请输入代理商编号")
            elif agent_id_input not in valid_map:
                st.error("代理商编号无效，请确认后重试")
            else:
                names = valid_map[agent_id_input]
                if len(names) == 1:
                    st.session_state["dash_logged_in"] = True
                    st.session_state["dash_agent_id"] = agent_id_input
                    st.session_state["dash_agent_name"] = names[0]
                    st.rerun()
                else:
                    st.session_state["dash_pending_id"] = agent_id_input
                    st.session_state["dash_pending_names"] = names
                    st.rerun()

        # 二次确认
        pending_names = st.session_state.get("dash_pending_names")
        if pending_names:
            st.info(
                f"编号 {st.session_state['dash_pending_id']} "
                f"对应多个渠道商，请确认您的身份："
            )
            chosen = st.selectbox("选择您的渠道商名称", pending_names)
            if st.button("确认登录", use_container_width=True, type="primary"):
                st.session_state["dash_logged_in"] = True
                st.session_state["dash_agent_id"] = st.session_state["dash_pending_id"]
                st.session_state["dash_agent_name"] = chosen
                st.session_state.pop("dash_pending_id", None)
                st.session_state.pop("dash_pending_names", None)
                st.rerun()


# ---------------------------------------------------------------------------
# 主看板页面（已登录）
# ---------------------------------------------------------------------------

def show_dashboard(per_device: pd.DataFrame, per_agent: pd.DataFrame):
    """已登录的渠道商看板。"""
    agent_name = st.session_state["dash_agent_name"]
    agent_id = st.session_state["dash_agent_id"]

    # ---- 顶部导航栏 ----
    col_title, col_btn = st.columns([5, 1])
    with col_title:
        st.markdown(
            f"""
<div class="nav-bar">
    <div>
        <div class="title">📊 渠道商激活数据看板</div>
        <div class="user">{agent_name}（编号 {agent_id}）</div>
    </div>
</div>
""",
            unsafe_allow_html=True,
        )
    with col_btn:
        st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)
        if st.button("🚪 退出", use_container_width=True):
            st.session_state["dash_logged_in"] = False
            st.session_state["dash_agent_name"] = None
            st.session_state["dash_agent_id"] = None
            st.rerun()

    # ---- 数据隔离：只取当前代理商的数据 ----
    agent_devices = per_device[per_device["agent_name"] == agent_name].copy()
    agent_agg_row = per_agent[per_agent["代理商"] == agent_name]

    if agent_devices.empty:
        st.warning(f"未找到渠道商「{agent_name}」的设备数据")
        return

    # ---- 统计 ----
    _total = len(agent_devices)
    _activated = int(agent_devices["is_activated"].sum())
    _unactivated = _total - _activated
    _landing = int(agent_devices["is_landing_eligible"].sum())
    _active = int(agent_devices["is_activation_eligible"].sum())
    _act_reward = int((agent_devices["activation_fee"] > 0).sum())

    _biz = agent_agg_row["业务线"].iloc[0] if not agent_agg_row.empty else ""
    _sales = agent_agg_row["销售"].iloc[0] if not agent_agg_row.empty else ""

    # 数据更新日期：从预设文件名推断（包含 YYYYMMDD），否则用今天
    _date_str = pd.Timestamp.now().strftime("%Y-%m-%d")
    try:
        _preset_dir = Path(__file__).parent / "data"
        _preset_act = _preset_dir / "激活数据.csv"
        if _preset_act.exists():
            m = _re.search(r"(\d{8})", _preset_act.name)
            if m:
                _date_str = pd.Timestamp(m.group(1), format="%Y%m%d").strftime("%Y-%m-%d")
    except Exception:
        pass

    # ---- 数据更新日期（红色提示，参考图2） ----
    st.markdown(
        f'<div class="update-date">数据更新日期：{_date_str}'
        f'（T+1，每天11点更新）</div>',
        unsafe_allow_html=True,
    )

    # ================================================================
    # 我的汇总（2×2 数字摘要网格 + 第5项独立）
    # ================================================================
    st.markdown(
        '<div class="section-title">📈 我的汇总</div>',
        unsafe_allow_html=True,
    )

    _activate_rate = _activated / max(_total, 1) * 100
    _landing_rate = _landing / max(_activated, 1) * 100
    _active_rate = _active / max(_activated, 1) * 100

    c1, c2 = st.columns(2)
    with c1:
        st.markdown(
            _stat_card(
                "📦 拿货总数",
                f"{_total:,}",
                f"{_biz or '-'} · {_sales or '-'}",
                "badge-gray",
            ),
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            _stat_card(
                "🟢 已激活",
                f"{_activated:,}",
                f"{_activate_rate:.1f}%",
                "badge-green" if _activate_rate >= 30 else "badge-orange",
            ),
            unsafe_allow_html=True,
        )

    c3, c4 = st.columns(2)
    with c3:
        st.markdown(
            _stat_card(
                "🎯 落地达标",
                f"{_landing:,}",
                f"达标率 {_landing_rate:.1f}%",
                "badge-orange" if _landing_rate >= 30 else "badge-gray",
            ),
            unsafe_allow_html=True,
        )
    with c4:
        st.markdown(
            _stat_card(
                "📈 活跃达标",
                f"{_active:,}",
                f"达标率 {_active_rate:.1f}%",
                "badge-orange" if _active_rate >= 30 else "badge-gray",
            ),
            unsafe_allow_html=True,
        )

    # 激活达标奖励 + 未激活（独立行）
    c5, c6 = st.columns(2)
    with c5:
        st.markdown(
            _stat_card(
                "🏆 激活达标奖励",
                f"{_act_reward:,}",
                "达标即奖" if _act_reward > 0 else "未达门槛",
                "badge-orange" if _act_reward > 0 else "badge-gray",
            ),
            unsafe_allow_html=True,
        )
    with c6:
        st.markdown(
            _stat_card(
                "🔴 未激活",
                f"{_unactivated:,}",
                f"未激活率 {(_unactivated/max(_total,1)*100):.1f}%",
                "badge-red" if _unactivated > 0 else "badge-gray",
            ),
            unsafe_allow_html=True,
        )

    st.markdown("---")

    # ================================================================
    # SN 查询（卡片化结果展示）
    # ================================================================
    st.markdown(
        '<div class="section-title">🔍 SN 查询</div>',
        unsafe_allow_html=True,
    )

    # 紧凑筛选：搜索框 + 状态筛选 + 批次筛选 + 按钮
    sr1, sr2, sr3, sr4, sr5 = st.columns([3, 2, 2, 1, 1])
    with sr1:
        sn_input = st.text_input(
            "输入设备 SN",
            placeholder="输入SN模糊搜索",
            label_visibility="collapsed",
        )
    with sr2:
        sn_status = st.selectbox(
            "激活状态",
            ["全部", "已激活", "未激活"],
            label_visibility="collapsed",
        )
    with sr3:
        batch_options = ["全部"] + sorted(
            agent_devices["batch_no"].dropna().unique().tolist()
        )
        sn_batch = st.selectbox(
            "批次",
            batch_options,
            label_visibility="collapsed",
        )
    with sr4:
        search_clicked = st.button(
            "查询", use_container_width=True, type="primary"
        )
    with sr5:
        reset_clicked = st.button("重置", use_container_width=True)

    if reset_clicked:
        st.rerun()

    if sn_input or search_clicked or sn_status != "全部" or sn_batch != "全部":
        # 在当前代理商的设备中搜索/筛选
        search_result = agent_devices.copy()
        if sn_input:
            search_result = search_result[
                search_result["sn"].str.contains(
                    sn_input, case=False, na=False
                )
            ]
        if sn_status == "已激活":
            search_result = search_result[search_result["is_activated"]]
        elif sn_status == "未激活":
            search_result = search_result[~search_result["is_activated"]]
        if sn_batch != "全部":
            search_result = search_result[search_result["batch_no"] == sn_batch]

        if not search_result.empty:
            st.success(f"找到 {len(search_result)} 条匹配记录")

            if len(search_result) == 1:
                # 单条：详细卡片
                row = search_result.iloc[0]
                st.markdown(
                    _device_card_html(row),
                    unsafe_allow_html=True,
                )

                # 达标详情（三列）
                st.markdown("---")
                d1, d2, d3 = st.columns(3)
                with d1:
                    land_ok = "✅" if row["is_landing_eligible"] else "❌"
                    st.markdown(
                        _stat_card(
                            "落地达标", land_ok,
                            f"¥{row.get('landing_fee', 0):,.0f}",
                            "badge-green" if row["is_landing_eligible"] else "badge-gray",
                        ),
                        unsafe_allow_html=True,
                    )
                with d2:
                    act_ok = "✅" if row["is_activation_eligible"] else "❌"
                    st.markdown(
                        _stat_card(
                            "活跃达标", act_ok,
                            f"¥{row.get('activity_fee', 0):,.2f}",
                            "badge-green" if row["is_activation_eligible"] else "badge-gray",
                        ),
                        unsafe_allow_html=True,
                    )
                with d3:
                    a_ok = "✅" if row.get("activation_fee", 0) > 0 else "❌"
                    st.markdown(
                        _stat_card(
                            "激活达标奖励", a_ok,
                            f"¥{row.get('activation_fee', 0):,.0f}",
                            "badge-orange" if row.get("activation_fee", 0) > 0 else "badge-gray",
                        ),
                        unsafe_allow_html=True,
                    )

                # 预计总奖励
                st.markdown(
                    _stat_card(
                        "💰 预计总奖励",
                        f"¥{row.get('total_reward', 0):,.2f}",
                        badge=None,
                    ),
                    unsafe_allow_html=True,
                )

                with st.expander("查看完整字段"):
                    st.dataframe(
                        search_result.T.rename(
                            columns={search_result.index[0]: "值"}
                        ),
                        use_container_width=True,
                    )
            else:
                # 多条：卡片列表
                cards_html = "".join(
                    _device_card_html(r) for _, r in search_result.iterrows()
                )
                st.markdown(cards_html, unsafe_allow_html=True)
        else:
            st.warning(
                f"未找到匹配的设备\n请确认 SN 是否正确，或该设备是否属于您的渠道"
            )

    st.markdown("---")

    # ================================================================
    # 设备明细（紧凑筛选 + 表格）
    # ================================================================
    st.markdown(
        '<div class="section-title">📋 设备明细</div>',
        unsafe_allow_html=True,
    )

    # 紧凑筛选：状态 + 批次 + 查询 + 重置
    f1, f2, f3, f4 = st.columns([3, 3, 1, 1])
    with f1:
        status_filter = st.multiselect(
            "状态筛选",
            ["已激活", "未激活", "落地达标", "活跃达标", "激活达标"],
            default=[],
            label_visibility="visible",
        )
    with f2:
        batch_options = sorted(
            agent_devices["batch_no"].dropna().unique().tolist()
        )
        batch_filter = st.multiselect(
            "批次筛选",
            options=batch_options,
            default=[],
        )
    with f3:
        detail_query = st.button(
            "查询", use_container_width=True, type="primary", key="detail_q"
        )
    with f4:
        detail_reset = st.button("重置", use_container_width=True, key="detail_r")

    if detail_reset:
        st.rerun()

    filtered = agent_devices.copy()
    if status_filter:
        mask = pd.Series(False, index=filtered.index)
        if "已激活" in status_filter:
            mask |= filtered["is_activated"]
        if "未激活" in status_filter:
            mask |= ~filtered["is_activated"]
        if "落地达标" in status_filter:
            mask |= filtered["is_landing_eligible"]
        if "活跃达标" in status_filter:
            mask |= filtered["is_activation_eligible"]
        if "激活达标" in status_filter:
            mask |= filtered["activation_fee"] > 0
        filtered = filtered[mask]

    if batch_filter:
        filtered = filtered[filtered["batch_no"].isin(batch_filter)]

    detail_cols = [
        "sn", "agent_name", "biz_line", "sales",
        "is_activated", "monthly_orders", "monthly_amount",
        "monthly_active_users", "monthly_active_days",
        "is_landing_eligible", "landing_fee",
        "activity_fee",
        "is_activation_eligible",
        "activation_fee", "total_reward",
        "batch_no",
    ]
    existing = [c for c in detail_cols if c in filtered.columns]

    # 显示当前筛选后条数 + 下载按钮
    head_l, head_r = st.columns([4, 1])
    with head_l:
        st.caption(f"共 {len(filtered)} 条记录")
    with head_r:
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
            filtered[existing].to_excel(
                writer, sheet_name="设备明细", index=False
            )
            if not agent_agg_row.empty:
                agent_agg_row.to_excel(
                    writer, sheet_name="汇总", index=False
                )
        st.download_button(
            "📥 下载我的数据",
            data=buf.getvalue(),
            file_name=f"{agent_name}_激活数据_{pd.Timestamp.now():%Y%m%d}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

    st.dataframe(
        filtered[existing], use_container_width=True, hide_index=True,
        height=420,
    )


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

per_device, per_agent = _get_data()

if per_device is None or per_agent is None:
    st.info("👆 数据加载中，请稍候...")
elif not st.session_state["dash_logged_in"]:
    show_login_page(per_device)
else:
    show_dashboard(per_device, per_agent)