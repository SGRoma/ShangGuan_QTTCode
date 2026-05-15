from datetime import date, datetime
from typing import Any

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def now() -> datetime:
    return datetime.utcnow()


class StockBasic(Base):
    __tablename__ = "stock_basic"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    stock_code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    stock_name: Mapped[str] = mapped_column(String(100))
    exchange: Mapped[str | None] = mapped_column(String(20), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(100), nullable=True)
    list_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)


class StockDailyPrice(Base):
    __tablename__ = "stock_daily_price"
    __table_args__ = (UniqueConstraint("stock_code", "trade_date", name="uq_stock_daily"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    stock_code: Mapped[str] = mapped_column(String(20), index=True)
    trade_date: Mapped[date] = mapped_column(Date, index=True)
    open: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    high: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    low: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    close: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    pre_close: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    volume: Mapped[float | None] = mapped_column(Numeric(20, 4), nullable=True)
    amount: Mapped[float | None] = mapped_column(Numeric(20, 4), nullable=True)
    adj_factor: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    data_source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class StockFactorDaily(Base):
    __tablename__ = "stock_factor_daily"
    __table_args__ = (UniqueConstraint("stock_code", "trade_date", "feature_version", name="uq_stock_factor_version"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    stock_code: Mapped[str] = mapped_column(String(20), index=True)
    trade_date: Mapped[date] = mapped_column(Date, index=True)
    pe: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    pb: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    roe: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    market_cap: Mapped[float | None] = mapped_column(Numeric(20, 4), nullable=True)
    ma5: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    ma20: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    ma60: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    rsi: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    macd: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    volume_ratio: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    volatility_20d: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    momentum_20d: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    feature_version: Mapped[str] = mapped_column(String(50), default="feature_v1")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class StrategyIdea(Base):
    __tablename__ = "strategy_idea"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(50), default="user_input")
    status: Mapped[str] = mapped_column(String(50), default="candidate", index=True)
    review_status: Mapped[str] = mapped_column(String(50), default="pending")
    can_train: Mapped[bool] = mapped_column(Boolean, default=False)
    can_trade: Mapped[bool] = mapped_column(Boolean, default=False)
    risk_level: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)

    versions: Mapped[list["StrategyVersion"]] = relationship(back_populates="idea")


class StrategyVersion(Base):
    __tablename__ = "strategy_version"
    __table_args__ = (UniqueConstraint("strategy_idea_id", "version", name="uq_strategy_version"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    strategy_idea_id: Mapped[int | None] = mapped_column(ForeignKey("strategy_idea.id"), nullable=True)
    version: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(200))
    logic_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    parameters_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    entry_rules_json: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)
    exit_rules_json: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)
    risk_rules_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    parent_version_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="experiment")
    change_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)

    idea: Mapped[StrategyIdea | None] = relationship(back_populates="versions")
    backtests: Mapped[list["BacktestResult"]] = relationship(back_populates="strategy_version")


class BacktestResult(Base):
    __tablename__ = "backtest_result"

    id: Mapped[int] = mapped_column(primary_key=True)
    strategy_version_id: Mapped[int] = mapped_column(ForeignKey("strategy_version.id"), index=True)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    initial_cash: Mapped[float | None] = mapped_column(Numeric(20, 4), nullable=True)
    final_value: Mapped[float | None] = mapped_column(Numeric(20, 4), nullable=True)
    total_return: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    annual_return: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    max_drawdown: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    sharpe_ratio: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    win_rate: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    profit_loss_ratio: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    trade_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    turnover_rate: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    benchmark_return: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    excess_return: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    result_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    strategy_version: Mapped[StrategyVersion] = relationship(back_populates="backtests")


class DatasetVersion(Base):
    __tablename__ = "dataset_version"
    __table_args__ = (UniqueConstraint("dataset_name", "version", name="uq_dataset_version"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    dataset_name: Mapped[str] = mapped_column(String(200))
    version: Mapped[str] = mapped_column(String(50))
    sample_count: Mapped[int] = mapped_column(Integer, default=0)
    approved_sample_count: Mapped[int] = mapped_column(Integer, default=0)
    excluded_sample_count: Mapped[int] = mapped_column(Integer, default=0)
    feature_config_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    label_config_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="draft")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    samples: Mapped[list["TrainingSample"]] = relationship(back_populates="dataset_version")


class DataModelDefinition(Base):
    __tablename__ = "data_model_definition"
    __table_args__ = (UniqueConstraint("name", "version", name="uq_data_model_definition"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    version: Mapped[str] = mapped_column(String(50))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    feature_version: Mapped[str] = mapped_column(String(50), default="feature_v1")
    pipeline_config_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    schedule_config_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="active", index=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_run_summary_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)


class AnalysisModelDefinition(Base):
    __tablename__ = "analysis_model_definition"
    __table_args__ = (UniqueConstraint("name", "version", name="uq_analysis_model_definition"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    version: Mapped[str] = mapped_column(String(50))
    model_family: Mapped[str] = mapped_column(String(100), default="trend_momentum")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_data_model_id: Mapped[int | None] = mapped_column(ForeignKey("data_model_definition.id"), nullable=True)
    parameters_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    entry_rules_json: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)
    exit_rules_json: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)
    risk_rules_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    capability_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)


class TrainingSample(Base):
    __tablename__ = "training_sample"

    id: Mapped[int] = mapped_column(primary_key=True)
    dataset_version_id: Mapped[int | None] = mapped_column(ForeignKey("dataset_version.id"), nullable=True, index=True)
    sample_type: Mapped[str] = mapped_column(String(100))
    stock_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    trade_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    features_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    label_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    sample_weight: Mapped[float] = mapped_column(Float, default=1.0)
    source_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quality_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="candidate")
    can_train: Mapped[bool] = mapped_column(Boolean, default=False)
    reviewed_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    dataset_version: Mapped[DatasetVersion | None] = relationship(back_populates="samples")


class QuantModelVersion(Base):
    __tablename__ = "quant_model_version"
    __table_args__ = (UniqueConstraint("model_name", "version", name="uq_quant_model_version"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    model_name: Mapped[str] = mapped_column(String(200))
    version: Mapped[str] = mapped_column(String(50))
    model_type: Mapped[str] = mapped_column(String(100))
    dataset_version_id: Mapped[int | None] = mapped_column(ForeignKey("dataset_version.id"), nullable=True)
    feature_config_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    model_config_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    training_metrics_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    validation_metrics_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    backtest_metrics_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    model_artifact_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="experiment")
    data_contaminated: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)


class DirtyDataRecord(Base):
    __tablename__ = "dirty_data_record"

    id: Mapped[int] = mapped_column(primary_key=True)
    target_type: Mapped[str] = mapped_column(String(100), index=True)
    target_id: Mapped[int] = mapped_column(Integer, index=True)
    dirty_type: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    action: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="open")
    created_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    resolved_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class AgentRunLog(Base):
    __tablename__ = "agent_run_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_name: Mapped[str] = mapped_column(String(100), index=True)
    user_input: Mapped[str | None] = mapped_column(Text, nullable=True)
    agent_output: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    tools_called_json: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)
    related_entity_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    related_entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class PromptVersion(Base):
    __tablename__ = "prompt_version"
    __table_args__ = (UniqueConstraint("prompt_name", "version", name="uq_prompt_version"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    prompt_name: Mapped[str] = mapped_column(String(200))
    version: Mapped[str] = mapped_column(String(50))
    agent_name: Mapped[str] = mapped_column(String(100))
    system_prompt: Mapped[str] = mapped_column(Text)
    output_schema_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class FeatureDefinition(Base):
    __tablename__ = "feature_definition"

    id: Mapped[int] = mapped_column(primary_key=True)
    feature_name: Mapped[str] = mapped_column(String(100), unique=True)
    feature_group: Mapped[str | None] = mapped_column(String(100), nullable=True)
    calculation_logic: Mapped[str] = mapped_column(Text)
    lookback_window: Mapped[int | None] = mapped_column(Integer, nullable=True)
    data_source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    leakage_risk_level: Mapped[str] = mapped_column(String(50), default="low")
    status: Mapped[str] = mapped_column(String(50), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
