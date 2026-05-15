import { useEffect, useState } from "react";
import { apiGet, apiPost } from "../api/client";
import type { AnyRecord } from "../types/domain";

const agentOptions = [
  ["generate-strategy", "策略生成智能体"],
  ["explain-backtest", "回测解释智能体"],
  ["risk-review", "风险复核智能体"],
  ["data-quality-review", "数据质量智能体"],
  ["model-iteration-review", "模型迭代智能体"],
  ["stock-research", "股票研究智能体"],
  ["technical-analysis", "技术分析智能体"]
];

export function Agents() {
  const [agent, setAgent] = useState("generate-strategy");
  const [input, setInput] = useState("寻找低估值、趋势向上、成交量放大的股票策略");
  const [output, setOutput] = useState<AnyRecord | null>(null);
  const [logs, setLogs] = useState<AnyRecord[]>([]);

  async function run() {
    const payload = await apiPost<AnyRecord>(`/agents/${agent}`, { user_input: input, context: {} });
    setOutput(payload);
    loadLogs();
  }
  async function loadLogs() {
    const payload = await apiGet<{ rows: AnyRecord[] }>("/agents/logs");
    setLogs(payload.rows);
  }
  useEffect(() => { loadLogs(); }, []);

  return (
    <section className="page">
      <div className="page-heading">
        <div><h1>智能体工作台</h1><p>智能体只能生成候选内容和解释报告，所有输出都会写入 agent_run_log。</p></div>
      </div>
      <div className="workbench">
        <article className="panel">
          <h2>运行智能体</h2>
          <select value={agent} onChange={(e) => setAgent(e.target.value)}>{agentOptions.map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select>
          <textarea value={input} onChange={(e) => setInput(e.target.value)} />
          <button onClick={run}>生成结构化输出</button>
        </article>
        <article className="panel">
          <h2>输出 JSON</h2>
          <pre>{JSON.stringify(output, null, 2)}</pre>
        </article>
      </div>
      <article className="panel">
        <h2>最近日志</h2>
        <div className="log-list">{logs.slice(0, 8).map((log) => <span key={log.id}>{log.created_at} · {log.agent_name} · {log.status}</span>)}</div>
      </article>
    </section>
  );
}

