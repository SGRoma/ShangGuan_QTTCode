# 数据库设计

MVP 已实现说明书中的核心表：

- `stock_basic`
- `stock_daily_price`
- `stock_factor_daily`
- `strategy_idea`
- `strategy_version`
- `backtest_result`
- `dataset_version`
- `training_sample`
- `quant_model_version`
- `dirty_data_record`
- `agent_run_log`
- `prompt_version`
- `feature_definition`

本地默认使用 SQLite 便于启动；生产或 Docker 环境通过 `DATABASE_URL` 使用 PostgreSQL。

