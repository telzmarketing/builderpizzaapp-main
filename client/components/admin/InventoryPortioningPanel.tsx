import { useEffect, useMemo, useState } from "react";
import { Loader2, Pencil, Plus, RefreshCw, X } from "lucide-react";
import {
  inventoryApi,
  type InventoryItem,
  type InventoryOverview,
  type InventoryPortionConfig,
} from "@/lib/api";
import { formatQuantity } from "@/lib/formatQuantity";
import { filterAndSort, InventoryTableControls } from "./InventoryTableControls";

const input =
  "w-full rounded-lg border border-surface-03 bg-surface-01 px-3 py-2 text-sm text-cream";
const button =
  "inline-flex items-center justify-center gap-2 rounded-lg bg-gold px-3 py-2 text-sm font-black text-black disabled:opacity-60";
const ghost =
  "inline-flex items-center justify-center gap-2 rounded-lg border border-surface-03 px-3 py-2 text-sm font-bold text-stone hover:text-cream";
const opKey = (prefix: string) => `${prefix}:${crypto.randomUUID()}`;
export function formatExactQuantity(value: number | string | null | undefined) {
  return formatQuantity(value);
}
export function portionUsageLabel(
  value: InventoryPortionConfig["usage"] | string,
) {
  return value === "mandatory"
    ? "Obrigatório"
    : value === "optional"
      ? "Opcional"
      : "Uso direto";
}
type Form = {
  source_item_id: string;
  usage: InventoryPortionConfig["usage"];
  portion_weight: string;
  unit_id: string;
  reference_fraction: string;
  size: string;
  min_stock: string;
  target_stock: string;
  shelf_life_days: string;
  yield_percent: string;
  loss_percent: string;
  technical_instructions: string;
  handling_instructions: string;
};
const initial = (): Form => ({
  source_item_id: "",
  usage: "mandatory",
  portion_weight: "",
  unit_id: "",
  reference_fraction: "0.5",
  size: "",
  min_stock: "0",
  target_stock: "0",
  shelf_life_days: "",
  yield_percent: "100",
  loss_percent: "0",
  technical_instructions: "",
  handling_instructions: "",
});

export default function InventoryPortioningPanel() {
  const [overview, setOverview] = useState<InventoryOverview | null>(null),
    [configs, setConfigs] = useState<InventoryPortionConfig[]>([]),
    [form, setForm] = useState<Form>(initial),
    [editing, setEditing] = useState<InventoryPortionConfig | null>(null),
    [loading, setLoading] = useState(true),
    [saving, setSaving] = useState(false),
    [message, setMessage] = useState(""),
    [error, setError] = useState(""),
    [quantities, setQuantities] = useState<Record<string, string>>({});
  const [search, setSearch] = useState(""),
    [sort, setSort] = useState<"name" | "weight">("name");
  const update = (v: Partial<Form>) => setForm((x) => ({ ...x, ...v }));
  const visibleConfigs = useMemo(() => filterAndSort(configs, search, sort, { name: (config) => `${config.output_item_name} ${config.source_item_name}`, weight: (config) => Number(config.portion_weight) || 0 }), [configs, search, sort]);
  async function load() {
    setLoading(true);
    try {
      const [o, c] = await Promise.all([
        inventoryApi.overview(),
        inventoryApi.portionConfigs(true),
      ]);
      setOverview(o);
      setConfigs(c);
      if (!form.unit_id && o.units[0]) update({ unit_id: o.units[0].id });
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Falha ao carregar porcionamentos.",
      );
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    void load();
  }, []);
  function edit(c: InventoryPortionConfig) {
    setEditing(c);
    setForm({
      source_item_id: c.source_item_id,
      usage: c.usage,
      portion_weight: String(c.portion_weight),
      unit_id: c.unit_id,
      reference_fraction: String(c.reference_fraction),
      size: c.size || "",
      min_stock: String(c.min_stock),
      target_stock: String(c.target_stock),
      shelf_life_days:
        c.shelf_life_days == null ? "" : String(c.shelf_life_days),
      yield_percent: String(c.yield_percent),
      loss_percent: String(c.loss_percent),
      technical_instructions: c.technical_instructions || "",
      handling_instructions: c.handling_instructions || "",
    });
  }
  function cancel() {
    setEditing(null);
    setForm((x) => ({
      ...x,
      source_item_id: "",
      portion_weight: "",
      size: "",
    }));
  }
  async function save() {
    setSaving(true);
    setError("");
    try {
      if (!form.source_item_id || !form.portion_weight || !form.unit_id)
        throw new Error("Informe insumo, peso e unidade.");
      const min = Number(form.min_stock),
        target = Number(form.target_stock);
      if (target < min)
        throw new Error("O estoque-alvo deve ser maior ou igual ao mínimo.");
      const p = {
        source_item_id: form.source_item_id,
        usage: form.usage,
        portion_weight: Number(form.portion_weight),
        unit_id: form.unit_id,
        reference_fraction: Number(form.reference_fraction),
        size: form.size || null,
        min_stock: min,
        target_stock: target,
        shelf_life_days: form.shelf_life_days
          ? Number(form.shelf_life_days)
          : null,
        yield_percent: Number(form.yield_percent),
        loss_percent: Number(form.loss_percent),
        technical_instructions: form.technical_instructions.trim() || null,
        handling_instructions: form.handling_instructions.trim() || null,
        active: true,
      };
      if (editing)
        await inventoryApi.updatePortionConfig(
          editing.id,
          p,
          opKey(`update:${editing.id}`),
        );
      else await inventoryApi.createPortionConfig(p, opKey("create"));
      setMessage(
        editing ? "Configuracao atualizada." : "Configuracao cadastrada.",
      );
      cancel();
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Nao foi possivel salvar.");
    } finally {
      setSaving(false);
    }
  }
  async function remove(c: InventoryPortionConfig) {
    if (!confirm(`Desativar ${c.output_item_name || "esta configuracao"}?`))
      return;
    setSaving(true);
    try {
      await inventoryApi.deactivatePortionConfig(c.id, opKey(`delete:${c.id}`));
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Nao foi possivel desativar.");
    } finally {
      setSaving(false);
    }
  }
  if (loading)
    return (
      <div className="flex min-h-40 items-center justify-center text-stone">
        <Loader2 size={18} className="mr-2 animate-spin" />
        Carregando porcionamentos...
      </div>
    );
  const items = (overview?.items ?? []).filter(
    (i: InventoryItem) => i.active && i.item_type !== "finished_good",
  );
  return (
    <section className="space-y-5 rounded-lg border border-surface-03 bg-surface-02 p-5">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-black text-cream">
            Cadastro de Porcionamento
          </h2>
          <p className="text-sm text-stone">
            Todos os insumos cadastrados aparecem para escolha.
          </p>
        </div>
        <button type="button" className={ghost} onClick={() => void load()}>
          <RefreshCw size={15} /> Atualizar
        </button>
      </div>
      <div className="grid gap-5 xl:grid-cols-[24rem_minmax(0,1fr)]">
        <div className="rounded-lg border border-surface-03 bg-surface-01 p-4">
          <h3 className="font-black text-cream">
            {editing ? "Editar configuração" : "Nova configuração"}
          </h3>
          {editing && (
            <button type="button" className={`${ghost} mt-2`} onClick={cancel}>
              Cancelar edição
            </button>
          )}
          <div className="mt-4 space-y-3">
            <label className="block text-xs text-stone">
              Insumo de origem
              <select
                className={input}
                value={form.source_item_id}
                onChange={(e) => update({ source_item_id: e.target.value })}
              >
                <option value="">Selecione o insumo</option>
                {items.map((i) => (
                  <option key={i.id} value={i.id}>
                    {i.name}
                    {i.unit_symbol ? ` (${i.unit_symbol})` : ""}
                  </option>
                ))}
              </select>
            </label>
            <label className="block text-xs text-stone">
              Uso operacional
              <select
                className={input}
                value={form.usage}
                onChange={(e) =>
                  update({ usage: e.target.value as Form["usage"] })
                }
              >
                <option value="mandatory">Porcionamento obrigatório</option>
                <option value="optional">Porcionamento opcional</option>
                <option value="direct">Utilização direta</option>
              </select>
            </label>
            <div className="grid grid-cols-2 gap-3">
              <label className="text-xs text-stone">
                Peso
                <input
                  className={input}
                  type="number"
                  min="0.000001"
                  step="0.000001"
                  value={form.portion_weight}
                  onChange={(e) => update({ portion_weight: e.target.value })}
                />
              </label>
              <label className="text-xs text-stone">
                Unidade
                <select
                  className={input}
                  value={form.unit_id}
                  onChange={(e) => update({ unit_id: e.target.value })}
                >
                  {(overview?.units ?? []).map((u) => (
                    <option key={u.id} value={u.id}>
                      {u.name} ({u.symbol})
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <label className="text-xs text-stone">
                Referência
                <select
                  className={input}
                  value={form.reference_fraction}
                  onChange={(e) =>
                    update({ reference_fraction: e.target.value })
                  }
                >
                  <option value="0.5">Meia pizza</option>
                  <option value="1">Pizza inteira</option>
                </select>
              </label>
              <label className="text-xs text-stone">
                Tamanho
                <input
                  className={input}
                  value={form.size}
                  onChange={(e) => update({ size: e.target.value })}
                />
              </label>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <label className="text-xs text-stone">
                Estoque mínimo
                <input
                  className={input}
                  type="number"
                  value={form.min_stock}
                  onChange={(e) => update({ min_stock: e.target.value })}
                />
              </label>
              <label className="text-xs text-stone">
                Estoque-alvo
                <input
                  className={input}
                  type="number"
                  value={form.target_stock}
                  onChange={(e) => update({ target_stock: e.target.value })}
                />
              </label>
            </div>
            <label className="block text-xs text-stone">
              Ficha técnica de porcionamento
              <textarea className={`${input} min-h-24`} value={form.technical_instructions} onChange={(e) => update({ technical_instructions: e.target.value })} placeholder="Descreva o preparo, a porção e a gramatura." />
            </label>
            <label className="block text-xs text-stone">
              Manuseio e armazenamento
              <textarea className={`${input} min-h-20`} value={form.handling_instructions} onChange={(e) => update({ handling_instructions: e.target.value })} placeholder="Informe cuidados, embalagem, validade e armazenamento." />
            </label>
            <button
              type="button"
              className={button}
              disabled={saving || !items.length}
              onClick={() => void save()}
            >
              <Plus size={15} />{" "}
              {editing ? "Salvar alteração" : "Cadastrar porcionamento"}
            </button>
          </div>
        </div>
        <div className="overflow-x-auto rounded-lg border border-surface-03">
          <InventoryTableControls search={search} onSearch={setSearch} sort={sort} onSort={(value) => setSort(value as typeof sort)} options={[{ value: "name", label: "Porção (A-Z)" }, { value: "weight", label: "Peso" }]} />
          <div className="grid min-w-[900px] grid-cols-[1.5fr_1.2fr_.8fr_.8fr_1.4fr_auto] gap-3 bg-surface-01 px-4 py-3 text-xs font-black uppercase tracking-wide text-stone">
            <span>Porção</span>
            <span>Matéria-prima</span>
            <span>Peso</span>
            <span>Uso</span>
            <span>Ações</span>
            <span />
          </div>
          {visibleConfigs.map((c) => (
            <div
              key={c.id}
              className="grid min-w-[900px] grid-cols-[1.5fr_1.2fr_.8fr_.8fr_1.4fr_auto] items-center gap-3 border-t border-surface-03 bg-surface-01 px-4 py-3 text-sm"
            >
              <span className="font-bold text-cream">{c.output_item_name}</span>
              <span className="text-stone">{c.source_item_name}</span>
              <span className="text-stone">
                {formatExactQuantity(c.portion_weight)} {c.unit_symbol || ""}
              </span>
              <span className="text-stone">{portionUsageLabel(c.usage)}</span>
              <div className="flex gap-2">
                <button
                  type="button"
                  className={ghost}
                  disabled={saving}
                  onClick={() => edit(c)}
                >
                  <Pencil size={14} /> Editar
                </button>
                <button
                  type="button"
                  className="rounded-lg p-2 text-stone hover:text-red-300"
                  disabled={saving}
                  onClick={() => void remove(c)}
                >
                  <X size={16} />
                </button>
              </div>
              <span />
            </div>
          ))}
          {!visibleConfigs.length && <p className="px-4 py-10 text-center text-sm text-stone">{configs.length ? "Nenhum porcionamento encontrado." : "Nenhum porcionamento cadastrado."}</p>}
        </div>
      </div>
      {message && <p className="text-emerald-300">{message}</p>}
      {error && <p className="text-red-300">{error}</p>}
    </section>
  );
}
