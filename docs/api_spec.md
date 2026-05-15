# API 摘要

## 股票数据

- `GET /api/stocks`
- `GET /api/stocks/{stock_code}`
- `GET /api/stocks/{stock_code}/daily`
- `GET /api/stocks/{stock_code}/factors`
- `POST /api/data/sync/daily`
- `POST /api/data/sync/factors`

## 策略

- `POST /api/strategies/ideas`
- `GET /api/strategies/ideas`
- `GET /api/strategies/ideas/{id}`
- `POST /api/strategies/ideas/{id}/review`
- `POST /api/strategies/versions`
- `GET /api/strategies/versions/{id}`
- `POST /api/strategies/versions/{id}/deprecate`

## 回测

- `POST /api/backtests/run`
- `GET /api/backtests/{id}`
- `GET /api/backtests/by-strategy/{strategy_version_id}`

## 一键研究工作流

- `POST /api/workflows/bootstrap`
- `POST /api/workflows/research-run`
- `POST /api/workflows/simulate`
- `GET /api/workflows/operation-state`
- `GET /api/workflows/stock-monitor/{stock_code}`

## 智能体

- `POST /api/agents/generate-strategy`
- `POST /api/agents/explain-backtest`
- `POST /api/agents/risk-review`
- `POST /api/agents/data-quality-review`
- `POST /api/agents/model-iteration-review`
- `GET /api/agents/logs`

## 数据治理

- `POST /api/datasets`
- `POST /api/datasets/{id}/samples`
- `POST /api/datasets/{id}/approve-samples`
- `POST /api/dirty-data/mark`
- `GET /api/dirty-data/{id}/impact`
