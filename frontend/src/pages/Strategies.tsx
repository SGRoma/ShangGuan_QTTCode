import { useEffect, useState } from "react";
import { apiGet, apiPost } from "../api/client";
import type { AnyRecord, OperationState, WorkflowPayload } from "../types/domain";

export function Strategies() {
  const [state, setState] = useState<OperationState | null>(null);
  const [stockCode, setStockCode] = useState("600418");
  const [idea, setIdea] = useState("基于趋势、动量、成交量和风险惩罚，让智能体生成一个可回测、可迭代、不能实盘下单的候选策略。");
  const [result, setResult] = useState<WorkflowPayload | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function load() {
    setState(await apiGet<OperationState>("/workflows/operation-state"));
  }

  async function generate() {
    setLoading(true);
    setError("");
    try {
      const payload = await apiPost<WorkflowPayload>("/workflows/research-run", {
        stock_code: stockCode,
        idea,
        min_score: 68,
        approve_sample: true
      });
      setResult(payload);
      setState(payload.operation_state);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "策略生成失败");
    } finally {
      setLoading(false);
    }
  }

  async function review(id: number, status: string) {
    await apiPost(`/strategies/ideas/${id}/review`, { status, can_train: status === "approved", can_trade: false, risk_level: "medium" });
    await load();
  }

  useEffect(() => { load().catch(() => undefined); }, []);

  return (
    <section className="page">
      <div className="page-heading">
        <div>
          <h1>策略实验</h1>
          <p>自然语言想法会先进入候选策略和版本库，同时触发回测、样本沉淀和模型记录；不会直接进入真实交易。</p>
        </div>
      </div>
      {error && <div className="error-banner">{error}</div>}
      <div className="workbench">
        <article className="panel command-panel">
          <h2>智能体生成策略</h2>
          <label><span>股票代码</span><input value={stockCode} onChange={(event) => setStockCode(event.target.value.replace(/\D/g, "").slice(0, 6))} /></label>
          <label><span>策略想法</span><textarea value={idea} onChange={(event) => setIdea(event.target.value)} /></label>
          <button onClick={generate} disabled={loading}>{loading ? "生成并回测中" : "生成策略并运行闭环"}</button>
          {result && <pre>{JSON.stringify(result.strategy_version, null, 2)}</pre>}
        </article>
        <article className="panel">
          <h2>策略版本</h2>
          <div className="card-list">
            {(state?.strategies || []).map((strategy) => (
              <div className="review-card" key={strategy.id}>
                <strong>{strategy.label}</strong>
                <span>{strategy.status} · min_score={strategy.parameters_json?.min_score ?? "--"}</span>
                <p>{strategy.change_reason}</p>
              </div>
            ))}
          </div>
        </article>
      </div>
      <article className="panel">
        <h2>候选想法审核</h2>
        <div className="table-wrap">
          <table>
            <thead><tr><th>ID</th><th>标题</th><th>状态</th><th>可训练</th><th>操作</th></tr></thead>
            <tbody>{(state?.agent_logs || []).map((log: AnyRecord) => <tr key={log.id}><td>{log.id}</td><td>{log.agent_name}</td><td>{log.status}</td><td>{log.related_entity_type || "--"}</td><td>{log.created_at}</td></tr>)}</tbody>
          </table>
        </div>
        <div className="card-list">
          {(state?.strategies || []).slice(0, 3).map((strategy) => strategy.strategy_idea_id ? (
            <div className="review-card" key={`idea-${strategy.strategy_idea_id}`}>
              <strong>策略想法 #{strategy.strategy_idea_id}</strong>
              <span>审核动作只影响训练资格，不开放实盘下单</span>
              <div>
                <button onClick={() => review(strategy.strategy_idea_id, "approved")}>批准训练</button>
                <button className="secondary" onClick={() => review(strategy.strategy_idea_id, "negative_sample")}>设为负样本</button>
                <button className="danger" onClick={() => review(strategy.strategy_idea_id, "rejected")}>拒绝</button>
              </div>
            </div>
          ) : null)}
        </div>
      </article>
    </section>
  );
}
