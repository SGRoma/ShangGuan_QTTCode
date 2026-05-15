from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field


class StockSyncRequest(BaseModel):
    stock_code: str = "600418"
    stock_name: str | None = None
    start: str = "20240101"


class FactorSyncRequest(BaseModel):
    stock_code: str = "600418"
    feature_version: str = "feature_v1"


class StrategyIdeaCreate(BaseModel):
    title: str
    content: str
    source: str = "user_input"
    created_by: str | None = None


class StrategyIdeaUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    status: str | None = None
    risk_level: str | None = None
    remark: str | None = None


class StrategyReviewRequest(BaseModel):
    status: Literal["pending_review", "approved", "rejected", "negative_sample", "deprecated", "invalid"]
    can_train: bool = False
    can_trade: bool = False
    risk_level: str | None = None
    remark: str | None = None


class StrategyVersionCreate(BaseModel):
    strategy_idea_id: int | None = None
    version: str = "v1"
    name: str
    logic_json: dict[str, Any] = Field(default_factory=dict)
    parameters_json: dict[str, Any] = Field(default_factory=dict)
    entry_rules_json: list[Any] | None = None
    exit_rules_json: list[Any] | None = None
    risk_rules_json: dict[str, Any] | None = None
    status: str = "experiment"
    change_reason: str | None = None


class BacktestRunRequest(BaseModel):
    strategy_version_id: int
    stock_code: str = "600418"
    start_date: date | None = None
    end_date: date | None = None
    initial_cash: float = 1_000_000
    benchmark: str = "000300.SH"
    fee_rate: float = 0.0003
    slippage_rate: float = 0.001
    max_position_per_stock: float = 0.2
    max_holding_count: int = 10


class AgentRequest(BaseModel):
    user_input: str
    related_entity_type: str | None = None
    related_entity_id: int | None = None
    context: dict[str, Any] = Field(default_factory=dict)


class AgentConfigUpdate(BaseModel):
    enabled: bool | None = None
    auto_run: bool | None = None
    schedule: str | None = None
    timeout_seconds: int | None = None
    notes: str | None = None


class DatasetCreate(BaseModel):
    dataset_name: str
    version: str = "v1"
    feature_config_json: dict[str, Any] = Field(default_factory=dict)
    label_config_json: dict[str, Any] = Field(default_factory=dict)
    status: str = "draft"
    description: str | None = None


class TrainingSampleCreate(BaseModel):
    sample_type: str
    stock_code: str | None = None
    trade_date: date | None = None
    features_json: dict[str, Any]
    label_json: dict[str, Any]
    sample_weight: float = 1.0
    source_type: str | None = None
    source_id: int | None = None
    quality_score: float | None = None
    status: str = "candidate"
    can_train: bool = False


class TrainingSampleUpdate(BaseModel):
    sample_type: str | None = None
    features_json: dict[str, Any] | None = None
    label_json: dict[str, Any] | None = None
    sample_weight: float | None = None
    quality_score: float | None = None
    status: Literal["candidate", "approved", "rejected", "negative_sample", "invalid", "deprecated"] | None = None
    can_train: bool | None = None


class SampleReviewRequest(BaseModel):
    sample_ids: list[int]
    status: Literal["approved", "rejected", "negative_sample", "invalid", "deprecated"]
    can_train: bool = False
    reviewed_by: str | None = "human_reviewer"


class QuantModelCreate(BaseModel):
    model_name: str = "low_valuation_trend_model"
    version: str = "v1"
    model_type: str = "multi_factor_score"
    dataset_version_id: int | None = None
    feature_config_json: dict[str, Any] = Field(default_factory=dict)
    model_config_json: dict[str, Any] = Field(default_factory=dict)
    status: str = "experiment"


class DirtyDataMarkRequest(BaseModel):
    target_type: str
    target_id: int
    dirty_type: Literal["invalid", "negative_sample", "deprecated", "source_error", "data_leakage", "contamination"]
    description: str | None = None
    action: Literal["invalid", "negative_sample", "deprecated", "quarantine", "rebuild_required"] = "quarantine"
    created_by: str | None = "human_reviewer"


class WorkflowBootstrapRequest(BaseModel):
    stock_code: str = "600418"
    stock_name: str | None = None


class ResearchRunRequest(BaseModel):
    stock_code: str = "600418"
    stock_name: str | None = None
    strategy_idea_id: int | None = None
    idea: str = "以趋势、动量、成交量和回撤控制为核心，构建可解释的动态多因子策略。"
    initial_cash: float = 1_000_000
    min_score: float = 70
    max_position_per_stock: float = 0.2
    approve_sample: bool = True


class SimulationRunRequest(BaseModel):
    stock_code: str = "600418"
    strategy_version_id: int | None = None
    initial_cash: float = 1_000_000
    refresh_market: bool = True


class DataModelCreate(BaseModel):
    name: str = "A股日线因子数据模型"
    version: str = "v1"
    description: str | None = "同步真实行情，计算技术因子，生成可审计训练样本。"
    feature_version: str = "feature_v1"
    pipeline_config_json: dict[str, Any] = Field(default_factory=lambda: {
        "sync_daily": True,
        "compute_factors": True,
        "generate_dataset": True,
        "price_adjust": "qfq",
        "data_sources": ["eastmoney", "tencent", "sina"],
    })
    schedule_config_json: dict[str, Any] = Field(default_factory=lambda: {"mode": "manual_or_daily", "cron": "after_market_close"})
    status: str = "active"


class DataModelUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    feature_version: str | None = None
    pipeline_config_json: dict[str, Any] | None = None
    schedule_config_json: dict[str, Any] | None = None
    status: str | None = None


class DataModelRunRequest(BaseModel):
    stock_code: str = "600418"
    data_model_id: int | None = None
    start: str = "20240101"
    generate_dataset: bool = True


class DataModelBatchRunRequest(BaseModel):
    stock_code: str
    data_model_ids: list[int]
    start: str = "20240101"
    generate_dataset: bool = True


class AnalysisModelCreate(BaseModel):
    name: str = "趋势动量风控模型"
    version: str = "v1"
    model_family: str = "trend_momentum"
    description: str | None = "基于趋势、动量、成交量和波动率风险的可解释分析模型。"
    default_data_model_id: int | None = None
    parameters_json: dict[str, Any] = Field(default_factory=lambda: {"min_score": 68, "max_position_per_stock": 0.2})
    entry_rules_json: list[Any] = Field(default_factory=lambda: ["score >= min_score", "risk_level != high"])
    exit_rules_json: list[Any] = Field(default_factory=lambda: ["score < min_score - 8", "close < ma20"])
    risk_rules_json: dict[str, Any] = Field(default_factory=lambda: {"stop_loss": -0.08, "max_drawdown_limit": 0.15, "no_real_trading": True})
    capability_json: dict[str, Any] = Field(default_factory=lambda: {"supports": ["signal", "backtest", "simulation", "risk_review"]})
    status: str = "active"


class ControlRunRequest(BaseModel):
    stock_code: str = "600418"
    data_model_id: int
    analysis_model_id: int
    idea: str | None = None
    initial_cash: float = 1_000_000
    approve_sample: bool = True
    refresh_data: bool = True
