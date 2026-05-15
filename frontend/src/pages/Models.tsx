import { useEffect, useState } from "react";
import { apiGet, apiPost } from "../api/client";
import type { AnyRecord, OperationState } from "../types/domain";

export function Models() {
  const [state, setState] = useState<OperationState | null>(null);
  const [name, setName] = useState("突破回撤控制模型");
  const [family, setFamily] = useState("breakout_risk");
  const [minScore, setMinScore] = useState(72);
  const [position, setPosition] = useState(0.15);
  const [error, setError] = useState("");

  async function load() {
    setState(await apiGet<OperationState>("/workflows/operation-state"));
  }

  async function createAnalysisModel() {
    setError("");
    try {
      await apiPost("/analysis-models", {
        name,
        version: `v${(state?.analysis_models?.length || 0) + 1}`,
        model_family: family,
        description: "用户新增的可选择分析模型，可在总控台绑定股票和数据模型执行。",
        default_data_model_id: state?.data_models?.[0]?.id,
        parameters_json: { min_score: minScore, max_position_per_stock: position },
        entry_rules_json: ["score >= min_score", "risk_level != high"],
        exit_rules_json: ["score < min_score - 8", "close < ma20"],
        risk_rules_json: { stop_loss: -0.08, max_drawdown_limit: 0.15, no_real_trading: true },
        capability_json: { supports: ["signal", "backtest", "simulation", "risk_review"], user_defined: true },
        status: "active"
      });
      await load();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "创建失败");
    }
  }

  useEffect(() => { load().catch((exc) => setError(exc instanceof Error ? exc.message : "加载失败")); }, []);

  return (
    <section className="page">
      <div className="page-heading">
        <div>
          <h1>分析模型管理</h1>
          <p>分析模型是可插拔的策略/评分/风控/回测组件。总控台选择股票、数据模型和分析模型后执行。</p>
        </div>
      </div>
      {error && <div className="error-banner">{error}</div>}
      <div className="workbench">
        <article className="panel command-panel">
          <h2>新增分析模型</h2>
          <label><span>模型名称</span><input value={name} onChange={(event) => setName(event.target.value)} /></label>
          <label><span>模型族</span><input value={family} onChange={(event) => setFamily(event.target.value)} /></label>
          <div className="form-grid">
            <label><span>入场分数</span><input type="number" value={minScore} onChange={(event) => setMinScore(Number(event.target.value))} /></label>
            <label><span>最大仓位</span><input type="number" step={0.01} value={position} onChange={(event) => setPosition(Number(event.target.value))} /></label>
          </div>
          <button onClick={createAnalysisModel}>创建分析模型</button>
        </article>
        <article className="panel">
          <h2>可选分析模型</h2>
          <div className="card-list">
            {(state?.analysis_models || []).map((model: AnyRecord) => (
              <div className="review-card" key={model.id}>
                <strong>#{model.id} {model.name} · {model.version}</strong>
                <span>{model.model_family} · {model.status}</span>
                <p>{model.description}</p>
                <pre>{JSON.stringify({ parameters: model.parameters_json, risk: model.risk_rules_json, capability: model.capability_json }, null, 2)}</pre>
              </div>
            ))}
          </div>
        </article>
      </div>
      <article className="panel">
        <h2>训练记录</h2>
        <div className="card-grid">
          {(state?.models || []).map((model: AnyRecord) => (
            <article className="review-card" key={model.id}>
              <strong>{model.model_name} {model.version}</strong>
              <span>{model.model_type} · {model.status} · dataset #{model.dataset_version_id || "--"}</span>
              <pre>{JSON.stringify({ training: model.training_metrics_json, validation: model.validation_metrics_json, backtest: model.backtest_metrics_json }, null, 2)}</pre>
            </article>
          ))}
        </div>
      </article>
    </section>
  );
}
