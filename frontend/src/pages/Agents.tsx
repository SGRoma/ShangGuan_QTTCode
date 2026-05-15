import { Activity, Bot, Brain, Clock, Play, RefreshCw } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { apiGet, apiPost } from "../api/client";
import type { AnyRecord } from "../types/domain";

export function Agents() {
  const [monitor, setMonitor] = useState<AnyRecord | null>(null);
  const [selectedKey, setSelectedKey] = useState("generate-strategy");
  const [input, setInput] = useState("基于当前股票数据，给出下一轮策略或模型迭代建议。");
  const [output, setOutput] = useState<AnyRecord | null>(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  async function load() {
    const payload = await apiGet<AnyRecord>("/agents/monitor");
    setMonitor(payload);
    if (!payload.agents?.some((agent: AnyRecord) => agent.key === selectedKey)) {
      setSelectedKey(payload.agents?.[0]?.key || "generate-strategy");
    }
  }

  async function runSelected() {
    setBusy("run");
    setError("");
    try {
      const payload = await apiPost<AnyRecord>(`/agents/${selectedKey}`, { user_input: input, context: { source: "agent_monitor" } });
      setOutput(payload);
      await load();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "智能体运行失败");
    } finally {
      setBusy("");
    }
  }

  useEffect(() => {
    load().catch((exc) => setError(exc instanceof Error ? exc.message : "加载失败"));
    const timer = window.setInterval(() => load().catch(() => undefined), 15000);
    return () => window.clearInterval(timer);
  }, []);

  const agents = monitor?.agents || [];
  const selected = useMemo(() => agents.find((agent: AnyRecord) => agent.key === selectedKey) || agents[0], [agents, selectedKey]);
  const logs = monitor?.logs || [];
  const learning = monitor?.learning || {};

  return (
    <section className="page">
      <div className="page-heading">
        <div>
          <h1>智能体监测台</h1>
          <p>这里监测智能体的运行、学习样本、调用来源和最近输出。当前为事件驱动 MVP：闭环运行时自动触发，独立定时调度器尚未接入。</p>
        </div>
        <button className="secondary icon-button" onClick={() => load()} disabled={!!busy}><RefreshCw size={16} /> 刷新</button>
      </div>
      {error && <div className="error-banner">{error}</div>}

      <div className="metric-grid compact">
        <Metric label="智能体数量" value={agents.length} />
        <Metric label="已审核训练样本" value={learning.approved_samples ?? 0} />
        <Metric label="数据集版本" value={learning.dataset_count ?? 0} />
        <Metric label="模型记录" value={learning.model_count ?? 0} />
        <Metric label="最近日志" value={logs.length} />
        <Metric label="自动化模式" value={monitor?.automation?.mode || "--"} />
      </div>

      <div className="workbench">
        <article className="panel">
          <h2>智能体选择</h2>
          <div className="agent-list">
            {agents.map((agent: AnyRecord) => (
              <button className={`agent-row ${agent.key === selectedKey ? "active" : ""}`} key={agent.key} onClick={() => setSelectedKey(agent.key)}>
                <Bot size={18} />
                <span><strong>{agent.label}</strong><small>{agent.agent_name}</small></span>
                <em>{agent.status}</em>
              </button>
            ))}
          </div>
        </article>

        <article className="panel agent-detail">
          <span className="section-label">智能体详情</span>
          <h2>{selected?.label || "--"}</h2>
          <p>{selected?.role || "暂无说明。"}</p>
          <div className="monitor-kpis">
            <SmallMetric label="运行次数" value={selected?.run_count ?? 0} />
            <SmallMetric label="24小时内" value={selected?.recent_24h ?? 0} />
            <SmallMetric label="成功率" value={pct(selected?.success_rate, 100)} />
            <SmallMetric label="平台调用" value={selected?.provider_calls ?? 0} />
          </div>
          <div className="fact-list">
            <span>自动运行：{selected?.auto_task || "--"}</span>
            <span>最近运行：{formatTime(selected?.last_run_at)}</span>
            <span>Fallback 次数：{selected?.fallback_calls ?? 0}</span>
          </div>
        </article>
      </div>

      <div className="workbench">
        <article className="panel command-panel">
          <h2>手动触发</h2>
          <label>
            <span>输入</span>
            <textarea value={input} onChange={(event) => setInput(event.target.value)} />
          </label>
          <button className="icon-button" onClick={runSelected} disabled={busy === "run" || !selectedKey}><Play size={16} /> {busy === "run" ? "运行中" : "运行所选智能体"}</button>
          <p className="data-status">手动触发用于调试和复核；生产化自动运行应交给后台调度器。</p>
        </article>
        <article className="panel">
          <h2>最近输出</h2>
          <pre>{JSON.stringify(output || selected?.last_output || {}, null, 2)}</pre>
        </article>
      </div>

      <div className="two-column">
        <article className="panel">
          <h2>学习进度</h2>
          <div className="learning-box">
            <Brain size={24} />
            <p>{learning.progress_text || "--"}</p>
          </div>
          <pre>{JSON.stringify({ latest_dataset: learning.latest_dataset, latest_model: learning.latest_model }, null, 2)}</pre>
        </article>
        <article className="panel">
          <h2>运行日志</h2>
          <div className="log-list">
            {logs.slice(0, 12).map((log: AnyRecord) => (
              <span key={log.id}><Clock size={14} /> {formatTime(log.created_at)} · {log.agent_name} · {log.status}</span>
            ))}
          </div>
        </article>
      </div>

      <article className="panel">
        <h2>自动化判断</h2>
        <div className="guardrail-list">
          <span><Activity size={14} /> {monitor?.automation?.description}</span>
          <span>{monitor?.automation?.recommended_next}</span>
        </div>
      </article>
    </section>
  );
}

function Metric({ label, value, tone }: { label: string; value: unknown; tone?: string }) {
  return <article className={`metric-card ${tone || ""}`}><span>{label}</span><strong>{String(value)}</strong></article>;
}

function SmallMetric({ label, value }: { label: string; value: unknown }) {
  return <div className="small-metric"><span>{label}</span><strong>{String(value)}</strong></div>;
}

function pct(value: unknown, scale = 1) {
  return `${(Number(value || 0) * scale).toFixed(1)}%`;
}

function formatTime(value: unknown) {
  if (!value) return "--";
  return String(value).replace("T", " ").replace("+08:00", "");
}
