import { useEffect, useState } from "react";
import { apiGet, apiPost } from "../api/client";
import { LineChart } from "../charts/LineChart";
import type { AnyRecord } from "../types/domain";

export function Stocks() {
  const [code, setCode] = useState("600418");
  const [monitor, setMonitor] = useState<AnyRecord | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState("");

  async function load(stock = code) {
    setMonitor(await apiGet<AnyRecord>(`/workflows/stock-monitor/${stock}`));
  }

  async function sync() {
    setSyncing(true);
    setError("");
    try {
      await apiPost("/data/sync/daily", { stock_code: code });
      await apiPost("/data/sync/factors", { stock_code: code });
      await load(code);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "同步失败");
    } finally {
      setSyncing(false);
    }
  }

  useEffect(() => {
    load().catch(() => sync());
    const timer = window.setInterval(() => load(code).catch(() => undefined), 15000);
    return () => window.clearInterval(timer);
  }, []);

  const quote = monitor?.quote || {};
  const latest = monitor?.latest_signal || {};
  const dataWarning = quote.data_status !== "realtime";
  return (
    <section className="page">
      <div className="page-heading">
        <div>
          <h1>股票实时监测</h1>
          <p>同步日线行情并计算 MA、RSI、MACD、动量、波动率和成交量比率。页面定时更新数据，不重排布局。</p>
        </div>
        <div className="toolbar">
          <input value={code} onChange={(event) => setCode(event.target.value.replace(/\D/g, "").slice(0, 6))} maxLength={6} />
          <button className="secondary" onClick={() => load(code)}>立即刷新</button>
          <button onClick={sync} disabled={syncing}>{syncing ? "同步中" : "同步行情与因子"}</button>
        </div>
      </div>
      {error && <div className="error-banner">{error}</div>}
      <div className="metric-grid compact">
        <Metric label="最新价" value={num(quote.price)} tone={Number(quote.change_pct) >= 0 ? "up" : "down"} />
        <Metric label="涨跌幅" value={`${num(quote.change_pct)}%`} tone={Number(quote.change_pct) >= 0 ? "up" : "down"} />
        <Metric label="AI 得分" value={num(latest.score)} />
        <Metric label="信号" value={monitor?.suggestion?.action || latest.signal || "--"} />
        <Metric label="风险" value={latest.risk_level || "--"} />
        <Metric label="更新时间" value={quote.quote_time || monitor?.updated_at || "--"} />
      </div>
      <p className={`data-status ${dataWarning ? "warning" : ""}`}>实时源：{quote.source || "--"}；历史源：{latest.data_source || "--"}。{quote.message || ""}</p>
      <div className="two-column">
        <article className="panel">
          <h2>价格与均线</h2>
          <LineChart rows={monitor?.series || []} mode="price" />
        </article>
        <article className="panel">
          <h2>因子得分</h2>
          <LineChart rows={monitor?.series || []} mode="score" />
        </article>
      </div>
      <article className="panel">
        <h2>最近信号</h2>
        <div className="table-wrap">
          <table>
            <thead><tr><th>日期</th><th>收盘</th><th>MA20</th><th>动量</th><th>量比</th><th>得分</th><th>风险</th><th>信号</th></tr></thead>
            <tbody>{(monitor?.series || []).slice(-30).reverse().map((row: AnyRecord) => <tr key={row.trade_date}><td>{row.trade_date}</td><td>{num(row.close)}</td><td>{num(row.ma20)}</td><td>{pct(row.momentum_20d)}</td><td>{num(row.volume_ratio)}</td><td>{num(row.score)}</td><td>{row.risk_level}</td><td>{row.signal}</td></tr>)}</tbody>
          </table>
        </div>
      </article>
    </section>
  );
}

function Metric({ label, value, tone }: { label: string; value: unknown; tone?: string }) {
  return <article className={`metric-card ${tone || ""}`}><span>{label}</span><strong>{String(value)}</strong></article>;
}

function num(value: unknown) {
  const number = Number(value);
  return Number.isFinite(number) ? number.toFixed(2) : "--";
}

function pct(value: unknown) {
  return `${(Number(value || 0) * 100).toFixed(2)}%`;
}
