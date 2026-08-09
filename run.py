#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Railway/云平台启动脚本：用 Python 直接读取 PORT 环境变量，
避免 shell 变量展开问题。
"""
import os
import subprocess
import sys


def main() -> int:
    # Railway 会注入 PORT 环境变量，本地默认 8501
    port = os.environ.get("PORT", "8501")

    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        "dashboard.py",
        "--server.port",
        str(port),
        "--server.address",
        "0.0.0.0",
        "--server.headless",
        "true",
        "--browser.gatherUsageStats",
        "false",
    ]

    print(f"[start] PORT={port}", flush=True)
    print(f"[start] cmd={' '.join(cmd)}", flush=True)

    # 把 PORT 也显式注入到子进程环境（兼容 Nixpacks 自动注入 STREAMLIT_SERVER_PORT）
    env = os.environ.copy()
    env["STREAMLIT_SERVER_PORT"] = str(port)

    return subprocess.call(cmd, env=env)


if __name__ == "__main__":
    sys.exit(main())