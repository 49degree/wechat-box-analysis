# -*- coding: utf-8 -*-
"""
渠道商激活数据看板（对外）— Gradio 版
=================================================
适配 Hugging Face Spaces 免费 Gradio SDK。

每个渠道商通过自己的代理商编号登录，登录后只能看到自己的拿货设备激活状态、
奖励达标情况，无法查看其他代理商数据。

启动方式（本地）：
  /Users/fournine/.workbuddy/binaries/python/envs/wb-analysis/bin/python dashboard_gradio.py
或：
  gradio dashboard_gradio.py
"""

from __future__ import annotations

import io
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import gradio as gr
import pandas as pd

from core import analyzer, data_loader

# ---------------------------------------------------------------------------
# 主题 & CSS
# ---------------------------------------------------------------------------

_CUSTOM_CSS = """
/* 主品牌色：橙色 */
:root {
    --primary-orange: #ff8c00;
    --primary-orange-light: #fff3e0;
    --primary-orange-dark: #e67e00;
    --success-green: #07c160;
    --danger-red: #fa5151;
    --warning-yellow: #ffc53d;
}

/* 数字摘要卡片 */
.stat-card {
    background: #ffffff;
    border: 1px solid #f0f0f0;
    border-radius: 12px;
    padding: 18px 20px;
    margin-bottom: 12px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}
.stat-card .label { color: #8c8c8c; font-size: 13px; margin-bottom: 6px; }
.stat-card .value { color: #262626; font-size: 28px; font-weight: 600; line-height: 1.2; }
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

.update-date {
    color: var(--danger-red);
    font-size: 13px;
    margin: 8px 0 16px 0;
    font-weight: 500;
}

.device-card {
    background: #ffffff;
    border: 1px solid #f0f0f0;
    border-radius: 10px;
    padding: 16px 20px;
    margin-bottom: 10px;
}
.device-card .sn { color: #8c8c8c; font-size: 12px; font-family: monospace; }
.device-card .row { display: flex; gap: 24px; margin-top: 8px; }
.device-card .cell { flex: 1; }
.device-card .cell-label { color: #8c8c8c; font-size: 12px; }
.device-card .cell-value { color: #262626; font-size: 18px; font-weight: 600; margin-top: 2px; }

.section-title {
    font-size: 16px; font-weight: 600; color: #262626;
    margin: 24px 0 12px 0;
    display: flex; align-items: center; gap: 8px;
}
.section-title::before {
    content: ""; display: inline-block;
    width: 4px; height: 16px;
    background: var(--primary-orange); border-radius: 2px;
}

.nav-bar {
    display: flex; align-items: center; justify-content: space-between;
    padding: 12px 0 16px 0; border-bottom: 1px solid #f0f0f0; margin-bottom: 16px;
}
.nav-bar .title { font-size: 20px; font-weight: 600; color: #262626; }
.nav-bar .user { color: #8c8c8c; font-size: 13px; }

.gr-button-primary {
    background-color: var(--primary-orange) !important;
    border-color: var(--primary-orange) !important;
}
"""

# ---------------------------------------------------------------------------
# 数据加载
# ---------------------------------------------------------------------------

def _load_data():
    """加载数据，支持多种来源：
    1) 环境变量 SHIPPING_DATA_PATH / ACTIVATION_DATA_PATH
    2) data/ 目录（本地开发）
    3) sample_data/ 目录（HF Spaces 示例数据）
    """
    base = Path(__file__).resolve().parent

    candidate_paths = [
        # 1. 环境变量（HF Spaces secrets / 云端配置）
        (os.environ.get("SHIPPING_DATA_PATH"),
         os.environ.get("ACTIVATION_DATA_PATH")),
        # 2. data/ 目录（本地预设）
        (str(base / "data" / "发货数据.xlsx"),
         str(base / "data" / "激活数据.csv")),
        # 3. sample_data/ 目录（HF Spaces 云端 fallback）
        (str(base / "sample_data" / "发货数据-示例.csv"),
         str(base / "sample_data" / "激活数据-示例.csv")),
    ]

    for ship_path, act_path in candidate_paths:
        if not (ship_path and act_path):
            continue
        ship_p = Path(ship_path)
        act_p = Path(act_path)
        if ship_p.exists() and act_p.exists():
            try:
                shipping_df = data_loader.load_shipping_data(str(ship_p))
                activation_df = data_loader.load_activation_data(
                    str(act_p), snapshot_mode="latest"
                )
                per_device, per_agent, _summary = analyzer.analyze(
                    shipping_df, activation_df
                )

                m = re.search(r"(\d{8})", act_p.name)
                update_date = (
                    pd.Timestamp(m.group(1), format="%Y%m%d").strftime("%Y-%m-%d")
                    if m
                    else pd.Timestamp.now().strftime("%Y-%m-%d")
                )
                return per_device, per_agent, update_date, str(ship_p)
            except Exception as e:
                print(f"[load] 加载失败 ({ship_p.name}): {e}", flush=True)
                continue

    return None, None, None, None


# 模块加载时执行一次，缓存在内存
PER_DEVICE, PER_AGENT, UPDATE_DATE, DATA_SOURCE = _load_data()

# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def _stat_card(label: str, value: str, badge: str = "",
               badge_class: str = "badge-gray") -> str:
    badge_html = (
        f'<span class="badge {badge_class}">{badge}</span>' if badge else ""
    )
    return f"""
<div class="stat-card">
    <div class="label">{label}</div>
    <div class="value">{value}{badge_html}</div>
</div>"""


def _device_card_html(row: pd.Series) -> str:
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
</div>"""


def _valid_agent_map(per_device: pd.DataFrame) -> dict[str, list[str]]:
    """返回 {agent_id: [agent_name, ...]}，一个编号可能对应多个代理商名。"""
    if per_device is None or per_device.empty:
        return {}
    pairs = per_device[["agent_id", "agent_name"]].drop_duplicates().dropna()
    result: dict[str, list[str]] = {}
    for aid, aname in zip(pairs["agent_id"].astype(str), pairs["agent_name"]):
        result.setdefault(aid, [])
        if aname not in result[aid]:
            result[aid].append(aname)
    return result


# ---------------------------------------------------------------------------
# 登录回调
# ---------------------------------------------------------------------------

def do_login(agent_id_input: str, state: dict):
    """处理登录请求。"""
    if PER_DEVICE is None:
        return (
            state,
            gr.update(visible=True),
            gr.update(visible=False),
            "数据加载失败，请检查数据文件是否存在。",
        )

    valid = _valid_agent_map(PER_DEVICE)
    agent_id_input = (agent_id_input or "").strip()

    if not agent_id_input:
        return (
            state,
            gr.update(visible=True),
            gr.update(visible=False),
            "❌ 请输入代理商编号",
        )

    if agent_id_input not in valid:
        return (
            state,
            gr.update(visible=True),
            gr.update(visible=False),
            "❌ 代理商编号无效，请确认后重试",
        )

    names = valid[agent_id_input]
    if len(names) == 1:
        # 唯一身份，直接登录
        state["logged_in"] = True
        state["agent_id"] = agent_id_input
        state["agent_name"] = names[0]
        return (
            state,
            gr.update(visible=False),
            gr.update(visible=True),
            "",
        )

    # 多个代理商名，需要二次确认
    state["pending_id"] = agent_id_input
    state["pending_names"] = names
    return (
        state,
        gr.update(visible=True),
        gr.update(visible=False),
        f"编号 {agent_id_input} 对应多个渠道商：{', '.join(names)}，请在下方选择身份后确认。",
    )


def do_confirm_identity(chosen_name: str, state: dict):
    """二次确认代理商身份。"""
    pending_id = state.get("pending_id")
    pending_names = state.get("pending_names") or []

    if not pending_id or chosen_name not in pending_names:
        return (
            state,
            gr.update(visible=True),
            gr.update(visible=False),
            "❌ 请先选择您的渠道商身份",
        )

    state["logged_in"] = True
    state["agent_id"] = pending_id
    state["agent_name"] = chosen_name
    state.pop("pending_id", None)
    state.pop("pending_names", None)
    return (
        state,
        gr.update(visible=False),
        gr.update(visible=True),
        "",
    )


def do_logout(state: dict):
    """退出登录。"""
    state["logged_in"] = False
    state["agent_id"] = None
    state["agent_name"] = None
    state.pop("pending_id", None)
    state.pop("pending_names", None)
    return (
        state,
        gr.update(visible=True),
        gr.update(visible=False),
        "",
        gr.update(value=""),
        gr.update(value=None, choices=[]),
        "",
    )


# ---------------------------------------------------------------------------
# 主看板回调
# ---------------------------------------------------------------------------

def _agent_devices(agent_name: str) -> pd.DataFrame:
    if PER_DEVICE is None or agent_name is None:
        return pd.DataFrame()
    return PER_DEVICE[PER_DEVICE["agent_name"] == agent_name].copy()


def _agent_agg_row(agent_name: str) -> pd.DataFrame:
    if PER_AGENT is None or agent_name is None:
        return pd.DataFrame()
    return PER_AGENT[PER_AGENT["代理商"] == agent_name]


def render_summary(state: dict):
    """汇总卡片 + 导航 + 更新日期 + 6 个独立卡片。"""
    if not state.get("logged_in"):
        empty = gr.update(value="")
        return (empty,) * 9

    agent_name = state["agent_name"]
    agent_id = state["agent_id"]
    agent_devices = _agent_devices(agent_name)
    agent_agg_row = _agent_agg_row(agent_name)

    _total = len(agent_devices)
    _activated = int(agent_devices["is_activated"].sum())
    _unactivated = _total - _activated
    _landing = int(agent_devices["is_landing_eligible"].sum())
    _active = int(agent_devices["is_activation_eligible"].sum())
    _act_reward = int((agent_devices["activation_fee"] > 0).sum())

    _biz = (
        agent_agg_row["业务线"].iloc[0]
        if not agent_agg_row.empty else ""
    )
    _sales = (
        agent_agg_row["销售"].iloc[0]
        if not agent_agg_row.empty else ""
    )
    _activate_rate = _activated / max(_total, 1) * 100
    _landing_rate = _landing / max(_activated, 1) * 100
    _active_rate = _active / max(_activated, 1) * 100

    nav_html = f"""
<div class="nav-bar">
    <div>
        <div class="title">📊 渠道商激活数据看板</div>
        <div class="user">{agent_name}（编号 {agent_id}）</div>
    </div>
</div>"""
    update_html = (
        f'<div class="update-date">数据更新日期：{UPDATE_DATE or "-"} '
        f'（T+1，每天11点更新）</div>'
    )

    return (
        gr.update(value=nav_html),
        gr.update(value=update_html),
        gr.update(value=_stat_card(
            "📦 拿货总数", f"{_total:,}",
            f"{_biz or '-'} · {_sales or '-'}", "badge-gray",
        )),
        gr.update(value=_stat_card(
            "🟢 已激活", f"{_activated:,}", f"{_activate_rate:.1f}%",
            "badge-green" if _activate_rate >= 30 else "badge-orange",
        )),
        gr.update(value=_stat_card(
            "🎯 落地达标", f"{_landing:,}", f"达标率 {_landing_rate:.1f}%",
            "badge-orange" if _landing_rate >= 30 else "badge-gray",
        )),
        gr.update(value=_stat_card(
            "📈 活跃达标", f"{_active:,}", f"达标率 {_active_rate:.1f}%",
            "badge-orange" if _active_rate >= 30 else "badge-gray",
        )),
        gr.update(value=_stat_card(
            "🏆 激活达标奖励", f"{_act_reward:,}",
            "达标即奖" if _act_reward > 0 else "未达门槛",
            "badge-orange" if _act_reward > 0 else "badge-gray",
        )),
        gr.update(value=_stat_card(
            "🔴 未激活", f"{_unactivated:,}",
            f"未激活率 {(_unactivated / max(_total, 1) * 100):.1f}%",
            "badge-red" if _unactivated > 0 else "badge-gray",
        )),
    )


def do_sn_search(sn_input: str, sn_status: str, sn_batch: str, state: dict):
    """SN 搜索 + 筛选。"""
    if not state.get("logged_in"):
        return (
            gr.update(value="❌ 请先登录"),
            gr.update(value=None),
            gr.update(visible=False),
            gr.update(visible=False),
            gr.update(value=""),
        )

    agent_devices = _agent_devices(state["agent_name"])

    if agent_devices.empty:
        return (
            gr.update(value="⚠️ 未找到您的设备数据"),
            gr.update(value=None),
            gr.update(visible=False),
            gr.update(visible=False),
            gr.update(value=""),
        )

    result = agent_devices.copy()
    if sn_input:
        result = result[result["sn"].astype(str).str.contains(
            sn_input, case=False, na=False
        )]
    if sn_status == "已激活":
        result = result[result["is_activated"]]
    elif sn_status == "未激活":
        result = result[~result["is_activated"]]
    if sn_batch and sn_batch != "全部":
        result = result[result["batch_no"] == sn_batch]

    if result.empty:
        return (
            gr.update(value="⚠️ 未找到匹配的设备，请确认 SN 或渠道归属"),
            gr.update(value=None),
            gr.update(visible=False),
            gr.update(visible=False),
            gr.update(value=""),
        )

    msg = f"✅ 找到 {len(result)} 条匹配记录"

    if len(result) == 1:
        row = result.iloc[0]
        cards_html = _device_card_html(row)

        land_ok = "✅" if row["is_landing_eligible"] else "❌"
        act_ok = "✅" if row["is_activation_eligible"] else "❌"
        a_ok = "✅" if row.get("activation_fee", 0) > 0 else "❌"

        detail_html = f"""
{cards_html}
<hr/>
<div style="display:flex; gap:12px;">
    {_stat_card("落地达标", land_ok, f"¥{row.get('landing_fee', 0):,.0f}",
                "badge-green" if row["is_landing_eligible"] else "badge-gray")}
    {_stat_card("活跃达标", act_ok, f"¥{row.get('activity_fee', 0):,.2f}",
                "badge-green" if row["is_activation_eligible"] else "badge-gray")}
    {_stat_card("激活达标奖励", a_ok, f"¥{row.get('activation_fee', 0):,.0f}",
                "badge-orange" if row.get("activation_fee", 0) > 0 else "badge-gray")}
</div>
{_stat_card("💰 预计总奖励", f"¥{row.get('total_reward', 0):,.2f}")}"""

        # 完整字段 dataframe
        full_df = result.T.reset_index()
        full_df.columns = ["字段", "值"]

        return (
            gr.update(value=msg),
            gr.update(value=full_df),
            gr.update(value=detail_html, visible=True),
            gr.update(visible=False),
            gr.update(value=""),
        )
    else:
        # 多条：渲染为列表 + 显示表格
        cards_html = "".join(_device_card_html(r) for _, r in result.iterrows())
        detail_cols = [
            "sn", "agent_name", "biz_line", "sales",
            "is_activated", "monthly_orders", "monthly_amount",
            "monthly_active_users", "monthly_active_days",
            "is_landing_eligible", "landing_fee", "activity_fee",
            "is_activation_eligible", "activation_fee", "total_reward",
            "batch_no",
        ]
        existing = [c for c in detail_cols if c in result.columns]
        table_df = result[existing].reset_index(drop=True)

        return (
            gr.update(value=msg),
            gr.update(value=table_df),
            gr.update(value="", visible=False),
            gr.update(value=cards_html, visible=True),
            gr.update(value=""),
        )


def get_batch_choices(state: dict):
    """根据当前登录代理商动态返回批次选项。"""
    if not state.get("logged_in"):
        return gr.update(choices=["全部"], value="全部")
    agent_devices = _agent_devices(state["agent_name"])
    batches = ["全部"] + sorted(
        agent_devices["batch_no"].dropna().unique().tolist()
    )
    return gr.update(choices=batches, value="全部")


def do_device_search(
    status_filter: list[str],
    batch_filter: list[str],
    state: dict,
):
    """设备明细查询（带状态 + 批次筛选）。"""
    if not state.get("logged_in"):
        return gr.update(value=None), gr.update(value=None), ""

    agent_devices = _agent_devices(state["agent_name"])
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
        "is_landing_eligible", "landing_fee", "activity_fee",
        "is_activation_eligible", "activation_fee", "total_reward",
        "batch_no",
    ]
    existing = [c for c in detail_cols if c in filtered.columns]
    table_df = filtered[existing].reset_index(drop=True)

    # 生成 Excel 文件用于下载
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
        filtered[existing].to_excel(writer, sheet_name="设备明细", index=False)
        agg = _agent_agg_row(state["agent_name"])
        if not agg.empty:
            agg.to_excel(writer, sheet_name="汇总", index=False)
    file_path = f"/tmp/{state['agent_name']}_激活数据_{pd.Timestamp.now():%Y%m%d_%H%M%S}.xlsx"
    with open(file_path, "wb") as f:
        f.write(buf.getvalue())

    caption = f"共 {len(filtered)} 条记录"
    return (
        gr.update(value=table_df),
        gr.update(value=file_path, visible=True),
        caption,
    )


def get_device_batch_choices(state: dict):
    """设备明细筛选的批次选项。"""
    if not state.get("logged_in"):
        return gr.update(choices=[], value=[])
    agent_devices = _agent_devices(state["agent_name"])
    batches = sorted(agent_devices["batch_no"].dropna().unique().tolist())
    return gr.update(choices=batches, value=[])


# ---------------------------------------------------------------------------
# UI 构建
# ---------------------------------------------------------------------------

with gr.Blocks(
    title="渠道商激活数据看板",
) as demo:
    # ---------- 全局状态 ----------
    state = gr.State({
        "logged_in": False,
        "agent_id": None,
        "agent_name": None,
        "pending_id": None,
        "pending_names": None,
    })

    # ---------- 登录页 ----------
    with gr.Column(visible=True) as login_view:
        gr.Markdown("""
<div style="text-align:center; margin: 40px 0 24px 0;">
    <div style="font-size: 48px;">📊</div>
    <div style="font-size: 22px; font-weight: 600; margin-top: 8px;">
        渠道商激活数据看板
    </div>
    <div style="color: #8c8c8c; font-size: 13px; margin-top: 6px;">
        请输入您的代理商编号登录
    </div>
</div>""")

        with gr.Row():
            with gr.Column(scale=1):
                pass
            with gr.Column(scale=2):
                login_id_input = gr.Textbox(
                    label="代理商编号",
                    placeholder="请输入您的代理商编号",
                )
                login_btn = gr.Button(
                    "登录", variant="primary", size="lg"
                )
                login_msg = gr.Markdown("")
                pending_dropdown = gr.Dropdown(
                    label="选择您的渠道商身份",
                    choices=[],
                    visible=False,
                )
                confirm_btn = gr.Button(
                    "确认登录", variant="primary",
                    visible=False,
                )
            with gr.Column(scale=1):
                pass

    # ---------- 主看板 ----------
    with gr.Column(visible=False) as dashboard_view:
        nav_bar = gr.Markdown("")
        update_date_md = gr.Markdown("")
        logout_btn = gr.Button("🚪 退出登录", size="sm")

        gr.Markdown('<div class="section-title">📈 我的汇总</div>')

        with gr.Row():
            card_total = gr.HTML("")
            card_activated = gr.HTML("")
        with gr.Row():
            card_landing = gr.HTML("")
            card_active = gr.HTML("")
        with gr.Row():
            card_act_reward = gr.HTML("")
            card_unactivated = gr.HTML("")

        gr.Markdown("---")
        gr.Markdown('<div class="section-title">🔍 SN 查询</div>')

        with gr.Row():
            sn_input_box = gr.Textbox(
                label="输入设备 SN（模糊搜索）",
                placeholder="输入SN模糊搜索",
                scale=3,
            )
            sn_status_box = gr.Dropdown(
                label="激活状态",
                choices=["全部", "已激活", "未激活"],
                value="全部",
                scale=2,
            )
            sn_batch_box = gr.Dropdown(
                label="批次",
                choices=["全部"],
                value="全部",
                scale=2,
            )
            sn_search_btn = gr.Button(
                "查询", variant="primary", scale=1
            )

        sn_msg = gr.Markdown("")
        sn_detail_html = gr.HTML(visible=False)
        sn_cards_html = gr.HTML(visible=False)
        sn_table = gr.Dataframe(
            label="查询结果表",
            visible=True,
            wrap=True,
        )

        gr.Markdown("---")
        gr.Markdown('<div class="section-title">📋 设备明细</div>')

        with gr.Row():
            detail_status_box = gr.Dropdown(
                label="状态筛选（可多选）",
                choices=["已激活", "未激活", "落地达标", "活跃达标", "激活达标"],
                multiselect=True,
                value=[],
                scale=3,
            )
            detail_batch_box = gr.Dropdown(
                label="批次筛选（可多选）",
                choices=[],
                multiselect=True,
                value=[],
                scale=3,
            )
            detail_query_btn = gr.Button(
                "查询", variant="primary", scale=1
            )

        detail_caption = gr.Markdown("")
        with gr.Row():
            with gr.Column(scale=4):
                pass
            with gr.Column(scale=1):
                download_file = gr.File(
                    label="📥 下载我的数据",
                    visible=False,
                )
        detail_table = gr.Dataframe(
            label="设备明细",
            wrap=True,
        )

    # ---------- 事件绑定 ----------
    # 登录按钮 → 校验
    def _login_click(aid, s):
        s_new, login_vis, dash_vis, msg = do_login(aid, s)
        # 如果是二次确认场景，显示 dropdown
        if s_new.get("pending_names"):
            return (
                s_new,
                login_vis,
                dash_vis,
                gr.update(value=msg),
                gr.update(
                    choices=s_new["pending_names"],
                    value=s_new["pending_names"][0],
                    visible=True,
                ),
                gr.update(visible=True),
            )
        return (
            s_new,
            login_vis,
            dash_vis,
            gr.update(value=msg),
            gr.update(choices=[], value=None, visible=False),
            gr.update(visible=False),
        )

    outputs_login = [state, login_view, dashboard_view, login_msg,
                     pending_dropdown, confirm_btn]
    login_btn.click(
        _login_click,
        inputs=[login_id_input, state],
        outputs=outputs_login,
    ).then(
        render_summary,
        inputs=[state],
        outputs=[nav_bar, update_date_md, card_total, card_activated,
                 card_landing, card_active, card_act_reward, card_unactivated],
    ).then(
        get_batch_choices,
        inputs=[state],
        outputs=[sn_batch_box],
    ).then(
        get_device_batch_choices,
        inputs=[state],
        outputs=[detail_batch_box],
    )

    # 二次确认
    def _confirm_click(name, s):
        s_new, login_vis, dash_vis, msg = do_confirm_identity(name, s)
        return (
            s_new,
            login_vis,
            dash_vis,
            gr.update(value=msg),
            gr.update(choices=[], value=None, visible=False),
            gr.update(visible=False),
        )

    confirm_btn.click(
        _confirm_click,
        inputs=[pending_dropdown, state],
        outputs=outputs_login,
    ).then(
        render_summary,
        inputs=[state],
        outputs=[nav_bar, update_date_md, card_total, card_activated,
                 card_landing, card_active, card_act_reward, card_unactivated],
    ).then(
        get_batch_choices,
        inputs=[state],
        outputs=[sn_batch_box],
    ).then(
        get_device_batch_choices,
        inputs=[state],
        outputs=[detail_batch_box],
    )

    # 退出
    def _logout_click(s):
        s_new, login_vis, dash_vis, msg, id_box, batch_box, sn_box = do_logout(s)
        return (
            s_new,
            login_vis,
            dash_vis,
            gr.update(value=msg),
            id_box,
            batch_box,
            sn_box,
        )

    logout_btn.click(
        _logout_click,
        inputs=[state],
        outputs=[state, login_view, dashboard_view, login_msg,
                 login_id_input, sn_batch_box, sn_input_box],
    ).then(
        lambda: (gr.update(value=""),) * 8,
        outputs=[nav_bar, update_date_md, card_total, card_activated,
                 card_landing, card_active, card_act_reward, card_unactivated],
    )

    # SN 搜索
    sn_search_btn.click(
        do_sn_search,
        inputs=[sn_input_box, sn_status_box, sn_batch_box, state],
        outputs=[sn_msg, sn_table, sn_detail_html, sn_cards_html, sn_msg],
    )

    # 设备明细查询
    detail_query_btn.click(
        do_device_search,
        inputs=[detail_status_box, detail_batch_box, state],
        outputs=[detail_table, download_file, detail_caption],
    )


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=int(os.environ.get("PORT", 7860)),
        show_error=True,
        css=_CUSTOM_CSS,
        theme=gr.themes.Soft(primary_hue=gr.themes.colors.orange),
    )