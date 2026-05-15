import { CheckCircle2, Database, FlaskConical, Layers3, Play, Plus } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { apiGet, apiPost } from "../api/client";
import type { AnyRecord, OperationState } from "../types/domain";

export function Datasets() {
  const [state, setState] = useState<OperationState | null>(null);
  const [selected, setSelected] = useState<AnyRecord | null>(null);
  const [stockCode, setStockCode] = useState("");
  const [selectedModelIds, setSelectedModelIds] = useState<number[]>([]);
  const [runResult, setRunResult] = useState<AnyRecord | null>(null);
  const [newModelName, setNewModelName] = useState("自定义A股日线数据模型");
  const [newFeatureVersion, setNewFeatureVersion] = useState("feature_v1");
  const [newDescription, setNewDescription] = useState("定义行情同步、因子计算、样本生成和防未来函数约束。");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  async function load() {
    const payload = await apiGet<OperationState>("/workflows/operation-state");
    setState(payload);
    const modelIds = payload.data_models?.map((model) => Number(model.id)) || [];
    if (!selectedModelIds.length && modelIds[0]) setSelectedModelIds([modelIds[0]]);
    const datasetId = selected?.id || payload.datasets[0]?.id;
    if (datasetId) setSelected(await apiGet(`/datasets/${datasetId}`));
  }

  async function createDataModel() {
    setBusy("create");
    setError("");
    try {
      await apiPost("/data-models", {
        name: newModelName,
        version: `v${(state?.data_models?.length || 0) + 1}`,
        description: newDescription,
        feature_version: newFeatureVersion,
        pipeline_config_json: {
          sync_daily: true,
          compute_factors: true,
          generate_dataset: true,
          price_adjust: "qfq",
          data_sources: ["eastmoney", "tencent", "sina"],
          leakage_guard: "trade_date_or_before"
        },
        schedule_config_json: { mode: "manual_or_daily", cron: "after_market_close" },
        status: "active"
      });
      await load();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "创建数据模型失败");
    } finally {
      setBusy("");
    }
  }

  async function runSelectedModels() {
    setBusy("run");
    setError("");
    setRunResult(null);
    try {
      if (stockCode.length !== 6) throw new Error("请先输入 6 位股票代码。");
      if (!selectedModelIds.length) throw new Error("请至少选择一个数据模型。");
      const payload = await apiPost<AnyRecord>("/data-models/batch-run", {
        stock_code: stockCode,
        data_model_ids: selectedModelIds,
        generate_dataset: true
      });
      setRunResult(payload);
      await load();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "数据模型测试失败");
    } finally {
      setBusy("");
    }
  }

  async function approve(id: number) {
    if (!selected) return;
    await apiPost(`/datasets/${selected.id}/approve-samples`, { sample_ids: [id], status: "approved", can_train: true, reviewed_by: "user" });
    await load();
  }

  async function exclude(id: number) {
    if (!selected) return;
    await apiPost(`/datasets/${selected.id}/exclude-samples`, { sample_ids: [id], status: "negative_sample", can_train: false, reviewed_by: "user" });
    await load();
  }

  useEffect(() => { load().catch((exc) => setError(exc instanceof Error ? exc.message : "加载失败")); }, []);

  const dataModels = state?.data_models || [];
  const datasets = state?.datasets || [];
  const selectedModels = useMemo(() => dataModels.filter((model) => selectedModelIds.includes(Number(model.id))), [dataModels, selectedModelIds]);

  function toggleModel(id: number) {
    setSelectedModelIds((current) => current.includes(id) ? current.filter((item) => item !== id) : [...current, id]);
  }

  return (
    <section className="page data-model-page">
      <div className="page-heading">
        <div>
          <h1>数据模型编制与样本审核</h1>
          <p>合理顺序是：先编制数据模型，再选择股票测试模型，随后审核生成的样本，最后把通过审核的数据供分析模型调用。</p>
        </div>
      </div>
      {error && <div className="error-banner">{error}</div>}

      <div className="process-strip">
        <Step icon={<Database size={18} />} title="1 编制数据模型" text="定义数据来源、因子版本、样本生成规则和防未来函数约束。" />
        <Step icon={<FlaskConical size={18} />} title="2 测试模型" text="选择股票与一个或多个数据模型执行，对比数据产物。" />
        <Step icon={<CheckCircle2 size={18} />} title="3 审核样本" text="人工批准或排除样本，只有 approved + can_train 可进入训练。" />
        <Step icon={<Layers3 size={18} />} title="4 供分析模型调用" text="总控台选择股票、数据模型、分析模型后生成分析结果。" />
      </div>

      <div className="workbench">
        <article className="panel command-panel">
          <span className="section-label">模型编制</span>
          <h2>新增数据模型</h2>
          <label><span>模型名称</span><input value={newModelName} onChange={(event) => setNewModelName(event.target.value)} /></label>
          <label><span>因子版本</span><input value={newFeatureVersion} onChange={(event) => setNewFeatureVersion(event.target.value)} /></label>
          <label><span>模型说明</span><textarea value={newDescription} onChange={(event) => setNewDescription(event.target.value)} /></label>
          <button className="icon-button" onClick={createDataModel} disabled={busy === "create" || !newModelName.trim()}><Plus size={16} /> {busy === "create" ? "创建中" : "创建数据模型"}</button>
        </article>

        <article className="panel">
          <h2>已编制数据模型</h2>
          <div className="card-list fixed-model-list">
            {dataModels.map((model) => (
              <label className={`model-check-card ${selectedModelIds.includes(Number(model.id)) ? "active" : ""}`} key={model.id}>
                <input type="checkbox" checked={selectedModelIds.includes(Number(model.id))} onChange={() => toggleModel(Number(model.id))} />
                <span>
                  <strong>{model.name} · {model.version}</strong>
                  <small>{model.status} · feature={model.feature_version} · last_run={formatTime(model.last_run_at)}</small>
                  <em>{model.description}</em>
                </span>
              </label>
            ))}
          </div>
        </article>
      </div>

      <article className="panel">
        <div className="panel-title-row">
          <h2>模型测试与股票执行</h2>
          <span className="data-status">不再默认执行 600418；必须输入股票代码并选择模型。</span>
        </div>
        <div className="run-bar">
          <label>
            <span>股票代码</span>
            <input placeholder="例如 600418" value={stockCode} onChange={(event) => setStockCode(event.target.value.replace(/\D/g, "").slice(0, 6))} />
          </label>
          <div className="selected-model-summary">
            <strong>已选模型</strong>
            <span>{selectedModels.length ? selectedModels.map((model) => model.name).join(" / ") : "未选择"}</span>
          </div>
          <button className="icon-button" onClick={runSelectedModels} disabled={busy === "run"}><Play size={16} /> {busy === "run" ? "执行中" : "运行测试"}</button>
        </div>
        <div className="result-grid">
          {(runResult?.results || []).map((item: AnyRecord) => (
            <article className="review-card" key={item.model.id}>
              <strong>{item.model.name}</strong>
              <span>股票 {item.result.stock_code} · 行数 {item.result.sync?.rows ?? "--"} · 最新得分 {num(item.result.factors?.latest_score?.score)}</span>
              <p>数据源：{item.result.sync?.data_source || "--"}；样本集：{item.result.dataset?.dataset_name || "--"}</p>
            </article>
          ))}
        </div>
      </article>

      <div className="workbench">
        <article className="panel">
          <h2>数据集版本</h2>
          <div className="card-list fixed-model-list">
            {datasets.map((dataset) => (
              <button className={`list-button ${selected?.id === dataset.id ? "active" : ""}`} key={dataset.id} onClick={() => apiGet<AnyRecord>(`/datasets/${dataset.id}`).then(setSelected)}>
                <strong>{dataset.dataset_name} · {dataset.version}</strong>
                <span>samples {dataset.sample_count} · approved {dataset.approved_sample_count} · excluded {dataset.excluded_sample_count}</span>
              </button>
            ))}
          </div>
        </article>

        <article className="panel">
          <h2>样本审核</h2>
          <div className="card-list fixed-sample-list">
            {(selected?.samples || []).map((sample: AnyRecord) => (
              <div className="review-card" key={sample.id}>
                <strong>#{sample.id} {sample.sample_type}</strong>
                <span>{sample.status} · can_train={String(sample.can_train)} · stock={sample.stock_code || "--"} · source={sample.source_type}#{sample.source_id}</span>
                <pre>{JSON.stringify({ features: sample.features_json, label: sample.label_json }, null, 2)}</pre>
                <div>
                  <button onClick={() => approve(sample.id)}>批准训练</button>
                  <button className="secondary" onClick={() => exclude(sample.id)}>设为负样本</button>
                </div>
              </div>
            ))}
          </div>
        </article>
      </div>
    </section>
  );
}

function Step({ icon, title, text }: { icon: React.ReactNode; title: string; text: string }) {
  return <article><div>{icon}<strong>{title}</strong></div><p>{text}</p></article>;
}

function formatTime(value: unknown) {
  if (!value) return "--";
  return String(value).replace("T", " ").replace("+08:00", "");
}

function num(value: unknown) {
  const number = Number(value);
  return Number.isFinite(number) ? number.toFixed(2) : "--";
}
