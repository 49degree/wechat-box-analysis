# -*- coding: utf-8 -*-
"""
命令行版：直接对发货数据 + 激活数据进行分析，并输出 Excel 报告。
用法：
  python cli.py --shipping 发货数据.csv --activation 激活数据.csv --out 报告.xlsx
"""

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd

from core import data_loader, analyzer


def main():
    parser = argparse.ArgumentParser(
        description="微信盒子代理商奖励分析 - 命令行版"
    )
    parser.add_argument(
        "--shipping", required=True, help="发货数据文件路径 (xlsx/csv)"
    )
    parser.add_argument(
        "--activation", required=True, help="激活数据文件路径 (xlsx/csv)"
    )
    parser.add_argument(
        "--out", default="微信盒子奖励分析.xlsx", help="输出 Excel 路径"
    )
    parser.add_argument(
        "--snapshot-mode",
        choices=["latest", "sum"],
        default="latest",
        help="激活数据多行聚合方式：latest=取最新, sum=累加",
    )
    args = parser.parse_args()

    print(f"📦 加载发货数据: {args.shipping}")
    shipping_df = data_loader.load_shipping_data(args.shipping)
    print(f"   ✓ {len(shipping_df)} 行")

    print(f"📡 加载激活数据: {args.activation}")
    activation_df = data_loader.load_activation_data(
        args.activation, snapshot_mode=args.snapshot_mode
    )
    print(f"   ✓ {len(activation_df)} 行")

    print("🚀 开始分析...")
    per_device, per_agent, summary = analyzer.analyze(
        shipping_df, activation_df
    )

    print("\n===== 全局汇总 =====")
    for k, v in summary.items():
        print(f"  {k:25s}: {v}")

    print(f"\n💾 写入 Excel: {args.out}")
    with pd.ExcelWriter(args.out, engine="xlsxwriter") as writer:
        per_agent.to_excel(writer, sheet_name="按代理商", index=False)
        per_device.to_excel(writer, sheet_name="设备明细", index=False)
        pd.DataFrame([summary]).T.rename(columns={0: "值"}).to_excel(
            writer, sheet_name="全局汇总"
        )
    print(f"   ✓ 完成")


if __name__ == "__main__":
    main()
