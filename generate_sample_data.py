# -*- coding: utf-8 -*-
"""
生成示例发货数据 + 激活数据，便于演示与测试。
运行：python generate_sample_data.py
"""

import random
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

random.seed(42)
OUT = Path(__file__).parent / "sample_data"
OUT.mkdir(parents=True, exist_ok=True)

# 30 个代理商、5 个区域
REGIONS = ["安徽", "广东", "上海", "北京", "四川"]
AGENTS_PER_REGION = {
    "安徽": [("许朋", "0001"), ("李伟", "0002"), ("王强", "0003"), ("赵敏", "0004"), ("陈丽", "0005"), ("孙浩", "0006")],
    "广东": [("林浩宇", "0101"), ("黄丽华", "0102"), ("张伟", "0103"), ("陈志强", "0104"), ("刘敏", "0105")],
    "上海": [("周敏", "0201"), ("钱文博", "0202"), ("吴俊", "0203"), ("郑文", "0204")],
    "北京": [("王磊", "0301"), ("冯子轩", "0302"), ("李欣", "0303"), ("韩雪", "0304")],
    "四川": [("杨柳", "0401"), ("何佳", "0402"), ("马腾", "0403"), ("罗红", "0404"), ("高远", "0405")],
}

# 1) 发货数据 ---------------------------------------------------------
shipping_rows = []
iccid_prefix = "8986082"
imei_prefix = "86571908"

for region, agents in AGENTS_PER_REGION.items():
    for agent_name, agent_id in agents:
        n_shipped = random.randint(40, 200)
        for i in range(n_shipped):
            sn = f"7GO56KBFJV*{random.choice(['B7','C7','D7','E7'])}{random.randint(100,999)}{chr(65+i%26)}M"
            iccid = iccid_prefix + "".join(random.choices("0123456789", k=15))
            imei = imei_prefix + "".join(random.choices("0123456789", k=8))
            # 备注
            sep = random.choice(["+", "-", " "])
            remark = f"{region}{sep}{agent_name} {agent_id}"
            shipping_rows.append({
                "设备贴纸设备号": sn,
                "ICCID": iccid,
                "IMEI": imei,
                "备注": remark,
            })

shipping_df = pd.DataFrame(shipping_rows)
shipping_df = shipping_df.drop_duplicates(subset=["设备贴纸设备号"])
shipping_df.to_csv(OUT / "发货数据-示例.csv", index=False, encoding="utf-8-sig")
print(f"发货数据：{len(shipping_df)} 行 → {OUT / '发货数据-示例.csv'}")

# 2) 激活数据 ---------------------------------------------------------
# 模拟 80% 设备被激活，达标情况分布：
#  - 40% 落地达标（订单≥300、用户≥20）
#  - 60% 活跃达标（订单≥300、用户≥20、天数≥7）
#  - 70% 激活达标（活跃达标 + 机构总量门槛）
activation_rows = []
for _, row in shipping_df.iterrows():
    sn = row["设备贴纸设备号"]
    if random.random() < 0.2:
        # 未激活
        activation_rows.append({
            "设备SN": sn,
            "采购时间": (date(2026, 4, 15) + timedelta(days=random.randint(0, 90))).isoformat(),
            "激活时间": "",
            "有效交易订单数(月)": 0,
            "有效交易订单实收金额(月)": 0.0,
            "月活用户数": 0,
            "有效天数": 0,
            "7天有效订单": 0,
            "30天有效订单": 0,
            "是否机构": random.choice(["是", "否"]),
        })
        continue

    # 70% 设备被分配为 5 月份采购（前），30% 6 月份后（叠加不可）
    purchase = date(2026, 4, 1) + timedelta(days=random.randint(0, 80))
    if random.random() < 0.3:
        purchase = date(2026, 7, 1) + timedelta(days=random.randint(0, 30))

    # 达标情况
    r = random.random()
    if r < 0.30:
        # 全部不达标
        orders = random.randint(0, 250)
        users = random.randint(0, 18)
        amount = orders * random.uniform(5, 50)
        days = random.randint(0, 6)
    elif r < 0.55:
        # 仅活跃达标（无有效天数）
        orders = random.randint(300, 800)
        users = random.randint(20, 60)
        amount = orders * random.uniform(20, 80)
        days = random.randint(0, 6)
    elif r < 0.80:
        # 落地 + 活跃
        orders = random.randint(300, 1500)
        users = random.randint(20, 80)
        amount = orders * random.uniform(20, 100)
        days = random.randint(7, 30)
    else:
        # 全部达标
        orders = random.randint(500, 2000)
        users = random.randint(20, 100)
        amount = orders * random.uniform(20, 100)
        days = random.randint(7, 30)

    activation_rows.append({
        "设备SN": sn,
        "采购时间": purchase.isoformat(),
        "激活时间": (purchase + timedelta(days=random.randint(1, 14))).isoformat(),
        "有效交易订单数(月)": orders,
        "有效交易订单实收金额(月)": round(amount, 2),
        "月活用户数": users,
        "有效天数": days,
        "7天有效订单": int(orders * 0.25),
        "30天有效订单": int(orders * 0.85),
        "是否机构": random.choice(["是", "否"]),
    })

activation_df = pd.DataFrame(activation_rows)
activation_df = activation_df.drop_duplicates(subset=["设备SN"])
activation_df.to_csv(OUT / "激活数据-示例.csv", index=False, encoding="utf-8-sig")
print(f"激活数据：{len(activation_df)} 行 → {OUT / '激活数据-示例.csv'}")
print(f"已激活：{len(activation_df[activation_df['有效交易订单数(月)'] > 0])}")
print(f"总代理商数：{shipping_df['备注'].nunique()}")
