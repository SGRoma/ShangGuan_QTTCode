# AIQuant 智能量化研究与模拟交易分析平台

本项目按 `AIQuant_Codex项目说明书_v1.0` 从零重建，是一个面向 MVP 的 AI + 量化 + 人工审核研究平台。

## 边界

- 不包含真实交易下单接口。
- 智能体只能生成候选内容、解释和复盘，不能直接替换正式策略或模型。
- 训练样本必须 `approved + can_train=true` 后才能进入正式训练数据集。
- 所有策略、数据集、模型、Prompt 和智能体输出都保留版本或日志。

## 技术栈

- 后端：FastAPI + SQLAlchemy + Pydantic + pandas + numpy
- 数据库：本地默认 SQLite，Docker Compose 提供 PostgreSQL
- 前端：React + TypeScript + Vite + ECharts
- 智能体：优先调用柏拉图 AI 平台 `https://api.bltcy.ai/v1/responses`，未配置 `BLTCY_API_KEY` 时自动使用本地结构化回退逻辑

## 本地启动

```powershell
cd D:\PythonProject\QTTest
python -m venv .venv
.\.venv\Scripts\pip install -r backend\requirements.txt
.\.venv\Scripts\python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

另开终端：

```powershell
cd D:\PythonProject\QTTest\frontend
npm install
npm run dev
```

访问：

- 前端：http://127.0.0.1:5173
- 后端 API：http://127.0.0.1:8000/docs
- 健康检查：http://127.0.0.1:8000/health

## 核心模块

- 研究操作台：一键初始化、股票监测、智能体生成策略、回测、样本沉淀、模型迭代、模拟盘刷新
- 股票研究：行情同步、技术指标计算
- 智能体工作台：结构化输出和 agent_run_log
- 策略实验：策略想法、审核、策略版本
- 回测结果：收益、回撤、交易明细、月度收益
- 训练数据审核：样本批准、拒绝、负样本
- 模型管理：多因子模型版本、训练、验证、提升、废弃
- 模拟交易：虚拟账户和信号看板
- 脏数据管理：标记、隔离、影响分析、污染模型追踪

## 推荐操作路径

1. 打开前端 `http://127.0.0.1:5173`。
2. 进入“研究操作台”，股票代码默认 `600418`。
3. 点击“初始化”生成默认数据、策略版本、回测、训练样本和模型。
4. 修改策略想法后点击“运行研究闭环”，系统会重新生成策略版本并更新回测和模拟盘。
5. 在“模拟盘”页面选择策略版本，点击“运行模拟盘”观察虚拟资产、持仓、成交和风控提示。

## Docker

```powershell
docker compose up --build
```

Docker 模式下后端默认使用 PostgreSQL，前端通过 Vite 代理访问 API。
