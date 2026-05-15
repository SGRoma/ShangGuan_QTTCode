import { Bot, Edit3, FlaskConical, GitBranch, Play } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { apiGet, apiPatch, apiPost } from "../api/client";
import type { AnyRecord, OperationState, WorkflowPayload } from "../types/domain";

export function Strategies() {
  const [state, setState] = useState<OperationState | null>(null);
  const [ideas, setIdeas] = useState<AnyRecord[]>([]);
  const [selectedIdeaId, setSelectedIdeaId] = useState<number | null>(null);
  const [stockCode, setStockCode] = useState("600418");
  const [title, setTitle] = useState("600418 趋势动量候选策略");
  const [idea, setIdea] = useState("基于趋势、动量、成交量和风险惩罚，生成一个只用于回测和模拟盘观察的候选策略。");
  const [result, setResult] = useState<WorkflowPayload | null>(null);
  const [loading, setLoading] = useState("");
  const [error, setError] = useState("");

  async function load() {
    const [operation, ideaPayload] = await Promise.all([
      apiGet<OperationState>("/workflows/operation-state"),
      apiGet<{ rows: AnyRecord[] }>("/strategies/ideas")
    ]);
    setState(operation);
    setIdeas(ideaPayload.rows);
    if (!selectedIdeaId && ideaPayload.rows[0]) setSelectedIdeaId(ideaPayload.rows[0].id);
  }

  async function saveIdea() {
    setLoading("save");
    setError("");
    try {
      if (selectedIdeaId) {
        await apiPatch(`/strategies/ideas/${selectedIdeaId}`, { title, content: idea, status: "candidate" });
      } else {
        const created = await apiPost<AnyRecord>("/strategies/ideas", { title, content: idea, source: "user_input", created_by: "user" });
        setSelectedIdeaId(created.id);
      }
      await load();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "保存候选想法失败");
    } finally {
      setLoading("");
    }
  }

  async function generate() {
    setLoading("generate");
    setError("");
    try {
      let ideaId = selectedIdeaId;
      if (!ideaId) {
        const created = await apiPost<AnyRecord>("/strategies/ideas", { title, content: idea, source: "user_input", created_by: "user" });
        ideaId = created.id;
        setSelectedIdeaId(created.id);
      }
      const payload = await apiPost<WorkflowPayload>("/workflows/research-run", {
        stock_code: stockCode,
        strategy_idea_id: ideaId,
        idea,
        min_score: 68,
        approve_sample: false
      });
      setResult(payload);
      await load();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "策略实验失败");
    } finally {
      setLoading("");
    }
  }

  async function review(id: number, status: string) {
    setError("");
    try {
      await apiPost(`/strategies/ideas/${id}/review`, {
        status,
        can_train: status === "approved",
        can_trade: false,
        risk_level: "medium",
        remark: status === "approved" ? "人工批准进入训练样本候选范围" : "人工复核后不作为正样本"
      });
      await load();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "审核失败");
    }
  }

  useEffect(() => { load().catch((exc) => setError(exc instanceof Error ? exc.message : "加载失败")); }, []);

  const selectedIdea = useMemo(() => ideas.find((item) => item.id === selectedIdeaId), [ideas, selectedIdeaId]);

  function selectIdea(row: AnyRecord) {
    setSelectedIdeaId(row.id);
    setTitle(row.title || "");
    setIdea(row.content || "");
  }

  const strategies = state?.strategies || [];

  return (
    <section className="page">
      <div className="page-heading">
        <div>
          <h1>策略实验室</h1>
          <p>策略生成属于智能体框架下的实验入口。策略版本不是最终策略，它是一次可复现的实验快照，用于回测、模拟盘、样本沉淀和后续模型对比。</p>
        </div>
      </div>
      {error && <div className="error-banner">{error}</div>}

      <div className="workbench">
        <article className="panel command-panel">
          <span className="section-label">候选想法</span>
          <h2>编辑候选策略想法</h2>
          <label><span>股票代码</span><input value={stockCode} onChange={(event) => setStockCode(event.target.value.replace(/\D/g, "").slice(0, 6))} /></label>
          <label><span>标题</span><input value={title} onChange={(event) => setTitle(event.target.value)} /></label>
          <label><span>策略想法</span><textarea value={idea} onChange={(event) => setIdea(event.target.value)} /></label>
          <div className="button-row">
            <button className="secondary icon-button" onClick={() => { setSelectedIdeaId(null); setTitle(""); setIdea(""); }}><Edit3 size={16} /> 新建</button>
            <button className="icon-button" onClick={saveIdea} disabled={loading === "save"}><FlaskConical size={16} /> {loading === "save" ? "保存中" : "保存想法"}</button>
            <button className="icon-button" onClick={generate} disabled={loading === "generate" || !idea.trim()}><Play size={16} /> {loading === "generate" ? "运行中" : "智能体生成并回测"}</button>
          </div>
          {selectedIdea && <p className="data-status">当前想法 #{selectedIdea.id}：{selectedIdea.status} · 可训练={String(selectedIdea.can_train)}</p>}
        </article>

        <article className="panel">
          <h2>候选想法列表</h2>
          <div className="card-list">
            {ideas.map((row) => (
              <button className={`list-button ${row.id === selectedIdeaId ? "active" : ""}`} key={row.id} onClick={() => selectIdea(row)}>
                <strong>#{row.id} {row.title}</strong>
                <span>{row.status} · review={row.review_status} · can_train={String(row.can_train)} · {formatTime(row.updated_at)}</span>
                <p>{row.content}</p>
              </button>
            ))}
          </div>
        </article>
      </div>

      <article className="panel">
        <h2>候选想法审核</h2>
        <div className="table-wrap">
          <table>
            <thead><tr><th>ID</th><th>标题</th><th>状态</th><th>可训练</th><th>更新时间</th><th>操作</th></tr></thead>
            <tbody>
              {ideas.map((row) => (
                <tr key={row.id}>
                  <td>{row.id}</td>
                  <td>{row.title}</td>
                  <td>{row.status}</td>
                  <td>{String(row.can_train)}</td>
                  <td>{formatTime(row.updated_at)}</td>
                  <td>
                    <div className="row-actions">
                      <button onClick={() => review(row.id, "approved")}>批准</button>
                      <button className="secondary" onClick={() => review(row.id, "negative_sample")}>负样本</button>
                      <button className="danger" onClick={() => review(row.id, "rejected")}>拒绝</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </article>

      <div className="workbench">
        <article className="panel">
          <h2><GitBranch size={16} /> 策略版本</h2>
          <p>每个版本保存参数、入场/退出规则、风险规则和来源。它的价值是让回测结果能追溯，不是把规则永久写死。</p>
          <div className="card-list">
            {strategies.map((strategy) => (
              <div className="review-card" key={strategy.id}>
                <strong>{strategy.label}</strong>
                <span>{strategy.status} · idea #{strategy.strategy_idea_id || "--"} · min_score={strategy.parameters_json?.min_score ?? "--"}</span>
                <p>{strategy.change_reason}</p>
              </div>
            ))}
          </div>
        </article>
        <article className="panel">
          <h2><Bot size={16} /> 本次实验输出</h2>
          <pre>{JSON.stringify(result?.strategy_version || result?.agent_review || {}, null, 2)}</pre>
        </article>
      </div>
    </section>
  );
}

function formatTime(value: unknown) {
  if (!value) return "--";
  return String(value).replace("T", " ").replace("+08:00", "");
}
