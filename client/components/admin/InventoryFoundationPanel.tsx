import { useEffect, useMemo, useRef, useState } from "react";
import {
  inventoryApi,
  inventoryFoundationApi as api,
  type InventoryOverview,
  type FoundationUnit,
  type FoundationBalance,
  type FoundationLot,
  type FoundationReservation,
  type FoundationPackaging,
} from "@/lib/api";

const input =
  "w-full rounded border border-surface-03 bg-surface-01 p-2 text-cream";
const button =
  "rounded bg-gold px-3 py-2 font-bold text-black disabled:opacity-50";
const box = "space-y-3 rounded-lg border border-surface-03 bg-surface-02 p-4";
const decimal = (value: string) => value.trim().replace(",", ".");

export default function InventoryFoundationPanel() {
  const [data, setData] = useState<InventoryOverview | null>(null);
  const [units, setUnits] = useState<FoundationUnit[]>([]);
  const [balances, setBalances] = useState<FoundationBalance[]>([]);
  const [lots, setLots] = useState<FoundationLot[]>([]);
  const [reservations, setReservations] = useState<FoundationReservation[]>([]);
  const [packagings, setPackagings] = useState<FoundationPackaging[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [preview, setPreview] = useState("");
  const [item, setItem] = useState("");
  const [location, setLocation] = useState("");
  const [lot, setLot] = useState("");
  const [unit, setUnit] = useState("");
  const [packaging, setPackaging] = useState("");
  const [quantity, setQuantity] = useState("");
  const [measured, setMeasured] = useState("");
  const [measuredUnit, setMeasuredUnit] = useState("");
  const [reason, setReason] = useState("");
  const [kind, setKind] = useState("manual_in");
  const [target, setTarget] = useState("");
  const [cost, setCost] = useState("0");
  const [lotCode, setLotCode] = useState("");
  const [expiry, setExpiry] = useState("");
  const [receivedAt, setReceivedAt] = useState(() => new Date().toISOString());
  const [openingLot, setOpeningLot] = useState<FoundationLot | null>(null);
  const [openingAt, setOpeningAt] = useState(() => new Date().toISOString());
  const [openingRule, setOpeningRule] = useState("");
  const [containerCode, setContainerCode] = useState("");
  const [definition, setDefinition] = useState({
    id: "",
    name: "",
    symbol: "",
    code: "",
    dimension: "mass",
    conversion_factor: "1",
  });
  const [packageForm, setPackageForm] = useState({
    name: "",
    commercial_unit_id: "",
    factor: "",
    variable_weight: false,
  });
  const pending = useRef(new Map<string, string>());
  const busy = useRef(false);
  const mounted = useRef(true);

  async function load() {
    setLoading(true);
    try {
      const [base, u, b, l, r, p] = await Promise.all([
        inventoryApi.overview(),
        api.units(),
        api.reconciliation(),
        api.lots(),
        api.reservations(),
        api.packagings(),
      ]);
      if (!mounted.current) return;
      setData(base);
      setUnits(u.items);
      setBalances(b.items);
      setLots(l.items);
      setReservations(r.items);
      setPackagings(p.items);
    } catch (e) {
      if (mounted.current)
        setError(e instanceof Error ? e.message : "Falha ao carregar estoque.");
    } finally {
      if (mounted.current) setLoading(false);
    }
  }
  useEffect(() => {
    mounted.current = true;
    void load();
    return () => {
      mounted.current = false;
    };
  }, []);

  async function command(
    resource: string,
    body: Record<string, unknown>,
    success: string,
    method = "POST",
  ) {
    if (busy.current) return;
    busy.current = true;
    setSaving(true);
    setError("");
    setMessage("");
    const fingerprint = JSON.stringify([resource, method, body]);
    const key = pending.current.get(fingerprint) ?? crypto.randomUUID();
    pending.current.set(fingerprint, key);
    try {
      await api.command(
        resource,
        {
          ...body,
          ...(resource === "operations" || resource === "reservations"
            ? { business_key: key }
            : {}),
        },
        key,
        method,
      );
      pending.current.delete(fingerprint);
      if (mounted.current) {
        setMessage(success);
        await load();
      }
    } catch (e) {
      if (mounted.current)
        setError(
          e instanceof Error
            ? e.message
            : "Falha ao registrar. Repetir o mesmo comando preserva a identificacao.",
        );
    } finally {
      busy.current = false;
      if (mounted.current) setSaving(false);
    }
  }
  const changeItem = (value: string) => {
    setItem(value);
    setLot("");
    setPackaging("");
    setPreview("");
  };
  const selectedItem = data?.items.find((row) => row.id === item);
  const selectedUnit = units.find((row) => row.id === definition.id);
  const selection = () => ({
    item_id: item,
    unit_id: unit,
    quantity: decimal(quantity),
    packaging_id: packaging || null,
    measured_quantity: measured ? decimal(measured) : null,
    measured_unit_id: measuredUnit || null,
  });
  const itemName = (id: string) =>
    data?.items.find((row) => row.id === id)?.name || id;
  const locationName = (id: string | null) =>
    data?.locations.find((row) => row.id === id)?.name || "Sem local legado";
  const fefoLots = useMemo(() => [...lots].sort((a, b) => {
    const expiryA = a.effective_expires_at || a.expires_on;
    const expiryB = b.effective_expires_at || b.expires_on;
    // Lotes sem validade ficam depois dos lotes com prazo; o servidor continua
    // sendo a autoridade para elegibilidade e alocacao FEFO.
    if (!expiryA && expiryB) return 1;
    if (expiryA && !expiryB) return -1;
    if (expiryA && expiryB && expiryA !== expiryB) return expiryA.localeCompare(expiryB);
    return a.received_at.localeCompare(b.received_at) || a.id.localeCompare(b.id);
  }), [lots]);
  const unitOptions = units.map((row) => (
    <option key={row.id} value={row.id}>
      {row.name} ({row.symbol})
      {row.dimension ? "" : " — classificacao pendente"}
    </option>
  ));
  const locationOptions = data?.locations.map((row) => (
    <option key={row.id} value={row.id}>
      {row.name}
    </option>
  ));

  if (loading && !data)
    return (
      <p role="status" className={box}>
        Carregando saldos e conversoes...
      </p>
    );
  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-xl font-bold text-cream">
          Saldos, lotes e conversoes
        </h2>
        <button
          type="button"
          className={button}
          disabled={saving || loading}
          onClick={() => {
            setError("");
            void load();
          }}
        >
          Atualizar
        </button>
      </div>
      {error && (
        <p
          role="alert"
          className="rounded border border-red-500 p-3 text-red-200"
        >
          {error}
        </p>
      )}
      {message && (
        <p
          role="status"
          className="rounded border border-emerald-500 p-3 text-emerald-200"
        >
          {message}
        </p>
      )}
      <div className={box}>
        <h3 className="font-bold text-cream">Saldos por local e lote</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm text-stone">
            <thead>
              <tr>
                {[
                  "Insumo",
                  "Local / lote",
                  "Fisico",
                  "Utilizavel",
                  "Reservado",
                  "Livre",
                  "Conferencia",
                ].map((h) => (
                  <th key={h} className="p-2">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {balances.map((b) => (
                <tr key={`${b.item_id}:${b.location_id}:${b.lot_id}`}>
                  <td className="p-2">{itemName(b.item_id)}</td>
                  <td className="p-2">
                    {locationName(b.location_id)} /{" "}
                    {lots.find((l) => l.id === b.lot_id)?.lot_code ||
                      "Sem lote legado"}
                  </td>
                  {[b.physical, b.usable, b.reserved, b.available].map(
                    (v, i) => (
                      <td key={i} className="p-2">
                        {v}
                      </td>
                    ),
                  )}
                  <td className="p-2">
                    {b.issues
                      ?.map(
                        (v) =>
                          ({
                            legacy_without_lot: "Saldo legado sem rastreio",
                            negative_physical: "Saldo negativo",
                            reserved_exceeds_usable:
                              "Reserva acima do utilizavel",
                          })[v] || v,
                      )
                      .join("; ") || "Sem divergencia"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!balances.length && (
          <p className="text-stone">Nenhuma movimentacao registrada.</p>
        )}
      </div>
      <div className={box}>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h3 className="font-bold text-cream">Lotes e validade (FEFO)</h3>
            <p className="text-sm text-stone">A ordem usa validade efetiva, recebimento e identificador. O servidor decide quais lotes podem ser consumidos.</p>
          </div>
          <span className="rounded bg-surface-03 px-2 py-1 text-xs text-stone">{fefoLots.length} lote(s)</span>
        </div>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full min-w-[720px] text-left text-sm text-stone">
            <thead><tr>{["Insumo", "Lote / recipiente", "Validade efetiva", "Recebido", "Estado", "Ações"].map((h) => <th key={h} className="p-2">{h}</th>)}</tr></thead>
            <tbody>
              {fefoLots.map((row) => {
                const expired = Boolean((row.effective_expires_at || row.expires_on) && new Date(row.effective_expires_at || `${row.expires_on}T23:59:59Z`).getTime() < Date.now());
                return <tr key={row.id} className="border-t border-surface-03">
                  <td className="p-2">{itemName(row.item_id)}</td>
                  <td className="p-2 font-semibold text-cream">{row.lot_code}{row.container_code ? ` / ${row.container_code}` : ""}</td>
                  <td className={`p-2 ${expired ? "font-bold text-red-300" : ""}`}>{row.effective_expires_at || row.expires_on || "Sem validade"}</td>
                  <td className="p-2">{new Date(row.received_at).toLocaleString("pt-BR")}</td>
                  <td className="p-2">{row.status}{row.opened_at ? ` · aberto ${new Date(row.opened_at).toLocaleDateString("pt-BR")}` : ""}</td>
                  <td className="p-2"><div className="flex flex-wrap gap-2">
                    <button type="button" className={button} disabled={saving || row.status !== "available"} onClick={() => { setOpeningLot(row); setOpeningAt(new Date().toISOString()); setOpeningRule(""); setContainerCode(""); }}>Registrar abertura</button>
                    <button type="button" className="rounded border border-red-500/50 px-2 py-1 text-xs text-red-200 disabled:opacity-50" disabled={saving || row.status === "blocked"} onClick={() => void command(`lots/${row.id}/state`, { expected_version: row.version, status: "blocked", reason: "Bloqueio operacional" }, "Lote bloqueado.")}>Bloquear</button>
                  </div></td>
                </tr>;
              })}
            </tbody>
          </table>
        </div>
        {!fefoLots.length && <p className="mt-3 text-stone">Nenhum lote cadastrado. A validade ausente permanece pendente.</p>}
      </div>
      {openingLot && <form className={box} onSubmit={(event) => { event.preventDefault(); void command(`lots/${openingLot.id}/open`, { expected_version: openingLot.version, opened_at: openingAt, opening_rule: openingRule, container_code: containerCode || null }, "Abertura registrada e validade recalculada.").then(() => setOpeningLot(null)); }}>
        <div className="flex items-center justify-between gap-3"><h3 className="font-bold text-cream">Abrir lote {openingLot.lot_code}</h3><button type="button" className="text-sm text-stone underline" onClick={() => setOpeningLot(null)}>Cancelar</button></div>
        <p className="text-sm text-stone">A abertura é um evento auditável. O servidor aplica a regra sanitária e não amplia a validade do lote.</p>
        <div className="grid gap-3 md:grid-cols-3">
          <label className="text-sm text-stone">Data/hora da abertura<input required className={input} value={openingAt} onChange={(e) => setOpeningAt(e.target.value)} /></label>
          <label className="text-sm text-stone">Regra aplicada<input required className={input} maxLength={120} placeholder="Ex.: 3 dias após abertura" value={openingRule} onChange={(e) => setOpeningRule(e.target.value)} /></label>
          <label className="text-sm text-stone">Recipiente/sub-lote<input className={input} maxLength={120} value={containerCode} onChange={(e) => setContainerCode(e.target.value)} /></label>
        </div>
        <button className={button} disabled={saving || !openingRule.trim()}>Confirmar abertura</button>
      </form>}
      <div className="grid gap-4 xl:grid-cols-2">
        <form
          className={box}
          onSubmit={(e) => {
            e.preventDefault();
            void command(
              definition.id ? `units/${definition.id}` : "units",
              {
                ...definition,
                id: undefined,
                conversion_factor: decimal(definition.conversion_factor),
                expected_version: selectedUnit?.version ?? 0,
              },
              "Unidade confirmada.",
              definition.id ? "PUT" : "POST",
            );
          }}
        >
          <h3 className="font-bold text-cream">Classificar unidade</h3>
          <p className="text-sm text-stone">
            Confirme a dimensao e o fator em relacao a kg, L ou unidade.
            Cadastros antigos permanecem sem conversao ate esta confirmacao.
          </p>
          <select
            aria-label="Unidade a classificar"
            className={input}
            value={definition.id}
            onChange={(e) => {
              const row = units.find((u) => u.id === e.target.value);
              setDefinition(
                row
                  ? {
                      id: row.id,
                      name: row.name,
                      symbol: row.symbol,
                      code: row.code || "",
                      dimension: row.dimension || "mass",
                      conversion_factor: row.conversion_factor || "1",
                    }
                  : {
                      id: "",
                      name: "",
                      symbol: "",
                      code: "",
                      dimension: "mass",
                      conversion_factor: "1",
                    },
              );
            }}
          >
            <option value="">Nova unidade</option>
            {unitOptions}
          </select>
          {(["name", "symbol", "code", "conversion_factor"] as const).map(
            (field) => (
              <label key={field} className="block text-sm text-stone">
                {
                  {
                    name: "Nome",
                    symbol: "Sigla",
                    code: "Codigo unico",
                    conversion_factor: "Fator confirmado",
                  }[field]
                }
                <input
                  required
                  className={input}
                  value={definition[field]}
                  onChange={(e) =>
                    setDefinition({ ...definition, [field]: e.target.value })
                  }
                />
              </label>
            ),
          )}
          <select
            aria-label="Dimensao"
            className={input}
            value={definition.dimension}
            onChange={(e) =>
              setDefinition({ ...definition, dimension: e.target.value })
            }
          >
            <option value="mass">Massa (kg)</option>
            <option value="volume">Volume (L)</option>
            <option value="count">Contagem (unidade)</option>
          </select>
          <button className={button} disabled={saving}>
            Confirmar unidade
          </button>
        </form>
        <div className={box}>
          <h3 className="font-bold text-cream">
            Selecao para conversao e movimentos
          </h3>
          <label className="block text-sm text-stone">
            Insumo
            <select
              className={input}
              value={item}
              onChange={(e) => changeItem(e.target.value)}
            >
              <option value="">Selecione</option>
              {data?.items.map((row) => (
                <option key={row.id} value={row.id}>
                  {row.name}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm text-stone">
            Local
            <select
              className={input}
              value={location}
              onChange={(e) => {
                setLocation(e.target.value);
                setLot("");
              }}
            >
              <option value="">Selecione</option>
              {locationOptions}
            </select>
          </label>
          <label className="block text-sm text-stone">
            Lote
            <select
              className={input}
              value={lot}
              onChange={(e) => setLot(e.target.value)}
            >
              <option value="">Sem lote (saldo legado)</option>
              {lots
                .filter((l) => l.item_id === item && l.location_id === location)
                .map((l) => (
                  <option key={l.id} value={l.id}>
                    {l.lot_code} — {l.status}
                  </option>
                ))}
            </select>
          </label>
          <label className="block text-sm text-stone">
            Unidade comercial
            <select
              className={input}
              value={unit}
              onChange={(e) => setUnit(e.target.value)}
            >
              <option value="">Selecione</option>
              {unitOptions}
            </select>
          </label>
          <label className="block text-sm text-stone">
            Embalagem
            <select
              className={input}
              value={packaging}
              onChange={(e) => setPackaging(e.target.value)}
            >
              <option value="">Conversao dimensional</option>
              {packagings
                .filter((p) => p.item_id === item)
                .map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                    {p.variable_weight ? " — peso variavel" : ""}
                  </option>
                ))}
            </select>
          </label>
          <label className="block text-sm text-stone">
            Quantidade
            <input
              className={input}
              inputMode="decimal"
              value={quantity}
              onChange={(e) => setQuantity(e.target.value)}
            />
          </label>
          <label className="block text-sm text-stone">
            Peso aferido (embalagem variavel)
            <input
              className={input}
              inputMode="decimal"
              value={measured}
              onChange={(e) => setMeasured(e.target.value)}
            />
          </label>
          <select
            aria-label="Unidade aferida"
            className={input}
            value={measuredUnit}
            onChange={(e) => setMeasuredUnit(e.target.value)}
          >
            <option value="">Unidade do peso aferido</option>
            {unitOptions}
          </select>
          <button
            type="button"
            className={button}
            disabled={saving || !item || !unit || !quantity}
            onClick={async () => {
              setError("");
              try {
                const result = await api.preview(selection());
                setPreview(
                  `${result.quantity} ${units.find((u) => u.id === result.unit_id)?.symbol || result.unit_id}`,
                );
              } catch (e) {
                setError(
                  e instanceof Error ? e.message : "Conversao indisponivel.",
                );
              }
            }}
          >
            Conferir conversao
          </button>
          {preview && (
            <p role="status" className="text-cream">
              Quantidade normalizada: {preview}
            </p>
          )}
        </div>
        <form
          className={box}
          onSubmit={(e) => {
            e.preventDefault();
            void command(
              "lots",
              {
                expected_version: 0,
                item_id: item,
                location_id: location,
                lot_code: lotCode,
                received_at: receivedAt,
                expires_on: expiry || null,
              },
              "Lote registrado. A movimentacao e uma confirmacao separada.",
            );
          }}
        >
          <h3 className="font-bold text-cream">Identificar lote</h3>
          <p className="text-sm text-stone">
            Usa insumo e local selecionados. Validade ausente deixa o lote
            indisponivel para uso.
          </p>
          <label className="block text-sm text-stone">
            Recebimento (data/hora com fuso)
            <input
              required
              className={input}
              value={receivedAt}
              onChange={(e) => setReceivedAt(e.target.value)}
            />
          </label>
          <label className="block text-sm text-stone">
            Codigo do lote
            <input
              required
              className={input}
              value={lotCode}
              onChange={(e) => setLotCode(e.target.value)}
            />
          </label>
          <label className="block text-sm text-stone">
            Validade original
            <input
              className={input}
              type="date"
              value={expiry}
              onChange={(e) => setExpiry(e.target.value)}
            />
          </label>
          <button className={button} disabled={saving || !item || !location}>
            Registrar lote
          </button>
        </form>
        <form
          className={box}
          onSubmit={(e) => {
            e.preventDefault();
            void command(
              "packagings",
              {
                expected_version: 0,
                item_id: item,
                name: packageForm.name,
                commercial_unit_id: packageForm.commercial_unit_id,
                base_unit_id: selectedItem?.unit_id,
                variable_weight: packageForm.variable_weight,
                factor: packageForm.variable_weight
                  ? null
                  : decimal(packageForm.factor),
              },
              "Embalagem confirmada.",
            );
          }}
        >
          <h3 className="font-bold text-cream">Embalagem por insumo</h3>
          <label className="block text-sm text-stone">
            Nome
            <input
              required
              className={input}
              value={packageForm.name}
              onChange={(e) =>
                setPackageForm({ ...packageForm, name: e.target.value })
              }
            />
          </label>
          <select
            aria-label="Unidade da embalagem"
            required
            className={input}
            value={packageForm.commercial_unit_id}
            onChange={(e) =>
              setPackageForm({
                ...packageForm,
                commercial_unit_id: e.target.value,
              })
            }
          >
            <option value="">Unidade comercial</option>
            {unitOptions}
          </select>
          <label className="block text-sm text-stone">
            <input
              type="checkbox"
              checked={packageForm.variable_weight}
              onChange={(e) =>
                setPackageForm({
                  ...packageForm,
                  variable_weight: e.target.checked,
                })
              }
            />{" "}
            Peso variavel
          </label>
          {!packageForm.variable_weight && (
            <label className="block text-sm text-stone">
              Quantidade base por embalagem
              <input
                required
                className={input}
                inputMode="decimal"
                value={packageForm.factor}
                onChange={(e) =>
                  setPackageForm({ ...packageForm, factor: e.target.value })
                }
              />
            </label>
          )}
          <button
            className={button}
            disabled={saving || !selectedItem?.unit_id}
          >
            Confirmar embalagem
          </button>
        </form>
        <div className={box}>
          <h3 className="font-bold text-cream">
            Registrar movimento ou reserva
          </h3>
          <p className="text-sm text-stone">
            Conferir insumo, local, lote e quantidade acima. O servidor valida
            conversao, saldo e permissoes.
          </p>
          <select
            aria-label="Tipo de movimento"
            className={input}
            value={kind}
            onChange={(e) => setKind(e.target.value)}
          >
            <option value="manual_in">Entrada</option>
            <option value="manual_out">Saida</option>
            <option value="transfer">Transferencia</option>
            <option value="loss">Perda</option>
            <option value="adjustment_in">Ajuste positivo</option>
            <option value="adjustment_out">Ajuste negativo</option>
          </select>
          {kind === "transfer" && (
            <select
              aria-label="Local destino"
              className={input}
              value={target}
              onChange={(e) => setTarget(e.target.value)}
            >
              <option value="">Destino</option>
              {locationOptions}
            </select>
          )}
          <label className="block text-sm text-stone">
            Custo unitario na unidade base
            <input
              className={input}
              inputMode="decimal"
              value={cost}
              onChange={(e) => setCost(e.target.value)}
            />
          </label>
          <label className="block text-sm text-stone">
            Justificativa
            <input
              className={input}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          </label>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              className={button}
              disabled={
                saving || !item || !location || !unit || !quantity || !reason
              }
              onClick={() =>
                void command(
                  "operations",
                  {
                    expected_version: 0,
                    kind,
                    reason,
                    lines: [
                      {
                        ...selection(),
                        location_id: location,
                        lot_id: lot || null,
                        target_location_id: kind === "transfer" ? target : null,
                        unit_cost: decimal(cost),
                      },
                    ],
                  },
                  "Movimento registrado.",
                )
              }
            >
              Confirmar movimento
            </button>
            <button
              type="button"
              className={button}
              disabled={
                saving ||
                !selectedItem?.unit_id ||
                !location ||
                !quantity ||
                !reason
              }
              onClick={async () => {
                try {
                  const converted = await api.preview(selection());
                  await command(
                    "reservations",
                    {
                      expected_version: 0,
                      item_id: item,
                      location_id: location,
                      lot_id: lot || null,
                      quantity: converted.quantity,
                      unit_id: converted.unit_id,
                      source_type: "manual",
                      source_id: item,
                      reason,
                    },
                    "Reserva registrada sem consumo.",
                  );
                } catch (e) {
                  setError(
                    e instanceof Error
                      ? e.message
                      : "Nao foi possivel reservar.",
                  );
                }
              }}
            >
              Reservar quantidade
            </button>
          </div>
        </div>
        <div className={box}>
          <h3 className="font-bold text-cream">Reservas</h3>
          {!reservations.length && (
            <p className="text-stone">Nenhuma reserva registrada.</p>
          )}
          {reservations.map((r) => (
            <div
              key={r.id}
              className="flex flex-wrap items-center justify-between gap-2 border-t border-surface-03 py-2 text-sm text-stone"
            >
              <span>
                {itemName(r.item_id)} — {r.quantity} — {r.status}
              </span>
              {r.status === "active" && (
                <button
                  className={button}
                  disabled={saving || !reason}
                  onClick={() =>
                    void command(
                      `reservations/${r.id}/release`,
                      { expected_version: r.version, reason },
                      "Reserva liberada.",
                    )
                  }
                >
                  Liberar reserva
                </button>
              )}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
