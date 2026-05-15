import { CheckCircle2, Database, Edit3, FlaskConical, Layers3, Play, Plus, Save, Trash2, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { apiDelete, apiGet, apiPatch, apiPost } from "../api/client";
import { LineChart } from "../charts/LineChart";
import type { AnyRecord, OperationState, SeriesPoint } from "../types/domain";

const DEFAULT_MODEL = {
  name: "A股日线数据模型",
  featureVersion: "feature_v1",
  description: "同步日线行情，计算技术因子，生成候选训练样本，并执行防未来函数检查。"
};

export function Datasets() {
  const [state, setState] = useState<OperationState | null>(null);
  const [selected, setSelected] = useState<AnyRecord | null>(null);
  const [stockCode, setStockCode] = useState("");
  const [selectedModelIds, setSelectedModelIds] = useState<number[]>([]);
  const [runResult, setRunResult] = useState<AnyRecord | null>(null);
  const [editingModelId, setEditingModelId] = useState<number | null>(null);
  const [editingSampleId, setEditingSampleId] = useState<number | null>(null);
  const [newModelName, setNewModelName] = useState(DEFAULT_MODEL.name);
  const [newFeatureVersion, setNewFeatureVersion] = useState(DEFAULT_MODEL.featureVersion);
  const [newDescription, setNewDescription] = useState(DEFAULT_MODEL.description);
  const [modelConfigText, setModelConfigText] = useState("{}");
  const [sampleFeatureText, setSampleFeatureText] = useState("");
  const [sampleLabelText, setSampleLabelText] = useState("");
  const [sampleQuality, setSampleQuality] = useState("80");
  const [sampleWeight, setSampleWeight] = useState("1");
  const [sampleStatus, setSampleStatus] = useState("candidate");
  const [sampleCanTrain, setSampleCanTrain] = useState(false);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  async function load() {
    const payload = await apiGet<OperationState>("/workflows/operation-state");
    setState(payload);
    const activeIds = (payload.data_models || [])
      .filter((model) => model.status !== "archived")
      .map((model) => Number(model.id));
    setSelectedModelIds((current) => current.filter((id) => activeIds.includes(id)));
    const datasetId = selected?.id || payload.datasets?.[0]?.id;
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
        pipeline_config_json: defaultPipeline(),
        schedule_config_json: { mode: "manual_or_daily", cron: "after_market_close" },
        status: "active"
      });
      resetModelForm();
      await load();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "创建数据模型失败");
    } finally {
      setBusy("");
    }
  }

  async function saveDataModel() {
    if (!editingModelId) return;
    setBusy("save-model");
    setError("");
    try {
      await apiPatch(`/data-models/${editingModelId}`, {
        name: newModelName,
        description: newDescription,
        feature_version: newFeatureVersion,
        pipeline_config_json: JSON.parse(modelConfigText || "{}")
      });
      resetModelForm();
      await load();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "保存数据模型失败，请检查 JSON。");
    } finally {
      setBusy("");
    }
  }

  async function deleteDataModel(model: AnyRecord) {
    if (!window.confirm(`删除数据模型「${model.name}」？历史运行记录会保留，模型将从当前列表归档。`)) return;
    setBusy(`delete-${model.id}`);
    setError("");
    try {
      await apiDelete(`/data-models/${model.id}`);
      setSelectedModelIds((current) => current.filter((id) => id !== Number(model.id)));
      await load();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "删除数据模型失败");
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

  async function saveSample() {
    if (!selected || !editingSampleId) return;
    setBusy("save-sample");
    setError("");
    try {
      await apiPatch(`/datasets/${selected.id}/samples/${editingSampleId}`, {
        features_json: JSON.parse(sampleFeatureText || "{}"),
        label_json: JSON.parse(sampleLabelText || "{}"),
        quality_score: Number(sampleQuality),
        sample_weight: Number(sampleWeight),
        status: sampleStatus,
        can_train: sampleCanTrain
      });
      setEditingSampleId(null);
      await load();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "保存样本失败，请检查 JSON。");
    } finally {
      setBusy("");
    }
  }

  useEffect(() => {
    load().catch((exc) => setError(exc instanceof Error ? exc.message : "加载失败"));
  }, []);

  const dataModels = (state?.data_models || []).filter((model) => model.status !== "archived");
  const datasets = state?.datasets || [];
  const selectedModels = useMemo(
    () => dataModels.filter((model) => selectedModelIds.includes(Number(model.id))),
    [dataModels, selectedModelIds]
  );
  const chartRows = ((runResult?.results?.[0]?.result?.preview_series || []) as AnyRecord[])
    .filter((row) => row.trade_date)
    .map((row) => ({ ...row, trade_date: String(row.trade_date) })) as SeriesPoint[];

  function toggleModel(id: number) {
    setSelectedModelIds((current) => current.includes(id) ? current.filter((item) => item !== id) : [...current, id]);
  }

  function resetModelForm() {
    setEditingModelId(null);
    setNewModelName(DEFAULT_MODEL.name);
    setNewFeatureVersion(DEFAULT_MODEL.featureVersion);
    setNewDescription(DEFAULT_MODEL.description);
    setModelConfigText(JSON.stringify(defaultPipeline(), null, 2));
  }

  function editModel(model: AnyRecord) {
    setEditingModelId(Number(model.id));
    setNewModelName(model.name || "");
    setNewFeatureVersion(model.feature_version || "feature_v1");
    setNewDescription(model.description || "");
    setModelConfigText(JSON.stringify(model.pipeline_config_json || defaultPipeline(), null, 2));
  }

  function editSample(sample: AnyRecord) {
    setEditingSampleId(Number(sample.id));
    setSampleFeatureText(JSON.stringify(sample.features_json || {}, null, 2));
    setSampleLabelText(JSON.stringify(sample.label_json || {}, null, 2));
    setSampleQuality(String(sample.quality_score ?? 80));
    setSampleWeight(String(sample.sample_weight ?? 1));
    setSampleStatus(sample.status || "candidate");
    setSampleCanTrain(Boolean(sample.can_train));
  }

  return (
    <section className="page data-model-page">
      <div className="page-heading">
        <div>
          <h1>数据模型编制与样本审核</h1>
          <p>先编制数据模型，再选择股票运行测试；测试会生成数据集和候选样本，样本审核通过后才供分析模型调用。</p>
        </div>
      </div>
      {error && <div className="error-banner">{error}</div>}

      <div className="process-strip">
        <Step icon={<Database size={18} />} title="1 编制数据模型" text="定义数据来源、因子版本、样本生成规则和防未来函数约束。" />
        <Step icon={<FlaskConical size={18} />} title="2 测试模型" text="选择股票和一个或多个数据模型执行，对比数据产物。" />
        <Step icon={<CheckCircle2 size={18} />} title="3 审核样本" text="人工批准、修改或排除样本，只有 approved + can_train 可进入训练。" />
        <Step icon={<Layers3 size={18} />} title="4 供分析模型调用" text="总控台选择股票、数据模型、分析模型后生成分析结果。" />
      </div>

      <div className="workbench model-workbench">
        <article className="panel command-panel">
          <h2>新增数据模型</h2>
          <label><span>模型名称</span><input value={newModelName} onChange={(event) => setNewModelName(event.target.value)} /></label>
          <label><span>因子版本</span><input value={newFeatureVersion} onChange={(event) => setNewFeatureVersion(event.target.value)} /></label>
          <label><span>模型说明</span><textarea value={newDescription} onChange={(event) => setNewDescription(event.target.value)} /></label>
          <button className="icon-button" onClick={createDataModel} disabled={busy === "create" || !newModelName.trim()}>
            <Plus size={16} /> {busy === "create" ? "创建中" : "创建数据模型"}
          </button>
        </article>

        <article className="panel">
          <div className="panel-title-row">
            <h2>已编制数据模型</h2>
            <span className="data-status">勾选模型后，可在下方对股票执行测试。</span>
          </div>
          <div className="card-list fixed-model-list">
            {dataModels.length === 0 && <Empty title="暂无数据模型" text="先在左侧创建数据模型，再选择股票运行测试。" />}
            {dataModels.map((model) => (
              <div className={`model-row ${selectedModelIds.includes(Number(model.id)) ? "active" : ""}`} key={model.id}>
                <label className="model-check">
                  <input type="checkbox" checked={selectedModelIds.includes(Number(model.id))} onChange={() => toggleModel(Number(model.id))} />
                  <span>
                    <strong>{model.name} · {model.version}</strong>
                    <small>{model.status} · feature={model.feature_version} · last_run={formatTime(model.last_run_at)}</small>
                    <em>{model.description}</em>
                  </span>
                </label>
                <div className="model-row-actions">
                  <button type="button" className="secondary icon-button" onClick={() => editModel(model)}><Edit3 size={14} /> 编辑</button>
                  <button type="button" className="danger icon-button" onClick={() => deleteDataModel(model)} disabled={busy === `delete-${model.id}`}>
                    <Trash2 size={14} /> 删除
                  </button>
                </div>
              </div>
            ))}
          </div>
        </article>
      </div>

      <article className="panel">
        <div className="panel-title-row">
          <div>
            <h2>模型测试与股票执行</h2>
            <p>运行测试会同步/读取该股票数据，执行所选数据模型，并生成数据集版本与候选训练样本。</p>
          </div>
          <span className={busy === "run" ? "status-pill warning-pill" : "status-pill"}>{busy === "run" ? "执行中" : "等待执行"}</span>
        </div>
        <div className="test-layout compact-test-layout">
          <div className="test-input-card">
            <label>
              <span>股票代码</span>
              <input placeholder="例如 600418" value={stockCode} onChange={(event) => setStockCode(event.target.value.replace(/\D/g, "").slice(0, 6))} />
            </label>
            <div className="selected-model-summary">
              <strong>已选模型</strong>
              <span>{selectedModels.length ? selectedModels.map((model) => model.name).join(" / ") : "未选择"}</span>
            </div>
          </div>
          <button className="icon-button primary-action" onClick={runSelectedModels} disabled={busy === "run"}>
            <Play size={16} /> {busy === "run" ? "运行中" : "运行测试"}
          </button>
        </div>
        <div className="run-feedback">
          <RunMetric label="股票" value={runResult?.stock_code || stockCode || "--"} />
          <RunMetric label="模型数量" value={String(runResult?.run_count ?? selectedModels.length)} />
          <RunMetric label="数据集" value={runResult?.results?.[0]?.result?.dataset?.dataset_name || "--"} />
          <RunMetric label="样本生成" value={String(runResult?.results?.[0]?.result?.dataset?.sample_count ?? "--")} />
        </div>
        {!runResult && <Empty title="尚未运行测试" text="输入股票代码、选择模型后点击运行测试；结果、图表和样本审核才会刷新。" />}
        <div className="result-grid">
          {(runResult?.results || []).map((item: AnyRecord) => (
            <article className="review-card" key={item.model.id}>
              <strong>{item.model.name}</strong>
              <span>股票 {item.result.stock_code} · 行数 {item.result.sync?.rows ?? "--"} · 最新得分 {num(item.result.factors?.latest_score?.score)}</span>
              <p>数据源：{item.result.sync?.data_source || "--"}；样本集：{item.result.dataset?.dataset_name || "--"}</p>
            </article>
          ))}
        </div>
        {chartRows.length > 0 && (
          <div className="two-column data-result-visual">
            <article className="panel inner-panel"><h2>运行后价格观察</h2><LineChart rows={chartRows} mode="price" /></article>
            <article className="panel inner-panel"><h2>运行后因子得分</h2><LineChart rows={chartRows} mode="score" /></article>
          </div>
        )}
      </article>

      <div className="workbench">
        <article className="panel">
          <h2>数据集版本</h2>
          <p className="panel-hint">数据集由模型测试生成；它不是单独手工填写的表，而是某次股票 + 数据模型运行后的样本容器。</p>
          <div className="card-list fixed-model-list">
            {datasets.length === 0 && <Empty title="暂无数据集版本" text="先运行一次模型测试，系统会生成数据集版本。" />}
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
          <p className="panel-hint">样本审核针对数据集。运行测试生成候选样本后，才能编辑、批准或设为负样本。</p>
          <div className="card-list fixed-sample-list">
            {(!selected || !selected.samples?.length) && <Empty title="暂无可审核样本" text="选择包含样本的数据集，或先运行模型测试生成候选样本。" />}
            {(selected?.samples || []).map((sample: AnyRecord) => (
              <div className="review-card" key={sample.id}>
                <strong>#{sample.id} {sample.sample_type}</strong>
                <span>{sample.status} · can_train={String(sample.can_train)} · stock={sample.stock_code || "--"} · source={sample.source_type}#{sample.source_id}</span>
                <pre>{JSON.stringify({ features: sample.features_json, label: sample.label_json }, null, 2)}</pre>
                <div>
                  <button className="secondary" onClick={() => editSample(sample)}>编辑样本</button>
                  <button onClick={() => approve(sample.id)}>批准训练</button>
                  <button className="secondary" onClick={() => exclude(sample.id)}>设为负样本</button>
                </div>
              </div>
            ))}
          </div>
        </article>
      </div>

      {editingModelId && (
        <div className="modal-backdrop">
          <article className="panel modal-panel">
            <div className="panel-title-row">
              <h2>编辑数据模型</h2>
              <button className="secondary icon-button" onClick={resetModelForm}><X size={15} /> 关闭</button>
            </div>
            <div className="modal-grid">
              <label><span>模型名称</span><input value={newModelName} onChange={(event) => setNewModelName(event.target.value)} /></label>
              <label><span>因子版本</span><input value={newFeatureVersion} onChange={(event) => setNewFeatureVersion(event.target.value)} /></label>
              <label className="full"><span>模型说明</span><textarea value={newDescription} onChange={(event) => setNewDescription(event.target.value)} /></label>
              <label className="full"><span>处理配置 JSON</span><textarea value={modelConfigText} onChange={(event) => setModelConfigText(event.target.value)} /></label>
            </div>
            <button className="icon-button" onClick={saveDataModel} disabled={busy === "save-model"}><Save size={16} /> {busy === "save-model" ? "保存中" : "保存模型"}</button>
          </article>
        </div>
      )}

      {editingSampleId && (
        <div className="modal-backdrop">
          <article className="panel modal-panel">
            <div className="panel-title-row">
              <h2>编辑样本 #{editingSampleId}</h2>
              <button className="secondary" onClick={() => setEditingSampleId(null)}>关闭</button>
            </div>
            <div className="sample-edit-grid">
              <label><span>特征 JSON</span><textarea value={sampleFeatureText} onChange={(event) => setSampleFeatureText(event.target.value)} /></label>
              <label><span>标签 JSON</span><textarea value={sampleLabelText} onChange={(event) => setSampleLabelText(event.target.value)} /></label>
              <label><span>质量分</span><input type="number" value={sampleQuality} onChange={(event) => setSampleQuality(event.target.value)} /></label>
              <label><span>样本权重</span><input type="number" step="0.1" value={sampleWeight} onChange={(event) => setSampleWeight(event.target.value)} /></label>
              <label><span>状态</span><select value={sampleStatus} onChange={(event) => setSampleStatus(event.target.value)}><option value="candidate">candidate</option><option value="approved">approved</option><option value="rejected">rejected</option><option value="negative_sample">negative_sample</option><option value="invalid">invalid</option><option value="deprecated">deprecated</option></select></label>
              <label className="toggle-row"><input type="checkbox" checked={sampleCanTrain} onChange={(event) => setSampleCanTrain(event.target.checked)} /><span>允许训练</span></label>
            </div>
            <button className="icon-button" onClick={saveSample} disabled={busy === "save-sample"}><Save size={16} /> {busy === "save-sample" ? "保存中" : "保存样本"}</button>
          </article>
        </div>
      )}
    </section>
  );
}

function Step({ icon, title, text }: { icon: React.ReactNode; title: string; text: string }) {
  return <article><div>{icon}<strong>{title}</strong></div><p>{text}</p></article>;
}

function Empty({ title, text }: { title: string; text: string }) {
  return <div className="empty-state"><strong>{title}</strong><span>{text}</span></div>;
}

function RunMetric({ label, value }: { label: string; value: string }) {
  return <div className="small-metric"><span>{label}</span><strong>{value}</strong></div>;
}

function defaultPipeline() {
  return {
    sync_daily: true,
    compute_factors: true,
    generate_dataset: true,
    price_adjust: "qfq",
    data_sources: ["eastmoney", "tencent", "sina"],
    leakage_guard: "trade_date_or_before"
  };
}

function formatTime(value: unknown) {
  if (!value) return "--";
  return String(value).replace("T", " ").replace("+08:00", "");
}

function num(value: unknown) {
  const number = Number(value);
  return Number.isFinite(number) ? number.toFixed(2) : "--";
}
