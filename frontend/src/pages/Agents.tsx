import { Activity, Bot, Brain, Bug, Clock, Play, RefreshCw, Settings } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { apiGet, apiPatch, apiPost } from "../api/client";
import type { AnyRecord } from "../types/domain";

export function Agents() {
  const [monitor, setMonitor] = useState<AnyRecord | null>(null);
  const [selectedKey, setSelectedKey] = useState("generate-strategy");
  const [input, setInput] = useState("基于当前股票数据，给出下一轮策略或模型迭代建议。");
  const [output, setOutput] = useState<AnyRecord | null>(null);
  const [showDebug, setShowDebug] = useState(false);
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
      const payload = await apiPost<AnyRecord>(`/agents/${selectedKey}`, { user_input: input, context: { source: "agent_debug" } });
      setOutput(payload);
      await load();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "智能体运行失败");
    } finally {
      setBusy("");
    }
  }

  async function updateConfig(body: AnyRecord) {
    if (!selectedKey) return;
    setBusy("config");
    setError("");
    try {
      await apiPatch(`/agents/${selectedKey}/config`, body);
      await load();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "配置更新失败");
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
    <section className="page agent-page">
      <div className="page-heading">
        <div>
          <h1>智能体监测台</h1>
          <p>监测智能体运行、学习样本、调用来源和最近输出。智能体默认由闭环事件触发，手动运行仅作为调试工具。</p>
        </div>
        <button className="secondary icon-button" onClick={() => load()} disabled={!!busy}><RefreshCw size={16} /> 刷新</button>
      </div>
      {error && <div className="error-banner">{error}</div>}

      <div className="metric-grid compact agent-metrics">
        <Metric label="智能体数量" value={agents.length} />
        <Metric label="已审核训练样本" value={learning.approved_samples ?? 0} />
        <Metric label="数据集版本" value={learning.dataset_count ?? 0} />
        <Metric label="模型记录" value={learning.model_count ?? 0} />
        <Metric label="最近日志" value={logs.length} />
        <Metric label="自动化模式" value={monitor?.automation?.mode_label || "--"} compact />
      </div>

      <div className="agent-layout">
        <article className="panel agent-select-panel">
          <h2>智能体列表</h2>
          <div className="agent-list fixed-list">
            {agents.map((agent: AnyRecord) => (
              <button className={`agent-row ${agent.key === selectedKey ? "active" : ""}`} key={agent.key} onClick={() => setSelectedKey(agent.key)}>
                <Bot size={18} />
                <span><strong>{agent.label}</strong><small>{agent.agent_name}</small></span>
                <em>{agent.enabled ? agent.status : "disabled"}</em>
              </button>
            ))}
          </div>
        </article>

        <article className="panel agent-detail">
          <span className="section-label">监测详情</span>
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

        <article className="panel agent-manage-panel">
          <h2><Settings size={16} /> 智能体管理</h2>
          <div className="config-grid">
            <label className="toggle-row">
              <input type="checkbox" checked={!!selected?.enabled} onChange={(event) => updateConfig({ enabled: event.target.checked })} />
              <span>启用智能体</span>
            </label>
            <label className="toggle-row">
              <input type="checkbox" checked={!!selected?.auto_run} onChange={(event) => updateConfig({ auto_run: event.target.checked })} />
              <span>允许自动运行</span>
            </label>
            <label>
              <span>触发方式</span>
              <select value={selected?.schedule || "manual"} onChange={(event) => updateConfig({ schedule: event.target.value })}>
                <option value="event:research_run">研究闭环事件</option>
                <option value="event:backtest_completed">回测完成事件</option>
                <option value="event:strategy_version_created">策略版本事件</option>
                <option value="after_market_close">收盘后</option>
                <option value="after_sample_review">样本审核后</option>
                <option value="manual_or_refresh">手动或刷新</option>
                <option value="manual">仅手动</option>
              </select>
            </label>
            <label>
              <span>超时秒数</span>
              <input type="number" min={3} max={60} value={selected?.timeout_seconds || 8} onChange={(event) => updateConfig({ timeout_seconds: Number(event.target.value) })} />
            </label>
          </div>
          <p className="data-status">管理配置会写入配置版本记录；当前尚未接入独立调度器，自动运行由闭环事件触发。</p>
        </article>
      </div>

      <div className="two-column agent-output-grid">
        <article className="panel fixed-output-panel">
          <h2>最近输出</h2>
          <pre className="fixed-pre">{JSON.stringify(output || selected?.last_output || {}, null, 2)}</pre>
        </article>
        <article className="panel">
          <h2>运行日志</h2>
          <div className="log-list fixed-log-list">
            {logs.slice(0, 12).map((log: AnyRecord) => (
              <span key={log.id}><Clock size={14} /> {formatTime(log.created_at)} · {log.agent_name} · {log.status}</span>
            ))}
          </div>
        </article>
      </div>

      <article className="panel">
        <h2>学习进度</h2>
        <div className="learning-box">
          <Brain size={24} />
          <p>{learning.progress_text || "--"}</p>
        </div>
      </article>

      <article className="panel">
        <button className="secondary icon-button" onClick={() => setShowDebug(!showDebug)}><Bug size={16} /> {showDebug ? "收起调试工具" : "打开调试工具"}</button>
        {showDebug && (
          <div className="debug-box">
            <label>
              <span>调试输入</span>
              <textarea value={input} onChange={(event) => setInput(event.target.value)} />
            </label>
            <button className="icon-button" onClick={runSelected} disabled={busy === "run" || !selectedKey}><Play size={16} /> {busy === "run" ? "运行中" : "手动运行所选智能体"}</button>
            <p className="data-status">严格来说，手动触发不属于生产流程；它保留用于调试、验收和人工复核。</p>
          </div>
        )}
      </article>

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

function Metric({ label, value, compact }: { label: string; value: unknown; compact?: boolean }) {
  return <article className={`metric-card ${compact ? "metric-card-compact-text" : ""}`}><span>{label}</span><strong>{String(value)}</strong></article>;
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
