# 微信盒子代理商奖励分析平台

> 基于发货数据 + 微信后台激活数据，匹配每个代理商的拿货量与三项奖励达标情况。

## 🎯 功能概览

### 管理端 (app.py)
- 全量数据分析、政策参数在线调整、可视化看板
- 漏斗式全局汇总、代理商汇总概览、三项奖励达标分布
- 导出 Excel（按代理商 / 设备明细 / 全局汇总）

### 渠道商看板 (dashboard.py)
- **登录认证**：代理商输入编号登录，数据隔离
- **2×2 数字摘要**：拿货/激活/落地达标/活跃达标，带百分比徽章
- **SN 查询**：模糊搜索设备，卡片化展示激活状态与奖励详情
- **设备明细**：状态+批次筛选，在线下载 Excel
- **橙色主题 UI**：参考竞品设计的卡片化界面

### CLI (cli.py)
- 命令行批量分析导出，适合定时任务

## 📁 项目结构

```
wechat_box_analysis/
├── app.py                   # 管理端 Streamlit 应用
├── dashboard.py             # 渠道商看板（对外）
├── cli.py                   # 命令行版本
├── core/
│   ├── policy.py            # 政策常量
│   ├── data_loader.py       # 数据加载与列识别
│   └── analyzer.py          # 奖励计算引擎
├── .streamlit/config.toml   # Streamlit 配置（主题色等）
├── sample_data/             # 示例数据
├── requirements.txt
└── README.md
```

## 🚀 本地运行

```bash
pip install -r requirements.txt

# 管理端
streamlit run app.py

# 渠道商看板
streamlit run dashboard.py --server.port 8502
```

## ☁️ 部署到 Streamlit Community Cloud

### 步骤 1：推送到 GitHub

```bash
cd wechat_box_analysis
git init
git add -A
git commit -m "Initial commit"

# 在 GitHub 上创建一个新仓库（Public），然后：
git remote add origin https://github.com/<你的用户名>/<仓库名>.git
git branch -M main
git push -u origin main
```

### 步骤 2：在 Streamlit Cloud 部署

1. 访问 [share.streamlit.io](https://share.streamlit.io)
2. 点击 **New app**
3. 选择你的 GitHub 仓库
4. **Main file path** 填写 `dashboard.py`（渠道商看板）或 `app.py`（管理端）
5. 点击 **Deploy**

部署完成后会获得一个公网访问地址，如：
`https://<用户名>-wechat-box-analysis-dashboard.streamlit.app`

### 数据加载说明

- **本地运行**：将数据文件放入 `data/` 目录（发货数据.xlsx + 激活数据.csv），看板自动加载
- **云端运行**：通过侧边栏上传发货数据和激活数据文件
- 真实数据文件已通过 .gitignore 排除，不会提交到公共仓库

## 📊 三项奖励政策

| 奖励 | 条件 | 金额 |
| --- | --- | --- |
| 🎯 落地技术服务费 | 单月有效订单 ≥ 300 且 月活用户 ≥ 20 | 200 元/台 |
| 📈 活跃技术服务费 | 有效交易实收金额 × 0.16%，分两档封顶 | 10/50 元/月 |
| 🏆 激活达标技术服务费 | 月订单 ≥ 300 + 月活 ≥ 20 + 有效天数 ≥ 7 + 机构/非机构激活总量门槛 | 200 元/台 |

## ⚠️ 注意事项

1. 激活达标奖励需先满足机构累计激活 ≥ 20,000 台 或 非机构累计激活 ≥ 10,000 台总量门槛
2. 激活数据为每日快照型（同 SN 多行），程序自动取最新一天数据
3. 列名支持模糊匹配，详见 `core/data_loader.py` 中的关键字列表
