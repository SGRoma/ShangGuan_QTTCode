import { useEffect, useMemo, useState } from "react";
import { apiGet, apiPost } from "../api/client";
import type { AnyRecord, OperationState } from "../types/domain";

export function DirtyData() {
  const [state, setState] = useState<OperationState | null>(null);
  const [rows, setRows] = useState<AnyRecord[]>([]);
  const [targetType, setTargetType] = useState("training_sample");
  const [targetId, setTargetId] = useState("");
  const [impact, setImpact] = useState<AnyRecord | null>(null);
  const [error, setError] = useState("");

  async function load() {
    const [operation, dirty] = await Promise.all([
      apiGet<OperationState>("/workflows/operation-state"),
      apiGet<{ rows: AnyRecord[] }>("/dirty-data")
    ]);
    setState(operation);
    setRows(dirty.rows);
    if (!targetId) {
      const first = firstTarget(operation, targetType);
      if (first) setTargetId(String(first.id));
    }
  }

  async function mark() {
    setError("");
    try {
      const payload = await apiPost<AnyRecord>("/dirty-data/mark", {
        target_type: targetType,
        target_id: Number(targetId),
        dirty_type: "invalid",
        action: "invalid",
        description: "人工标记疑似脏数据"
      });
      setImpact(payload.impact);
      await load();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "标记失败");
    }
  }

  async function inspect(id: number) {
    setImpact(await apiGet(`/dirty-data/${id}/impact`));
  }

  useEffect(() => { load().catch((exc) => setError(exc instanceof Error ? exc.message : "加载失败")); }, []);

  const options = useMemo(() => targets(state, targetType), [state, targetType]);
  return (
    <section className="page">
      <div className="page-heading">
        <div>
          <h1>脏数据管理</h1>
          <p>选择真实对象进行标记、隔离和影响分析。样本或数据集污染会追踪到相关模型。</p>
        </div>
      </div>
      {error && <div className="error-banner">{error}</div>}
      <div className="workbench">
        <article className="panel command-panel">
          <h2>标记脏数据</h2>
          <label>
            <span>目标类型</span>
            <select value={targetType} onChange={(event) => { setTargetType(event.target.value); setTargetId(""); }}>
              <option value="training_sample">训练样本</option>
              <option value="dataset_version">数据集版本</option>
              <option value="quant_model_version">模型版本</option>
            </select>
          </label>
          <label>
            <span>目标对象</span>
            <select value={targetId} onChange={(event) => setTargetId(event.target.value)}>
              {options.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
            </select>
          </label>
          <button className="danger" onClick={mark} disabled={!targetId}>标记并隔离</button>
        </article>
        <article className="panel">
          <h2>影响分析</h2>
          <pre>{JSON.stringify(impact, null, 2)}</pre>
        </article>
      </div>
      <article className="panel">
        <h2>脏数据记录</h2>
        <div className="table-wrap">
          <table>
            <thead><tr><th>ID</th><th>目标</th><th>类型</th><th>状态</th><th>操作</th></tr></thead>
            <tbody>{rows.map((row) => <tr key={row.id}><td>{row.id}</td><td>{row.target_type} #{row.target_id}</td><td>{row.dirty_type}</td><td>{row.status}</td><td><button onClick={() => inspect(row.id)}>影响</button></td></tr>)}</tbody>
          </table>
        </div>
      </article>
    </section>
  );
}

function firstTarget(state: OperationState | null, type: string) {
  return targets(state, type)[0];
}

function targets(state: OperationState | null, type: string) {
  if (!state) return [];
  if (type === "dataset_version") {
    return state.datasets.map((dataset) => ({ id: dataset.id, label: `${dataset.dataset_name} ${dataset.version} #${dataset.id}` }));
  }
  if (type === "quant_model_version") {
    return state.models.map((model) => ({ id: model.id, label: `${model.model_name} ${model.version} #${model.id}` }));
  }
  const samples = state.training_samples || [];
  return samples.length
    ? samples.map((sample) => ({ id: sample.id, label: `样本 #${sample.id} · ${sample.sample_type} · ${sample.status}` }))
    : [{ id: 1, label: "训练样本 #1" }];
}
