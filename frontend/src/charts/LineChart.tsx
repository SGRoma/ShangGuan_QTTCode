import { useEffect, useRef } from "react";
import * as echarts from "echarts";
import type { SeriesPoint } from "../types/domain";

interface LineChartProps {
  rows: SeriesPoint[];
  mode: "equity" | "drawdown" | "score" | "price";
}

export function LineChart({ rows, mode }: LineChartProps) {
  const ref = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!ref.current) return;
    const chart = echarts.init(ref.current);
    const x = rows.map((row) => row.trade_date);
    const option =
      mode === "drawdown"
        ? {
            grid: { left: 48, right: 16, top: 24, bottom: 36 },
            tooltip: { trigger: "axis" },
            xAxis: { type: "category", data: x },
            yAxis: { type: "value" },
            series: [{ name: "回撤", type: "line", data: rows.map((row) => row.drawdown), smooth: true, areaStyle: {}, color: "#15803d" }]
          }
        : mode === "score"
          ? {
              grid: { left: 48, right: 16, top: 24, bottom: 36 },
              tooltip: { trigger: "axis" },
              xAxis: { type: "category", data: x },
              yAxis: { type: "value", min: 0, max: 100 },
              series: [{ name: "多因子得分", type: "line", data: rows.map((row) => row.score), smooth: true, color: "#2563eb" }]
            }
          : mode === "price"
            ? {
                grid: { left: 48, right: 16, top: 24, bottom: 36 },
                tooltip: { trigger: "axis" },
                legend: { top: 0 },
                xAxis: { type: "category", data: x },
                yAxis: { type: "value", scale: true },
                series: [
                  { name: "收盘价", type: "line", data: rows.map((row) => row.close), smooth: true, color: "#d4382f" },
                  { name: "MA20", type: "line", data: rows.map((row) => row.ma20), smooth: true, color: "#2563eb" },
                  { name: "MA60", type: "line", data: rows.map((row) => row.ma60), smooth: true, color: "#64748b" }
                ]
              }
          : {
              grid: { left: 48, right: 16, top: 24, bottom: 36 },
              tooltip: { trigger: "axis" },
              legend: { top: 0 },
              xAxis: { type: "category", data: x },
              yAxis: { type: "value" },
              series: [
                { name: "策略净值", type: "line", data: rows.map((row) => row.equity_curve), smooth: true, color: "#d4382f" },
                { name: "基准净值", type: "line", data: rows.map((row) => row.benchmark_curve), smooth: true, color: "#64748b" }
              ]
            };
    chart.setOption(option);
    const resize = () => chart.resize();
    window.addEventListener("resize", resize);
    return () => {
      window.removeEventListener("resize", resize);
      chart.dispose();
    };
  }, [rows, mode]);

  return <div className="chart-surface" ref={ref} />;
}
