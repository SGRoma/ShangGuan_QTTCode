import { BarChart3, Bot, Database, FileWarning, FlaskConical, LineChart, ShieldCheck, WalletCards } from "lucide-react";
import type { ReactNode } from "react";

export type PageKey = "dashboard" | "stocks" | "agents" | "strategies" | "backtests" | "datasets" | "models" | "simulation" | "dirty";

const nav = [
  {
    title: "总览",
    items: [{ key: "dashboard", label: "研究总控台", icon: BarChart3 }]
  },
  {
    title: "智能体",
    items: [
      { key: "agents", label: "智能体工作台", icon: Bot },
      { key: "strategies", label: "策略生成", icon: FlaskConical }
    ]
  },
  {
    title: "数据模型",
    items: [
      { key: "stocks", label: "行情与因子", icon: LineChart },
      { key: "datasets", label: "训练样本", icon: Database },
      { key: "dirty", label: "脏数据治理", icon: FileWarning }
    ]
  },
  {
    title: "分析模型",
    items: [
      { key: "models", label: "模型迭代", icon: ShieldCheck },
      { key: "backtests", label: "回测分析", icon: BarChart3 },
      { key: "simulation", label: "模拟盘", icon: WalletCards }
    ]
  }
] as const;

interface LayoutProps {
  page: PageKey;
  setPage: (page: PageKey) => void;
  children: ReactNode;
}

export function Layout({ page, setPage, children }: LayoutProps) {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">AQ</div>
          <div>
            <strong>AIQuant</strong>
            <span>研究与模拟交易平台</span>
          </div>
        </div>
        <nav>
          {nav.map((group) => (
            <div className="nav-group" key={group.title}>
              <span>{group.title}</span>
              {group.items.map((item) => {
                const Icon = item.icon;
                return (
                  <button key={item.key} className={page === item.key ? "active" : ""} onClick={() => setPage(item.key as PageKey)}>
                    <Icon size={17} />
                    {item.label}
                  </button>
                );
              })}
            </div>
          ))}
        </nav>
      </aside>
      <main className="content">{children}</main>
    </div>
  );
}
