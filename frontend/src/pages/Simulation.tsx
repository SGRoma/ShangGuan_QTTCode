import { useEffect, useState } from "react";
import { apiGet, apiPost } from "../api/client";
import { LineChart } from "../charts/LineChart";
import type { AnyRecord, OperationState } from "../types/domain";

export function Simulation() {
  const [stockCode, setStockCode] = useState("600418");
  const [strategyId, setStrategyId] = useState("");
  const [state, setState] = useState<OperationState | null>(null);
  const [data, setData] = useState<AnyRecord | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function loadState() {
    const payload = await apiGet<OperationState>("/workflows/operation-state");
    setState(payload);
    if (!strategyId && payload.strategies[0]) setStrategyId(String(payload.strategies[0].id));
    if (!data && payload.backtests[0]) {
      setData(await apiPost<AnyRecord>("/workflows/simulate", { stock_code: stockCode, strategy_version_id: payload.strategies[0]?.id, refresh_market: false }));
    }
  }

  async function run(refresh_market = true) {
    setLoading(true);
    setError("");
    try {
      const payload = await apiPost<AnyRecord>("/workflows/simulate", {
        stock_code: stockCode,
        strategy_version_id: Number(strategyId),
        refresh_market
      });
      setData(payload);
      await loadState();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "模拟盘刷新失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadState().catch((exc) => setError(exc instanceof Error ? exc.message : "加载失败"));
    const timer = window.setInterval(() => run(false).catch(() => undefined), 15000);
    return () => window.clearInterval(timer);
  }, []);

  const quote = data?.quote || {};
  const signals = data?.signals || [];
  return (
    <section className="page">
      <div className="page-heading">
        <div>
          <h1>模拟盘监控</h1>
          <p>选择股票和策略版本后，系统按最新信号刷新虚拟账户、持仓、成交与风控提示；不会连接券商或真实资金。</p>
        </div>
        <div className="toolbar">
          <input value={stockCode} onChange={(event) => setStockCode(event.target.value.replace(/\D/g, "").slice(0, 6))} />
          <select value={strategyId} onChange={(event) => setStrategyId(event.target.value)}>
            {(state?.strategies || []).map((strategy) => <option key={strategy.id} value={strategy.id}>{strategy.label}</option>)}
          </select>
          <button onClick={() => run(true)} disabled={loading || !strategyId}>{loading ? "刷新中" : "运行模拟盘"}</button>
        </div>
      </div>
      {error && <div className="error-banner">{error}</div>}
      <div className="metric-grid compact">
        <Metric label="总资产" value={money(data?.account?.total_value)} />
        <Metric label="现金" value={money(data?.account?.cash)} />
        <Metric label="持仓数" value={data?.positions?.length || 0} />
        <Metric label="最新价" value={num(quote.price)} tone={Number(quote.change_pct) >= 0 ? "up" : "down"} />
        <Metric label="涨跌幅" value={`${num(quote.change_pct)}%`} tone={Number(quote.change_pct) >= 0 ? "up" : "down"} />
        <Metric label="状态" value={data?.status || "watching"} />
      </div>
      <div className="two-column">
        <article className="panel"><h2>模拟净值</h2><LineChart rows={signals} mode="equity" /></article>
        <article className="panel">
          <h2>风控告警</h2>
          <div className="guardrail-list">{(data?.risk_alerts || []).map((item: string) => <span key={item}>{item}</span>)}</div>
          <p className="decision-text">{data?.agent_review}</p>
        </article>
      </div>
      <article className="panel">
        <h2>虚拟成交</h2>
        <div className="table-wrap">
          <table>
            <thead><tr><th>日期</th><th>方向</th><th>价格</th><th>仓位</th><th>说明</th></tr></thead>
            <tbody>{(data?.trades || []).map((row: AnyRecord, index: number) => <tr key={index}><td>{row.trade_date}</td><td className={row.side === "buy" ? "cn-up" : "cn-down"}>{row.side}</td><td>{row.price}</td><td>{row.quantity_ratio}</td><td>{row.reason}</td></tr>)}</tbody>
          </table>
        </div>
      </article>
    </section>
  );
}

function Metric({ label, value, tone }: { label: string; value: unknown; tone?: string }) {
  return <article className={`metric-card ${tone || ""}`}><span>{label}</span><strong>{String(value)}</strong></article>;
}

function money(value: unknown) {
  return Number(value || 0).toLocaleString("zh-CN", { maximumFractionDigits: 2 });
}

function num(value: unknown) {
  const number = Number(value);
  return Number.isFinite(number) ? number.toFixed(2) : "--";
}
