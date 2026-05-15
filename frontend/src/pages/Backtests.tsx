import { useEffect, useState } from "react";
import { apiGet, apiPost } from "../api/client";
import { LineChart } from "../charts/LineChart";
import type { AnyRecord, OperationState } from "../types/domain";

export function Backtests() {
  const [state, setState] = useState<OperationState | null>(null);
  const [versionId, setVersionId] = useState("");
  const [stockCode, setStockCode] = useState("600418");
  const [result, setResult] = useState<AnyRecord | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function load() {
    const payload = await apiGet<OperationState>("/workflows/operation-state");
    setState(payload);
    if (!versionId && payload.strategies[0]) setVersionId(String(payload.strategies[0].id));
    if (!result && payload.backtests[0]) setResult(payload.backtests[0]);
  }

  async function run() {
    setLoading(true);
    setError("");
    try {
      const payload = await apiPost<AnyRecord>("/backtests/run", {
        strategy_version_id: Number(versionId),
        stock_code: stockCode,
        initial_cash: 1000000,
        fee_rate: 0.0003,
        slippage_rate: 0.001,
        max_position_per_stock: 0.2
      });
      setResult(payload);
      await load();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "回测失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load().catch((exc) => setError(exc instanceof Error ? exc.message : "加载失败"));
  }, []);

  const metrics = result?.result_json?.metrics || result || {};
  const rows = result?.result_json?.series || result?.series || [];
  return (
    <section className="page">
      <div className="page-heading">
        <div>
          <h1>回测操作</h1>
          <p>选择已有策略版本和股票代码即可运行回测。信号按 T 日生成、T+1 执行，不使用未来价格直接交易。</p>
        </div>
        <div className="toolbar">
          <select value={versionId} onChange={(event) => setVersionId(event.target.value)}>
            {(state?.strategies || []).map((strategy) => <option key={strategy.id} value={strategy.id}>{strategy.label}</option>)}
          </select>
          <input value={stockCode} onChange={(event) => setStockCode(event.target.value.replace(/\D/g, "").slice(0, 6))} />
          <button onClick={run} disabled={loading || !versionId}>{loading ? "运行中" : "执行回测"}</button>
        </div>
      </div>
      {error && <div className="error-banner">{error}</div>}
      <div className="metric-grid compact">
        <Metric label="累计收益" value={pct(metrics.total_return)} tone={Number(metrics.total_return) >= 0 ? "up" : "down"} />
        <Metric label="年化收益" value={pct(metrics.annual_return)} tone={Number(metrics.annual_return) >= 0 ? "up" : "down"} />
        <Metric label="最大回撤" value={pct(metrics.max_drawdown)} tone="down" />
        <Metric label="夏普" value={num(metrics.sharpe_ratio)} />
        <Metric label="胜率" value={pct(metrics.win_rate)} />
        <Metric label="交易次数" value={metrics.trade_count ?? "--"} />
      </div>
      <div className="two-column">
        <article className="panel"><h2>收益曲线</h2><LineChart rows={rows} mode="equity" /></article>
        <article className="panel"><h2>回撤曲线</h2><LineChart rows={rows} mode="drawdown" /></article>
      </div>
      <article className="panel">
        <h2>交易明细</h2>
        <div className="table-wrap">
          <table>
            <thead><tr><th>日期</th><th>方向</th><th>价格</th><th>仓位</th><th>原因</th></tr></thead>
            <tbody>{(result?.result_json?.trades || result?.trades || []).map((row: AnyRecord, index: number) => <tr key={index}><td>{row.trade_date}</td><td className={row.side === "buy" ? "cn-up" : "cn-down"}>{row.side}</td><td>{row.price}</td><td>{row.quantity_ratio}</td><td>{row.reason}</td></tr>)}</tbody>
          </table>
        </div>
      </article>
    </section>
  );
}

function Metric({ label, value, tone }: { label: string; value: unknown; tone?: string }) {
  return <article className={`metric-card ${tone || ""}`}><span>{label}</span><strong>{String(value)}</strong></article>;
}
function pct(v: unknown) { return `${(Number(v || 0) * 100).toFixed(2)}%`; }
function num(v: unknown) { return Number(v || 0).toFixed(2); }
