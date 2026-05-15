import { useEffect, useState } from "react";
import { apiGet, apiPost } from "../api/client";
import type { AnyRecord, OperationState } from "../types/domain";

export function Datasets() {
  const [state, setState] = useState<OperationState | null>(null);
  const [selected, setSelected] = useState<AnyRecord | null>(null);
  const [stockCode, setStockCode] = useState("600418");
  const [dataModelId, setDataModelId] = useState("");
  const [error, setError] = useState("");

  async function load() {
    const payload = await apiGet<OperationState>("/workflows/operation-state");
    setState(payload);
    if (!dataModelId && payload.data_models?.[0]) setDataModelId(String(payload.data_models[0].id));
    const datasetId = selected?.id || payload.datasets[0]?.id;
    if (datasetId) setSelected(await apiGet(`/datasets/${datasetId}`));
  }

  async function runDataModel() {
    setError("");
    try {
      await apiPost(`/data-models/${dataModelId}/run`, { stock_code: stockCode, data_model_id: Number(dataModelId), generate_dataset: true });
      await load();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "数据模型执行失败");
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

  return (
    <section className="page">
      <div className="page-heading">
        <div>
          <h1>数据模型与训练样本</h1>
          <p>数据模型负责定期执行：同步行情、计算因子、生成数据集和样本，是分析模型运行的地基。</p>
        </div>
      </div>
      {error && <div className="error-banner">{error}</div>}
      <div className="workbench">
        <article className="panel command-panel">
          <h2>执行数据模型</h2>
          <label><span>股票代码</span><input value={stockCode} onChange={(event) => setStockCode(event.target.value.replace(/\D/g, "").slice(0, 6))} /></label>
          <label>
            <span>数据模型</span>
            <select value={dataModelId} onChange={(event) => setDataModelId(event.target.value)}>
              {(state?.data_models || []).map((model) => <option key={model.id} value={model.id}>{model.name} · {model.version}</option>)}
            </select>
          </label>
          <button onClick={runDataModel} disabled={!dataModelId}>运行数据模型</button>
          <div className="card-list">
            {(state?.data_models || []).map((model) => (
              <div className="review-card" key={model.id}>
                <strong>{model.name} · {model.version}</strong>
                <span>{model.status} · last_run={model.last_run_at || "--"}</span>
                <p>{model.description}</p>
              </div>
            ))}
          </div>
        </article>
        <article className="panel">
          <h2>数据集版本</h2>
          <div className="card-list">
            {(state?.datasets || []).map((dataset) => (
              <button className="list-button" key={dataset.id} onClick={() => apiGet<AnyRecord>(`/datasets/${dataset.id}`).then(setSelected)}>
                <strong>{dataset.dataset_name} · {dataset.version}</strong>
                <span>samples {dataset.sample_count} · approved {dataset.approved_sample_count} · excluded {dataset.excluded_sample_count}</span>
              </button>
            ))}
          </div>
        </article>
      </div>
      <article className="panel">
        <h2>样本审核</h2>
        <div className="card-list">
          {(selected?.samples || []).map((sample: AnyRecord) => (
            <div className="review-card" key={sample.id}>
              <strong>#{sample.id} {sample.sample_type}</strong>
              <span>{sample.status} · can_train={String(sample.can_train)} · source={sample.source_type}#{sample.source_id}</span>
              <pre>{JSON.stringify({ features: sample.features_json, label: sample.label_json }, null, 2)}</pre>
              <div>
                <button onClick={() => approve(sample.id)}>批准训练</button>
                <button className="secondary" onClick={() => exclude(sample.id)}>设为负样本</button>
              </div>
            </div>
          ))}
        </div>
      </article>
    </section>
  );
}
