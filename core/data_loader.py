# -*- coding: utf-8 -*-
"""
数据加载与清洗模块
==================
提供两个主要函数：
  * load_shipping_data(file)        - 读取「发货数据」Excel/CSV
  * load_activation_data(file)      - 读取「微信后台下载每日激活数据」Excel/CSV

针对列名兼容多种命名（微信后台导出列名经常调整），做关键字模糊匹配。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import IO, Union

import pandas as pd


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def _read_any(file: Union[str, Path, IO[bytes]]) -> pd.DataFrame:
    """根据扩展名选择 Excel 或 CSV 读取。"""
    if hasattr(file, "name"):
        name = file.name
    else:
        name = str(file)

    name_lower = name.lower()
    if name_lower.endswith((".xlsx", ".xls", ".xlsm")):
        return pd.read_excel(file)
    if name_lower.endswith(".csv"):
        # 尝试多种编码
        for enc in ("utf-8", "utf-8-sig", "gbk", "gb18030"):
            try:
                if hasattr(file, "seek"):
                    file.seek(0)
                return pd.read_csv(file, encoding=enc)
            except (UnicodeDecodeError, pd.errors.EmptyDataError):
                continue
        return pd.read_csv(file, encoding="utf-8", encoding_errors="ignore")
    # 默认按 Excel 尝试
    return pd.read_excel(file)


def _first_match(columns, keywords):
    """在列名中查找第一个包含任一关键字（不区分大小写）的列。"""
    lowered = [str(c).lower() for c in columns]
    for kw in keywords:
        kw_low = kw.lower()
        for i, col in enumerate(lowered):
            if kw_low in col:
                return columns[i]
    return None


# ---------------------------------------------------------------------------
# 发货数据
# ---------------------------------------------------------------------------

# 设备号列关键字
SN_KEYWORDS = ["设备号", "设备贴纸", "sn", "device", "贴纸设备"]
# ICCID 列
ICCID_KEYWORDS = ["iccid"]
# IMEI 列
IMEI_KEYWORDS = ["imei"]
# 发货批次 / 备注列（用于解析区域+代理商+批次号）
REMARK_KEYWORDS = ["发货批次", "备注", "批次", "remark"]
# 代理商名称列（显式列，优先使用）
AGENT_NAME_KEYWORDS = ["代理商名称", "代理名称", "agent_name", "客户名称", "代理商"]
# 代理商编号列（显式列，优先使用）
AGENT_ID_KEYWORDS = ["代理商编号", "代理编号", "agent_id", "客户编号"]
# 业务线列
BIZ_LINE_KEYWORDS = ["业务线", "业务"]
# 销售人员列
SALES_KEYWORDS = ["销售", "销售员", "业务员"]


def parse_agent_short(remark: str):
    """
    从发货批次字符串中提取代理商简称。
    例如：
      "安徽+许朋 0001"              -> "许朋"
      "北京+韩强DPK365050819131"   -> "韩强"
      "广东+深圳市中汇  005"        -> "深圳市中汇"
    解析失败时返回原始字符串。
    """
    if not isinstance(remark, str):
        return str(remark) if remark is not None else None

    text = remark.strip()
    if not text:
        return None

    # 去掉第一个分隔符之前的部分（区域前缀）
    sep_match = re.search(r"[+\-/]", text)
    if sep_match:
        rest = text[sep_match.end():].strip()
    else:
        rest = text

    # 去掉尾部编号（字母前缀+数字 或 纯数字）
    num_match = re.search(r"[A-Za-z]*\d{4,}\s*$", rest)
    if num_match:
        agent = rest[: num_match.start()].strip(" +-_/、,，")
    else:
        agent = rest.strip(" +-_/、,，")

    return agent or None


def load_shipping_data(file) -> pd.DataFrame:
    """
    加载发货数据并做标准化。
    返回列：sn, iccid, imei, remark, agent, batch_no,
            agent_name, agent_id, biz_line, sales

    - batch_no: 直接取「发货批次」列原始值
    - agent:    从发货批次中提取的代理商简称（仅辅助展示）
    - agent_name: 优先使用显式「代理商名称」列
    - agent_id:   优先使用显式「代理商编号」列
    """
    df = _read_any(file)
    cols = list(df.columns)

    sn_col = _first_match(cols, SN_KEYWORDS)
    iccid_col = _first_match(cols, ICCID_KEYWORDS)
    imei_col = _first_match(cols, IMEI_KEYWORDS)
    remark_col = _first_match(cols, REMARK_KEYWORDS)
    agent_name_col = _first_match(cols, AGENT_NAME_KEYWORDS)
    agent_id_col = _first_match(cols, AGENT_ID_KEYWORDS)
    biz_line_col = _first_match(cols, BIZ_LINE_KEYWORDS)
    sales_col = _first_match(cols, SALES_KEYWORDS)

    if sn_col is None:
        raise ValueError(
            "未在发货数据中识别到「设备号」列，请确认列名包含："
            f"{SN_KEYWORDS} 之一。当前列：{cols}"
        )

    out = pd.DataFrame()
    out["sn"] = df[sn_col].astype(str).str.strip()

    out["iccid"] = df[iccid_col].astype(str).str.strip() if iccid_col else None
    out["imei"] = df[imei_col].astype(str).str.strip() if imei_col else None

    # 发货批次/备注（batch_no 直接取原始值）
    if remark_col:
        out["remark"] = df[remark_col].astype(str).str.strip()
        out["batch_no"] = out["remark"]  # 批次编号 = 发货批次原始值
        out["agent"] = out["remark"].apply(parse_agent_short)
    else:
        out["remark"] = None
        out["batch_no"] = None
        out["agent"] = None

    # 代理商名称（显式列优先）
    if agent_name_col:
        out["agent_name"] = df[agent_name_col].astype(str).str.strip()
    else:
        out["agent_name"] = out["agent"]  # 回退到解析的简称

    # 代理商编号（显式列优先）
    if agent_id_col:
        out["agent_id"] = df[agent_id_col].astype(str).str.strip()
    else:
        out["agent_id"] = None

    # 业务线
    out["biz_line"] = df[biz_line_col].astype(str).str.strip() if biz_line_col else None
    # 销售
    out["sales"] = df[sales_col].astype(str).str.strip() if sales_col else None

    # 丢弃空 SN
    out = out[out["sn"].str.len() > 0].copy()
    out = out.drop_duplicates(subset=["sn"], keep="last").reset_index(drop=True)
    return out


# ---------------------------------------------------------------------------
# 激活数据
# ---------------------------------------------------------------------------

# 后台导出的列名可能千变万化，给出常见关键字
# 关键词按优先级排列：累计有效 > 累计 > 当日（政策要求用累计有效数据）
ACT_SN_KEYWORDS = ["sn", "设备号", "设备贴纸", "贴纸设备号", "终端号", "设备sn"]
ACT_ORDERS_KEYWORDS = [
    "累计有效交易笔数", "累计有效交易", "有效交易订单", "累计交易笔数",
    "订单数", "有效订单", "交易笔数", "订单",
]
ACT_AMOUNT_KEYWORDS = [
    "累计有效交易金额", "累计有效交易", "有效交易金额", "累计交易金额",
    "实收金额", "交易金额", "金额",
]
ACT_USERS_KEYWORDS = [
    "累计交易用户数", "累计交易用户", "月活用户", "累计用户数",
    "交易用户数", "用户数", "活用户",
]
ACT_DAYS_KEYWORDS = ["有效天数", "活跃天数", "有效日", "有效天"]
ACT_DATE_KEYWORDS = ["首笔交易日期", "首笔交易", "激活日期", "激活时间", "首活日期", "首次激活"]
ACT_PURCHASE_KEYWORDS = ["采购时间", "采购日期", "发货时间", "发货日期"]
ACT_INSTITUTION_KEYWORDS = ["机构", "是否机构"]
# 微信后台直接提供的激活标志位
ACT_ACTIVATED_FLAG_KEYWORDS = ["是否激活", "激活状态", "已激活"]
# 统计日期（快照日期）
ACT_SNAPSHOT_DATE_KEYWORDS = ["统计日期", "数据日期", "快照日期", "报表日期"]
# 沉睡天数（用于反推有效天数）
ACT_SLEEP_DAYS_KEYWORDS = ["沉睡天数", "休眠天数"]


def _parse_wechat_date(series):
    """
    解析微信后台日期列，兼容多种格式：
      - 20260804 / 20260804.0 (数字 YYYYMMDD，会被 pandas 误认为纳秒时间戳)
      - 2026-08-04 / 2026/08/04 (标准日期)
      - 2026-08-04 12:00:00 (日期时间)
    """
    if series is None:
        return None

    # 微信后台日期常以纯数字 YYYYMMDD 存储（int 或 float）
    # pd.to_datetime 会把数字当纳秒时间戳，所以先转字符串
    if pd.api.types.is_numeric_dtype(series):
        str_series = series.astype("Int64").astype(str).str.strip()
        str_series = str_series.where(str_series != "<NA>", None)
        return pd.to_datetime(str_series, format="%Y%m%d", errors="coerce")

    # 字符串类型：先尝试标准解析
    result = pd.to_datetime(series, errors="coerce")

    # 如果成功率低，尝试 YYYYMMDD 字符串格式
    total = len(series)
    if total > 0 and result.notna().sum() < total * 0.5:
        str_series = series.astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
        result2 = pd.to_datetime(str_series, format="%Y%m%d", errors="coerce")
        mask = result.isna() & result2.notna()
        result[mask] = result2[mask]

    return result


def load_activation_data(file, snapshot_mode: str = "latest") -> pd.DataFrame:
    """
    加载激活数据并标准化。
    返回列：sn, purchase_date, first_active_date, snapshot_date,
           activated_flag, monthly_orders, monthly_amount,
           monthly_active_users, monthly_active_days, is_institution

    snapshot_mode: 数据聚合策略（同一 SN 出现多行时）
      - "latest": 取最新一条（适合每日下载的「快照」数据）
      - "sum":    累加所有行（适合每日下载的「增量」数据）
    """
    df = _read_any(file)
    cols = list(df.columns)

    sn_col = _first_match(cols, ACT_SN_KEYWORDS)
    if sn_col is None:
        raise ValueError(
            "未在激活数据中识别到「设备 SN」列，请确认列名包含："
            f"{ACT_SN_KEYWORDS} 之一。当前列：{cols}"
        )

    out = pd.DataFrame()
    out["sn"] = df[sn_col].astype(str).str.strip()

    # 解析日期
    def _maybe_date(keywords):
        c = _first_match(cols, keywords)
        if c is None:
            return None, None
        return c, _parse_wechat_date(df[c])

    purchase_col, purchase_series = _maybe_date(ACT_PURCHASE_KEYWORDS)
    active_col, active_series = _maybe_date(ACT_DATE_KEYWORDS)
    snapshot_col, snapshot_series = _maybe_date(ACT_SNAPSHOT_DATE_KEYWORDS)

    out["purchase_date"] = purchase_series
    out["first_active_date"] = active_series
    # 快照日期：优先用统计日期，否则用首笔交易日期
    out["_snapshot_date"] = snapshot_series if snapshot_series is not None else active_series

    def _maybe_num(keywords):
        c = _first_match(cols, keywords)
        if c is None:
            return None, None
        return c, pd.to_numeric(df[c], errors="coerce")

    _, orders_series = _maybe_num(ACT_ORDERS_KEYWORDS)
    _, amount_series = _maybe_num(ACT_AMOUNT_KEYWORDS)
    _, users_series = _maybe_num(ACT_USERS_KEYWORDS)
    _, days_series = _maybe_num(ACT_DAYS_KEYWORDS)

    out["monthly_orders"] = orders_series.fillna(0) if orders_series is not None else 0
    out["monthly_amount"] = amount_series.fillna(0) if amount_series is not None else 0
    out["monthly_active_users"] = users_series.fillna(0) if users_series is not None else 0
    out["monthly_active_days"] = days_series.fillna(0) if days_series is not None else 0

    # ---- 是否激活标志位（微信后台直接提供 0/1）----
    activated_flag_col = _first_match(cols, ACT_ACTIVATED_FLAG_KEYWORDS)
    if activated_flag_col is not None:
        flag_val = pd.to_numeric(df[activated_flag_col], errors="coerce").fillna(0)
        out["activated_flag"] = flag_val.astype(int) == 1
    else:
        out["activated_flag"] = None  # 无此列时后续用 first_active_date 判断

    inst_col = _first_match(cols, ACT_INSTITUTION_KEYWORDS)
    if inst_col is not None:
        v = df[inst_col].astype(str).str.strip()
        out["is_institution"] = v.isin(["是", "1", "yes", "true", "Y", "机构", "True"])
    else:
        out["is_institution"] = False

    out = out[out["sn"].str.len() > 0].copy()

    # ---- 如果没有「有效天数」列，从首笔交易日期到统计日期计算 ----
    if days_series is None and active_series is not None:
        snapshot_for_calc = snapshot_series if snapshot_series is not None else pd.Timestamp.now()
        active_days_calc = (snapshot_for_calc - active_series).dt.days
        out["monthly_active_days"] = active_days_calc.fillna(0).clip(lower=0).astype(int)

    # ---- 同一 SN 多行处理 ----
    if out["sn"].duplicated().any():
        if snapshot_mode == "latest":
            # 取最新（按 _snapshot_date 倒序，再保留 first）
            out = out.sort_values(["sn", "_snapshot_date"], ascending=[True, False])
            out = out.drop_duplicates(subset=["sn"], keep="first")
        else:
            # 累加所有行
            agg_dict = {
                "monthly_orders": "sum",
                "monthly_amount": "sum",
                "monthly_active_users": "max",
                "monthly_active_days": "max",
                "is_institution": "max",
            }
            if "activated_flag" in out.columns:
                agg_dict["activated_flag"] = "max"
            if "purchase_date" in out.columns:
                agg_dict["purchase_date"] = "min"
            if "first_active_date" in out.columns:
                agg_dict["first_active_date"] = "min"
            out = out.groupby("sn", as_index=False).agg(agg_dict)
    else:
        out = out.drop_duplicates(subset=["sn"], keep="last")

    out = out.drop(columns=["_snapshot_date"], errors="ignore").reset_index(drop=True)
    return out


# ---------------------------------------------------------------------------
# 列识别调试助手（用于 UI 提示）
# ---------------------------------------------------------------------------

def detect_columns(df: pd.DataFrame) -> dict:
    """返回识别到的关键列，便于在 UI 提示用户。"""
    cols = list(df.columns)
    return {
        "sn": _first_match(cols, SN_KEYWORDS + ACT_SN_KEYWORDS),
        "iccid": _first_match(cols, ICCID_KEYWORDS),
        "imei": _first_match(cols, IMEI_KEYWORDS),
        "remark": _first_match(cols, REMARK_KEYWORDS),
        "agent_name": _first_match(cols, AGENT_NAME_KEYWORDS),
        "agent_id": _first_match(cols, AGENT_ID_KEYWORDS),
        "biz_line": _first_match(cols, BIZ_LINE_KEYWORDS),
        "sales": _first_match(cols, SALES_KEYWORDS),
        "purchase_date": _first_match(cols, ACT_PURCHASE_KEYWORDS),
        "first_active_date": _first_match(cols, ACT_DATE_KEYWORDS),
        "activated_flag": _first_match(cols, ACT_ACTIVATED_FLAG_KEYWORDS),
        "snapshot_date": _first_match(cols, ACT_SNAPSHOT_DATE_KEYWORDS),
        "monthly_orders": _first_match(cols, ACT_ORDERS_KEYWORDS),
        "monthly_amount": _first_match(cols, ACT_AMOUNT_KEYWORDS),
        "monthly_active_users": _first_match(cols, ACT_USERS_KEYWORDS),
        "monthly_active_days": _first_match(cols, ACT_DAYS_KEYWORDS),
        "is_institution": _first_match(cols, ACT_INSTITUTION_KEYWORDS),
    }
