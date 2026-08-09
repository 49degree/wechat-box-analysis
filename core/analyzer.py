# -*- coding: utf-8 -*-
"""
奖励分析计算引擎
================
输入：
  * shipping_df: load_shipping_data() 输出
  * activation_df: load_activation_data() 输出

输出（analyze()）：
  per_device: 每台设备一条记录，包含三项奖励的达标情况和预计金额
  per_agent:  按代理商聚合后的统计
  summary:    全局汇总
"""

from __future__ import annotations

from typing import Tuple

import pandas as pd

from . import policy as P


# ---------------------------------------------------------------------------
# 单设备奖励计算
# ---------------------------------------------------------------------------

def compute_device_rewards(row: pd.Series) -> pd.Series:
    """
    计算单台设备的三个奖励的达标情况和预计金额。
    入参是一行 merged dataframe，包含：
      monthly_orders, monthly_amount, monthly_active_users,
      monthly_active_days
    """
    orders = float(row.get("monthly_orders", 0) or 0)
    amount = float(row.get("monthly_amount", 0) or 0)
    users = float(row.get("monthly_active_users", 0) or 0)
    days = float(row.get("monthly_active_days", 0) or 0)

    # ---- 1. 落地技术服务费 ----
    is_landing = (orders >= P.LANDING_MIN_ORDERS) and (users >= P.LANDING_MIN_ACTIVE_USERS)
    landing_fee = P.LANDING_FEE_PER_DEVICE if is_landing else 0.0

    # ---- 2. 活跃技术服务费 ----
    raw_activity = amount * P.ACTIVITY_FEE_RATE
    if orders < P.LANDING_MIN_ORDERS:
        cap = P.ACTIVITY_FEE_TIER1_CAP
    else:
        cap = P.ACTIVITY_FEE_TIER2_CAP
    activity_fee = round(min(raw_activity, cap), 2)
    # 单台累计上限（按当前快照）
    activity_fee = round(min(activity_fee, P.ACTIVITY_FEE_TOTAL_CAP), 2)

    # ---- 3. 激活达标技术服务费 ----
    is_activation = (
        (orders >= P.ACTIVATION_MIN_ORDERS)
        and (users >= P.ACTIVATION_MIN_ACTIVE_USERS)
        and (days >= P.ACTIVATION_MIN_ACTIVE_DAYS)
    )
    activation_fee = P.ACTIVATION_FEE_PER_DEVICE if is_activation else 0.0

    return pd.Series(
        {
            "is_landing_eligible": bool(is_landing),
            "landing_fee": landing_fee,
            "activity_fee": activity_fee,
            "activity_raw": round(raw_activity, 2),
            "is_activation_eligible": bool(is_activation),
            "activation_fee": activation_fee,
            "total_reward": round(
                landing_fee + activity_fee + activation_fee, 2
            ),
        }
    )


# ---------------------------------------------------------------------------
# 主分析函数
# ---------------------------------------------------------------------------

def analyze(
    shipping_df: pd.DataFrame,
    activation_df: pd.DataFrame,
) -> Tuple[pd.DataFrame, pd.DataFrame, dict]:
    """
    主入口：合并 + 奖励计算 + 多维聚合。
    """
    if shipping_df is None or shipping_df.empty:
        raise ValueError("发货数据为空")
    if activation_df is None or activation_df.empty:
        raise ValueError("激活数据为空")

    # 1) 合并 - 左连接发货表，缺失激活记录的设备视为"未激活"
    merged = shipping_df.merge(
        activation_df, on="sn", how="left", indicator=True
    )

    # 2) 激活标志：优先使用微信后台的「是否激活」标志位
    #    无标志位时退回到 first_active_date 不为空
    in_activation = (merged["_merge"] == "both")
    if "activated_flag" in merged.columns and merged["activated_flag"].notna().any():
        flag = merged["activated_flag"].fillna(False).astype(bool)
        merged["is_activated"] = in_activation & flag
    else:
        merged["is_activated"] = in_activation & (
            merged["first_active_date"].notna()
            & (merged["first_active_date"] != pd.NaT)
        )

    # 3) 缺失激活数据时填 0
    for col in [
        "monthly_orders", "monthly_amount", "monthly_active_users",
        "monthly_active_days",
    ]:
        if col not in merged.columns:
            merged[col] = 0
        merged[col] = pd.to_numeric(merged[col], errors="coerce").fillna(0)

    for col in ["purchase_date", "first_active_date"]:
        if col not in merged.columns:
            merged[col] = pd.NaT

    # 4) 机构判定 - 优先使用激活数据中的标记；否则按代理商名称启发式
    if "is_institution" in merged.columns:
        merged["is_institution"] = merged["is_institution"].fillna(False).astype(bool)
    else:
        merged["is_institution"] = False
    # 启发式：代理商名称包含"机构""分行""支行"等关键词时视为机构
    name_col = "agent_name" if "agent_name" in merged.columns else (
        "agent" if "agent" in merged.columns else None
    )
    if name_col:
        agent_str = merged[name_col].fillna("").astype(str)
        heuristic = agent_str.str.contains(
            r"机构|分行|支行|银行|银联|支付", regex=True, na=False
        )
        merged["is_institution"] = merged["is_institution"] | heuristic

    # 5) 计算每台设备的奖励
    rewards = merged.apply(compute_device_rewards, axis=1)
    per_device = pd.concat([merged.drop(columns=["_merge"]), rewards], axis=1)

    # 6) 机构/非机构激活总量门槛（仅统计已激活设备）
    activated_mask = per_device["is_activated"]
    institution_activated = int(
        (per_device["is_institution"] & activated_mask).sum()
    )
    non_institution_activated = int(
        (~per_device["is_institution"] & activated_mask).sum()
    )

    institution_meets = institution_activated >= P.INSTITUTION_ACTIVATION_THRESHOLD
    non_inst_meets = non_institution_activated >= P.NON_INSTITUTION_ACTIVATION_THRESHOLD

    # 机构或非机构任一满足则可参与激活达标奖励
    # 注：达标奖励本身只针对参与方计算
    per_device["activation_threshold_open"] = (
        (per_device["is_institution"] & institution_meets)
        | ((~per_device["is_institution"]) & non_inst_meets)
    )
    # 重新计算激活达标费：仅当门槛打开且单设备达标
    per_device["activation_fee"] = per_device.apply(
        lambda r: P.ACTIVATION_FEE_PER_DEVICE
        if (r["activation_threshold_open"] and r["is_activation_eligible"])
        else 0.0,
        axis=1,
    )
    per_device["total_reward"] = (
        per_device["landing_fee"]
        + per_device["activity_fee"]
        + per_device["activation_fee"]
    ).round(2)

    # ---------- 按代理商聚合 ----------
    display_name_col = "agent_name" if "agent_name" in per_device.columns else (
        "agent" if "agent" in per_device.columns else None
    )
    if display_name_col:
        per_device["agent_name"] = per_device[display_name_col].fillna("未指定")
    else:
        per_device["agent_name"] = "未指定"

    per_device["agent_key"] = per_device.apply(
        lambda r: f"{r.get('agent_name') or '未指定'}|{r.get('agent_id') or ''}",
        axis=1,
    )

    # 聚合辅助函数：把多行字符串合并去重为 "值1/值2"
    def _join_unique(s):
        vals = s.dropna().astype(str)
        vals = vals[vals != "None"]
        if vals.empty:
            return ""
        return "/".join(sorted(set(vals)))

    agent_agg = (
        per_device.groupby(["agent_name", "agent_id"], dropna=False)
        .agg(
            批次编号=("batch_no", _join_unique),
            拿货数量=("sn", "count"),
            已激活数量=("is_activated", "sum"),
            落地达标数量=("is_landing_eligible", "sum"),
            活跃达标数量=("is_activation_eligible", "sum"),
            激活达标数量=("activation_threshold_open", "sum"),  # 达到门槛的设备数
            激活达标实际奖励数量=("activation_fee", lambda s: int((s > 0).sum())),
            落地费总额=("landing_fee", "sum"),
            活跃费总额=("activity_fee", "sum"),
            激活达标费总额=("activation_fee", "sum"),
            预计总奖励=("total_reward", "sum"),
            月有效订单总数=("monthly_orders", "sum"),
            月有效交易总额=("monthly_amount", "sum"),
            业务线=("biz_line", _join_unique),
            销售=("sales", _join_unique),
        )
        .reset_index()
        .rename(columns={"agent_name": "代理商", "agent_id": "代理商编号"})
    )
    # 数值列取整
    for col in [
        "落地费总额", "活跃费总额",
        "激活达标费总额", "预计总奖励", "月有效交易总额",
    ]:
        agent_agg[col] = agent_agg[col].astype(float).round(2)
    for col in [
        "拿货数量", "已激活数量", "落地达标数量", "活跃达标数量",
        "激活达标数量", "激活达标实际奖励数量",
        "月有效订单总数",
    ]:
        agent_agg[col] = agent_agg[col].astype(int)

    # 列顺序：业务线/销售放第3,4列，批次编号放最后一列
    agent_agg = agent_agg[[
        "代理商", "代理商编号", "业务线", "销售",
        "拿货数量", "已激活数量", "落地达标数量", "活跃达标数量",
        "激活达标数量", "激活达标实际奖励数量",
        "落地费总额", "活跃费总额", "激活达标费总额", "预计总奖励",
        "月有效订单总数", "月有效交易总额",
        "批次编号",
    ]]

    # ---------- 全局汇总 ----------
    summary = {
        "拿货总数": int(per_device.shape[0]),
        "已激活数量": int(per_device["is_activated"].sum()),
        "未激活数量": int((~per_device["is_activated"]).sum()),
        "落地达标数量": int(per_device["is_landing_eligible"].sum()),
        "活跃达标数量": int(per_device["is_activation_eligible"].sum()),
        "激活达标奖励数量": int((per_device["activation_fee"] > 0).sum()),
        "落地费总额": round(float(per_device["landing_fee"].sum()), 2),
        "活跃费总额": round(float(per_device["activity_fee"].sum()), 2),
        "激活达标费总额": round(float(per_device["activation_fee"].sum()), 2),
        "预计总奖励": round(float(per_device["total_reward"].sum()), 2),
        "机构激活数": institution_activated,
        "非机构激活数": non_institution_activated,
        "机构门槛达成": bool(institution_meets),
        "非机构门槛达成": bool(non_inst_meets),
        "代理商数量": int(per_device["agent_key"].nunique()),
    }

    # ---------- 设备明细列顺序：biz_line/sales 放第3,4列，batch_no 放最后 ----------
    _front = ["sn", "agent_name", "biz_line", "sales"]
    _last = ["batch_no"]
    _mid = [c for c in per_device.columns if c not in _front and c not in _last]
    per_device = per_device[_front + _mid + _last]

    return per_device, agent_agg, summary
