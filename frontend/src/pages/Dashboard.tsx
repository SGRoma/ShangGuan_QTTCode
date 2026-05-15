import { Bot, Database, Play, RefreshCw, ShieldCheck } from "lucide-react";
import type { ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";
import { apiGet, apiPost } from "../api/client";
import { LineChart as TrendChart } from "../charts/LineChart";
import type { AnyRecord, OperationState } from "../types/domain";

export function Dashboard() {
  const [stockCode, setStockCode] = useState("600418");
  const [dataModelId, setDataModelId] = useState("");
  const [analysisModelId, setAnalysisModelId] = useState("");
  const [idea, setIdea] = useState("使用所选数据模型构建数据底座，再用所选分析模型生成 600418 的信号、回测和模拟盘结果。");
  const [state, setState] = useState<OperationState | null>(null);
  const [monitor, setMonitor] = useState<AnyRecord | null>(null);
  const [result, setResult] = useState<AnyRecord | null>(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  async function refresh(code = stockCode) {
    const [operation, monitorPayload] = await Promise.all([
      apiGet<OperationState>("/workflows/operation-state"),
      apiGet<AnyRecord>(`/workflows/stock-monitor/${code}`)
    ]);
    setState(operation);
    setMonitor(monitorPayload);
    if (!dataModelId && operation.data_models?.[0]) setDataModelId(String(operation.data_models[0].id));
    if (!analysisModelId && operation.analysis_models?.[0]) setAnalysisModelId(String(operation.analysis_models[0].id));
  }

  async function runControl() {
    setBusy("run");
    setError("");
    try {
      const payload = await apiPost<AnyRecord>("/workflows/control-run", {
        stock_code: stockCode,
        data_model_id: Number(dataModelId),
        analysis_model_id: Number(analysisModelId),
        idea,
        refresh_data: true,
        approve_sample: true
      });
      setResult(payload);
      await refresh(stockCode);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "执行失败");
    } finally {
      setBusy("");
    }
  }

  useEffect(() => {
    refresh().catch((exc) => setError(exc instanceof Error ? exc.message : "加载失败"));
    const timer = window.setInterval(() => refresh(stockCode).catch(() => undefined), 15000);
    return () => window.clearInterval(timer);
  }, []);

  const stockOptions = useMemo(() => state?.stocks || [], [state]);
  const dataModels = state?.data_models || [];
  const analysisModels = state?.analysis_models || [];
  const selectedDataModel = dataModels.find((item) => String(item.id) === dataModelId);
  const selectedAnalysisModel = analysisModels.find((item) => String(item.id) === analysisModelId);
  const quote = monitor?.quote || result?.simulation?.quote || {};
  const latest = monitor?.latest_signal || {};
  const backtest = result?.backtest || state?.backtests?.[0] || {};
  const series = result?.simulation?.signals || backtest?.series || [];

  return (
    <section className="page console-page">
      <div className="page-heading console-heading">
        <div>
          <h1>总控台：股票 + 数据模型 + 分析模型</h1>
          <p>数据模型先构建地基，分析模型再生成信号、回测和模拟盘结果。智能体保持统一边界，只做生成、解释、复核和审计日志。</p>
        </div>
        <button className="secondary icon-button" onClick={() => refresh()} disabled={!!busy}><RefreshCw size={16} /> 刷新</button>
      </div>

      {error && <div className="error-banner">{error}</div>}

      <div className="operation-grid">
        <article className="panel command-panel">
          <span className="section-label">执行组合</span>
          <h2>选择执行对象</h2>
          <div className="form-grid">
            <label>
              <span>股票</span>
              <div className="inline-input">
                <input value={stockCode} onChange={(event) => setStockCode(event.target.value.replace(/\D/g, "").slice(0, 6))} />
                <select value={stockCode} onChange={(event) => setStockCode(event.target.value)}>
                  {stockOptions.map((stock) => <option key={stock.stock_code} value={stock.stock_code}>{stock.stock_code} {stock.stock_name}</option>)}
                </select>
              </div>
            </label>
            <label>
              <span>数据模型</span>
              <select value={dataModelId} onChange={(event) => setDataModelId(event.target.value)}>
                {dataModels.map((model) => <option key={model.id} value={model.id}>{model.name} · {model.version}</option>)}
              </select>
            </label>
            <label>
              <span>分析模型</span>
              <select value={analysisModelId} onChange={(event) => setAnalysisModelId(event.target.value)}>
                {analysisModels.map((model) => <option key={model.id} value={model.id}>{model.name} · {model.version}</option>)}
              </select>
            </label>
          </div>
          <label className="idea-box">
            <span>本次研究目标</span>
            <textarea value={idea} onChange={(event) => setIdea(event.target.value)} />
          </label>
          <button className="icon-button primary-action" onClick={runControl} disabled={busy === "run" || !dataModelId || !analysisModelId}>
            <Play size={17} /> {busy === "run" ? "执行中" : "执行并生成结果"}
          </button>
        </article>

        <article className="panel monitor-panel">
          <span className="section-label">当前行情</span>
          <h2>{stockCode} 实时监控</h2>
          <div className="quote-line">
            <strong className={Number(quote.change_pct) >= 0 ? "cn-up" : "cn-down"}>{num(quote.price)}</strong>
            <span className={Number(quote.change_pct) >= 0 ? "cn-up" : "cn-down"}>{num(quote.change)} / {num(quote.change_pct)}%</span>
          </div>
          <p className={`data-status ${quote.data_status !== "realtime" ? "warning" : ""}`}>实时源：{quote.source || "--"} · 历史源：{latest.data_source || "--"}</p>
          <div className="monitor-kpis">
            <SmallMetric label="AI 得分" value={num(latest.score)} />
            <SmallMetric label="风险" value={latest.risk_level || "--"} />
            <SmallMetric label="信号" value={monitor?.suggestion?.action || "--"} />
            <SmallMetric label="模型族" value={selectedAnalysisModel?.model_family || "--"} />
          </div>
        </article>
      </div>

      <div className="module-grid">
        <ModuleCard icon={<Database size={28} />} title="数据模型" label="数据地基" model={selectedDataModel} extra={`最近运行：${selectedDataModel?.last_run_at || "--"}`} />
        <ModuleCard icon={<ShieldCheck size={28} />} title="分析模型" label="策略与回测" model={selectedAnalysisModel} extra={`能力：${supportText(selectedAnalysisModel?.capability_json?.supports)}`} />
        <article className="panel module-card">
          <span className="section-label">智能体</span>
          <Bot size={28} />
          <h2>统一辅助层</h2>
          <p>智能体规则一致：不真实下单，不直接提升模型，只输出候选、解释、风控复核和日志。</p>
          <div className="fact-list">
            <span>日志：{state?.agent_logs?.length ?? 0}</span>
            <span>未处理脏数据：{state?.summary?.open_dirty ?? 0}</span>
          </div>
        </article>
      </div>

      <div className="metric-grid compact">
        <Metric label="累计收益" value={pct(backtest.total_return)} tone={Number(backtest.total_return) >= 0 ? "up" : "down"} />
        <Metric label="超额收益" value={pct(backtest.excess_return)} tone={Number(backtest.excess_return) >= 0 ? "up" : "down"} />
        <Metric label="最大回撤" value={pct(backtest.max_drawdown)} tone="down" />
        <Metric label="夏普" value={num(backtest.sharpe_ratio)} />
        <Metric label="交易次数" value={backtest.trade_count ?? "--"} />
        <Metric label="训练样本" value={result?.dataset?.approved_sample_count ?? state?.training_samples?.length ?? 0} />
      </div>

      <div className="two-column wide-left">
        <article className="panel"><h2>价格与趋势</h2><TrendChart rows={monitor?.series || []} mode="price" /></article>
        <article className="panel"><h2>分析模型净值</h2><TrendChart rows={series} mode="equity" /></article>
      </div>
    </section>
  );
}

function ModuleCard({ icon, title, label, model, extra }: { icon: ReactNode; title: string; label: string; model?: AnyRecord; extra: string }) {
  return (
    <article className="panel module-card">
      <span className="section-label">{label}</span>
      {icon}
      <h2>{title}</h2>
      <p>{model?.description || "等待选择模型。"}</p>
      <div className="fact-list">
        <span>{model ? `${model.name} · ${model.version}` : "--"}</span>
        <span>{extra}</span>
      </div>
    </article>
  );
}

function Metric({ label, value, tone }: { label: string; value: unknown; tone?: string }) {
  return <article className={`metric-card ${tone || ""}`}><span>{label}</span><strong>{String(value)}</strong></article>;
}

function SmallMetric({ label, value }: { label: string; value: unknown }) {
  return <div className="small-metric"><span>{label}</span><strong>{String(value)}</strong></div>;
}

function pct(value: unknown) { return `${(Number(value || 0) * 100).toFixed(2)}%`; }
function num(value: unknown) {
  const number = Number(value);
  return Number.isFinite(number) ? number.toFixed(2) : "--";
}

function supportText(value: unknown) {
  if (Array.isArray(value)) return value.join(" / ");
  if (typeof value === "string") return value;
  return "--";
}
