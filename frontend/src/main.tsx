import { StrictMode, useState } from "react";
import { createRoot } from "react-dom/client";
import { Layout, type PageKey } from "./components/Layout";
import { Agents } from "./pages/Agents";
import { Backtests } from "./pages/Backtests";
import { Dashboard } from "./pages/Dashboard";
import { Datasets } from "./pages/Datasets";
import { DirtyData } from "./pages/DirtyData";
import { Models } from "./pages/Models";
import { Simulation } from "./pages/Simulation";
import { Stocks } from "./pages/Stocks";
import { Strategies } from "./pages/Strategies";
import "./styles.css";

function App() {
  const [page, setPage] = useState<PageKey>("dashboard");
  return (
    <Layout page={page} setPage={setPage}>
      {page === "dashboard" && <Dashboard />}
      {page === "stocks" && <Stocks />}
      {page === "agents" && <Agents />}
      {page === "strategies" && <Strategies />}
      {page === "backtests" && <Backtests />}
      {page === "datasets" && <Datasets />}
      {page === "models" && <Models />}
      {page === "simulation" && <Simulation />}
      {page === "dirty" && <DirtyData />}
    </Layout>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>
);

