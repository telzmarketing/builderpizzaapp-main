import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Camera,
  Check,
  ClipboardCheck,
  Loader2,
  RefreshCw,
  Search,
  UserRound,
  WifiOff,
} from "lucide-react";
import KdsBrandLogo from "@/components/kds/KdsBrandLogo";
import KdsSessionActions from "@/components/kds/KdsSessionActions";
import {
  kdsAuditoriaApi,
  resolveOptimizedAssetUrl,
  uploadApi,
  type KdsAuditoriaEvidence,
  type KdsAuditoriaOrder,
  type KdsAuditoriaQueueEntry,
} from "@/lib/api";
import { orderDisplayCode } from "@/lib/orderIdentity";

type OriginFilter = "all" | "own" | "ifood" | "99food" | "keeta";
const ORIGINS: Array<{ value: OriginFilter; label: string }> = [
  { value: "all", label: "Todas" },
  { value: "own", label: "Loja própria" },
  { value: "ifood", label: "iFood" },
  { value: "99food", label: "99Food" },
  { value: "keeta", label: "Keeta" },
];

export function normalizeAuditoriaOrigin(
  origin?: string | null,
): Exclude<OriginFilter, "all"> | "other" {
  const value = (origin ?? "").toLowerCase().replace(/[ _-]/g, "");
  if (["own", "loja", "lojaprópria", "propria", "store"].includes(value))
    return "own";
  if (value.includes("ifood")) return "ifood";
  if (value.includes("99food") || value === "99") return "99food";
  if (value.includes("keeta")) return "keeta";
  return "other";
}

export function filterAuditoriaOrders(
  orders: KdsAuditoriaQueueEntry[],
  query: string,
  origin: OriginFilter,
) {
  const needle = query.trim().toLowerCase();
  return orders.filter((order) => {
    if (
      origin !== "all" &&
      normalizeAuditoriaOrigin(order.order_origin) !== origin
    )
      return false;
    if (!needle) return true;
    return [order.order_id, order.order_code, order.order_origin]
      .filter(Boolean)
      .some((value) => String(value).toLowerCase().includes(needle));
  });
}

function errorMessage(error: unknown) {
  return error instanceof Error
    ? error.message
    : "Não foi possível atualizar a auditoria.";
}
function displayOrder(order: { order_id: string; order_code?: string | null }) {
  return orderDisplayCode({ id: order.order_id, order_code: order.order_code });
}
function originLabel(origin?: string | null) {
  return (
    ORIGINS.find((item) => item.value === normalizeAuditoriaOrigin(origin))
      ?.label ?? "Outro canal"
  );
}

export default function KdsAuditoria() {
  const [queue, setQueue] = useState<KdsAuditoriaQueueEntry[]>([]);
  const [selectedQueue, setSelectedQueue] =
    useState<KdsAuditoriaQueueEntry | null>(null);
  const [selected, setSelected] = useState<KdsAuditoriaOrder | null>(null);
  const [query, setQuery] = useState("");
  const [origin, setOrigin] = useState<OriginFilter>("all");
  const [evidence, setEvidence] = useState<KdsAuditoriaEvidence[]>([]);
  const [assetId, setAssetId] = useState("");
  const [uploadedUrl, setUploadedUrl] = useState("");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [starting, setStarting] = useState(false);
  const [actionKey, setActionKey] = useState<string | null>(null);
  const [handoffing, setHandoffing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);

  const loadQueue = useCallback(async (manual = false) => {
    if (manual) setRefreshing(true);
    try {
      setQueue(await kdsAuditoriaApi.queue());
      setError(null);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);
  useEffect(() => {
    void loadQueue();
    const timer = window.setInterval(() => void loadQueue(), 15_000);
    return () => window.clearInterval(timer);
  }, [loadQueue]);

  const visibleQueue = useMemo(
    () => filterAuditoriaOrders(queue, query, origin),
    [queue, query, origin],
  );
  const allItemsConfirmed =
    Boolean(selected?.audit_items.length) &&
    selected!.audit_items.every((item) => item.confirmed);
  const allVolumesConfirmed =
    Boolean(selected?.audit_volumes.length) &&
    selected!.audit_volumes.every((volume) => volume.confirmed);
  const canHandoff = Boolean(
    selected?.audit_id &&
      allItemsConfirmed &&
      allVolumesConfirmed &&
      evidence.length > 0 &&
      !handoffing,
  );
  const refreshDetail = async (orderId: string) => {
    const detail = await kdsAuditoriaApi.detail(orderId);
    setSelected(detail);
    setEvidence(detail.audit_evidence ?? []);
  };

  const openOrder = async (entry: KdsAuditoriaQueueEntry) => {
    setSelectedQueue(entry);
    setSelected(null);
    setEvidence([]);
    setAssetId("");
    setUploadedUrl("");
    setFeedback(null);
    setError(null);
    setStarting(true);
    try {
      let detail = await kdsAuditoriaApi.detail(entry.order_id);
      if (!detail.audit_id)
        detail = await kdsAuditoriaApi.start(entry.order_id);
      setSelected(detail);
      setEvidence(detail.audit_evidence ?? []);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setStarting(false);
    }
  };
  const confirmItem = async (itemId: string, quantity: number) => {
    if (!selected?.audit_id) return;
    setActionKey(`item:${itemId}`);
    setFeedback(null);
    try {
      await kdsAuditoriaApi.confirmItem(selected.audit_id, itemId, quantity);
      await refreshDetail(selected.order_id);
      setFeedback("Item confirmado no servidor.");
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setActionKey(null);
    }
  };
  const confirmVolume = async (volumeId: string) => {
    if (!selected?.audit_id) return;
    setActionKey(`volume:${volumeId}`);
    setFeedback(null);
    try {
      await kdsAuditoriaApi.confirmVolume(selected.audit_id, volumeId);
      await refreshDetail(selected.order_id);
      setFeedback("Volume confirmado no servidor.");
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setActionKey(null);
    }
  };
  const registerExistingEvidence = async () => {
    if (!selected?.audit_id || !assetId.trim()) return;
    setActionKey("evidence");
    setFeedback(null);
    try {
      const saved = await kdsAuditoriaApi.addEvidence(selected.audit_id, {
        asset_id: assetId.trim(),
        evidence_type: "handoff",
        captured_at: new Date().toISOString(),
        metadata_json: JSON.stringify({ source: "private-upload" }),
      });
      setEvidence((current) => [...current, saved]);
      await refreshDetail(selected.order_id);
      setAssetId("");
      setFeedback("Evidência privada vinculada à auditoria.");
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setActionKey(null);
    }
  };
  const captureEvidence = async (file: File | undefined) => {
    if (!file || !selected?.audit_id) return;
    setActionKey("capture");
    setFeedback(null);
    setError(null);
    setUploadedUrl("");
    try {
      const uploaded = await uploadApi.uploadAsset(file, "private");
      if (!uploaded.asset_id) {
        setUploadedUrl(uploaded.url);
        setFeedback(
          "Upload privado concluído, mas o backend não retornou asset_id. Use o fallback manual abaixo para vincular a evidência.",
        );
        return;
      }
      const saved = await kdsAuditoriaApi.addEvidence(selected.audit_id, {
        asset_id: uploaded.asset_id,
        evidence_type: "handoff",
        captured_at: new Date().toISOString(),
        metadata_json: JSON.stringify({
          source: "camera-private-upload",
          url: uploaded.url,
        }),
      });
      setEvidence((current) => [...current, saved]);
      await refreshDetail(selected.order_id);
      setFeedback("Foto enviada como privada e vinculada à auditoria.");
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setActionKey(null);
    }
  };
  const handoff = async () => {
    if (!selected?.audit_id || !canHandoff) return;
    setHandoffing(true);
    setFeedback(null);
    try {
      await kdsAuditoriaApi.handoff(
        selected.audit_id,
        `kds-auditoria-${selected.audit_id}-${Date.now()}`,
      );
      setQueue((current) =>
        current.filter((item) => item.order_id !== selected.order_id),
      );
      setSelected(null);
      setSelectedQueue(null);
      setFeedback("Entrega ao motoboy confirmada no servidor.");
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setHandoffing(false);
    }
  };

  return (
    <main className="min-h-screen bg-surface-00 px-3 py-3 text-cream sm:px-5 sm:py-5">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-4">
        <header className="sticky top-0 z-20 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-surface-03 bg-surface-02 p-3 shadow-soft sm:p-4">
          <div className="flex min-w-0 items-center gap-3">
            <KdsBrandLogo
              className="h-11 w-16 object-contain"
              fallback={<ClipboardCheck className="text-gold" />}
            />
            <div>
              <p className="text-xs font-black uppercase tracking-widest text-gold">
                Gran Torino · Operações
              </p>
              <h1 className="text-xl font-black sm:text-2xl">KDS Auditoria</h1>
              <p className="text-xs text-stone">
                Conferência final antes da transferência
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="hidden items-center gap-1 rounded-full border border-emerald-400/30 px-3 py-2 text-xs text-emerald-200 sm:flex">
              <Check size={14} /> Sessão ativa
            </span>
            <KdsSessionActions />
          </div>
        </header>
        <section className="grid gap-3 rounded-2xl border border-surface-03 bg-surface-02 p-3 sm:grid-cols-[1fr_auto] sm:p-4">
          <label className="flex min-h-11 items-center gap-2 rounded-xl border border-surface-03 bg-surface-01 px-3">
            <Search size={17} className="text-stone" />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Pesquisar pedido ou origem"
              className="min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-stone"
            />
          </label>
          <div className="flex flex-wrap gap-2">
            {ORIGINS.map((item) => (
              <button
                key={item.value}
                type="button"
                onClick={() => setOrigin(item.value)}
                className={`min-h-11 rounded-xl border px-3 text-xs font-bold ${origin === item.value ? "border-gold bg-gold/15 text-gold" : "border-surface-03 bg-surface-01 text-stone"}`}
              >
                {item.label}
              </button>
            ))}
            <button
              type="button"
              onClick={() => void loadQueue(true)}
              disabled={refreshing}
              className="inline-flex min-h-11 items-center gap-2 rounded-xl border border-surface-03 bg-surface-01 px-3 text-xs font-bold text-cream"
            >
              <RefreshCw
                size={15}
                className={refreshing ? "animate-spin" : ""}
              />{" "}
              Atualizar
            </button>
          </div>
        </section>
        {error && (
          <div
            role="alert"
            className="flex items-center gap-2 rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200"
          >
            <WifiOff size={17} /> {error}
          </div>
        )}
        {feedback && (
          <div
            role="status"
            className="rounded-xl border border-emerald-400/30 bg-emerald-400/10 p-3 text-sm text-emerald-200"
          >
            {feedback}
          </div>
        )}
        {loading ? (
          <div className="flex min-h-48 items-center justify-center gap-2 text-stone">
            <Loader2 className="animate-spin text-gold" /> Carregando fila de
            auditoria...
          </div>
        ) : visibleQueue.length === 0 ? (
          <div className="flex min-h-48 flex-col items-center justify-center rounded-2xl border border-dashed border-surface-03 bg-surface-02 p-6 text-center text-stone">
            <ClipboardCheck size={36} className="mb-2 text-emerald-300" />
            <p className="font-bold">Nenhum pedido aguardando auditoria</p>
          </div>
        ) : (
          <div className="grid gap-3 lg:grid-cols-[minmax(18rem,0.8fr)_minmax(0,1.4fr)]">
            <section className="space-y-2" aria-label="Fila de pedidos">
              {visibleQueue.map((entry) => (
                <button
                  key={entry.order_id}
                  type="button"
                  onClick={() => void openOrder(entry)}
                  className={`w-full rounded-2xl border p-4 text-left ${selectedQueue?.order_id === entry.order_id ? "border-gold bg-gold/10" : "border-surface-03 bg-surface-02"}`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <strong className="text-lg">#{displayOrder(entry)}</strong>
                    <span className="rounded-full bg-surface-01 px-2 py-1 text-[10px] font-black uppercase text-gold">
                      {originLabel(entry.order_origin)}
                    </span>
                  </div>
                  <p className="mt-3 text-xs font-bold text-amber-200">
                    {entry.delivery_person_id
                      ? `Entregador vinculado: ${entry.delivery_person_id}`
                      : "Entregador será resolvido pelo fluxo existente"}
                  </p>
                </button>
              ))}
            </section>
            {starting ? (
              <div className="flex min-h-64 items-center justify-center gap-2 rounded-2xl border border-surface-03 bg-surface-02 text-stone">
                <Loader2 className="animate-spin text-gold" /> Iniciando
                auditoria...
              </div>
            ) : selected ? (
              <section
                className="space-y-4 rounded-2xl border border-surface-03 bg-surface-02 p-4"
                aria-label="Detalhe da auditoria"
              >
                <div>
                  <p className="text-xs font-black uppercase tracking-widest text-gold">
                    Auditoria iniciada
                  </p>
                  <h2 className="text-2xl font-black">
                    #
                    {displayOrder({
                      order_id: selected.order_id,
                      order_code: selected.order_code,
                    })}
                  </h2>
                  <p className="text-sm text-stone">
                    {originLabel(selected.order_origin)} · Status:{" "}
                    {selected.audit_status || "in_progress"}
                  </p>
                </div>
                <div>
                  <h3 className="mb-2 font-black">Itens conferidos</h3>
                  <div className="space-y-2">
                    {selected.items.map((item) => {
                      const confirmation = selected.audit_items.find(
                        (row) => row.order_item_id === item.id,
                      );
                      const busy = actionKey === `item:${item.id}`;
                      return (
                        <label
                          key={item.id}
                          className="flex min-h-12 items-center gap-3 rounded-xl border border-surface-03 bg-surface-01 p-3"
                        >
                          <input
                            type="checkbox"
                            checked={Boolean(confirmation?.confirmed)}
                            disabled={busy || Boolean(confirmation?.confirmed)}
                            onChange={() =>
                              void confirmItem(item.id, item.quantity)
                            }
                            className="h-5 w-5 accent-amber-400"
                          />
                          <span className="text-sm font-semibold">
                            <strong className="mr-2 text-gold">
                              {item.quantity}x
                            </strong>
                            {item.product_name || `Produto ${item.product_id}`}
                            {item.selected_size
                              ? ` · ${item.selected_size}`
                              : ""}
                          </span>
                          {busy && (
                            <Loader2
                              size={16}
                              className="ml-auto animate-spin"
                            />
                          )}
                        </label>
                      );
                    })}
                  </div>
                </div>
                <div>
                  <h3 className="mb-2 font-black">Volumes</h3>
                  <div className="grid gap-2 sm:grid-cols-2">
                    {selected.audit_volumes.map((volume) => {
                      const busy = actionKey === `volume:${volume.id}`;
                      return (
                        <label
                          key={volume.id}
                          className="flex min-h-12 items-center gap-3 rounded-xl border border-surface-03 bg-surface-01 p-3"
                        >
                          <input
                            type="checkbox"
                            checked={volume.confirmed}
                            disabled={busy || volume.confirmed}
                            onChange={() => void confirmVolume(volume.id)}
                            className="h-5 w-5 accent-amber-400"
                          />
                          <span className="text-sm font-bold">
                            Volume {volume.sequence}
                          </span>
                          {busy && (
                            <Loader2
                              size={16}
                              className="ml-auto animate-spin"
                            />
                          )}
                        </label>
                      );
                    })}
                  </div>
                </div>
                <div className="rounded-xl border border-amber-300/30 bg-amber-300/10 p-3">
                  <h3 className="font-black text-amber-100">
                    Evidência privada obrigatória
                  </h3>
                  <p className="mt-1 text-xs text-amber-100/80">
                    Capture pela câmera: o arquivo será enviado com visibilidade
                    privada e vinculado automaticamente quando houver{" "}
                    <code>asset_id</code>.
                  </p>
                  <label className="mt-3 inline-flex min-h-12 cursor-pointer items-center justify-center gap-2 rounded-xl bg-amber-300 px-4 font-black text-slate-950">
                    <Camera size={17} />
                    {actionKey === "capture"
                      ? "Enviando..."
                      : "Capturar e registrar foto"}
                    <input
                      type="file"
                      accept="image/*"
                      capture="environment"
                      className="sr-only"
                      disabled={actionKey === "capture"}
                      onChange={(event) => {
                        void captureEvidence(event.target.files?.[0]);
                        event.currentTarget.value = "";
                      }}
                    />
                  </label>
                  {uploadedUrl && (
                    <p className="mt-3 text-xs text-amber-100">
                      Upload privado criado em{" "}
                      <code className="break-all">{uploadedUrl}</code>, mas sem{" "}
                      <code>asset_id</code>. Fallback de vinculação:
                    </p>
                  )}
                  <div className="mt-3 flex flex-col gap-2 sm:flex-row">
                    <input
                      value={assetId}
                      onChange={(event) => setAssetId(event.target.value)}
                      placeholder="asset_id do upload privado (fallback)"
                      className="min-h-11 min-w-0 flex-1 rounded-xl border border-surface-03 bg-surface-01 px-3 text-sm text-cream placeholder:text-stone"
                    />
                    <button
                      type="button"
                      disabled={!assetId.trim() || actionKey === "evidence"}
                      onClick={() => void registerExistingEvidence()}
                      className="min-h-11 rounded-xl bg-amber-300 px-4 text-sm font-black text-slate-950 disabled:opacity-40"
                    >
                      {actionKey === "evidence"
                        ? "Vinculando..."
                        : "Vincular fallback"}
                    </button>
                  </div>
                  <p className="mt-2 text-xs text-stone">
                    {evidence.length} evidência(s) vinculada(s) nesta sessão.
                  </p>
                </div>
                {evidence.length > 0 && (
                  <section
                    className="mt-4 border-t border-amber-200/20 pt-3"
                    aria-label="Histórico de evidências"
                  >
                    <div className="mb-3 flex items-center justify-between gap-2">
                      <h4 className="font-black text-amber-100">
                        Histórico de fotos
                      </h4>
                      <span className="text-xs text-amber-100/70">
                        {evidence.length} original(is)
                      </span>
                    </div>
                    <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                      {evidence.map((item) => (
                        <a
                          key={item.evidence_id}
                          href={
                            item.url
                              ? resolveOptimizedAssetUrl(item.url, 640)
                              : undefined
                          }
                          target="_blank"
                          rel="noreferrer"
                          className="group overflow-hidden rounded-lg border border-amber-200/20 bg-surface-01"
                        >
                          <div className="aspect-square overflow-hidden bg-surface-00">
                            {item.url ? (
                              <img
                                src={resolveOptimizedAssetUrl(item.url, 320)}
                                alt={
                                  item.original_filename || "Evidência original"
                                }
                                className="h-full w-full object-cover transition-transform group-hover:scale-105"
                                loading="lazy"
                              />
                            ) : (
                              <div className="flex h-full items-center justify-center px-2 text-center text-[11px] text-stone">
                                Asset sem URL privada
                              </div>
                            )}
                          </div>
                          <div className="p-2 text-[10px] text-stone">
                            <p className="truncate text-cream">
                              {item.original_filename || item.asset_id}
                            </p>
                            <p>
                              {item.processing_status === "not_processed"
                                ? "Detecção ainda não processada"
                                : item.processing_status}
                            </p>
                            <p>
                              {item.captured_at
                                ? new Date(item.captured_at).toLocaleString(
                                    "pt-BR",
                                  )
                                : "Data não informada"}
                            </p>
                          </div>
                        </a>
                      ))}
                    </div>
                  </section>
                )}
                <button
                  type="button"
                  disabled={!canHandoff}
                  onClick={() => void handoff()}
                  className="flex min-h-14 w-full items-center justify-center gap-2 rounded-xl bg-emerald-500 px-4 text-base font-black text-slate-950 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  <UserRound size={18} />
                  {handoffing
                    ? "Confirmando no servidor..."
                    : "Confirmar entrega ao motoboy"}
                </button>
                {!canHandoff && (
                  <p className="text-center text-xs text-stone">
                    Confirme todos os itens e volumes e vincule uma evidência
                    privada antes do handoff.
                  </p>
                )}
              </section>
            ) : (
              <div className="flex min-h-64 items-center justify-center rounded-2xl border border-dashed border-surface-03 bg-surface-02 p-6 text-center text-stone">
                Selecione um pedido para iniciar a auditoria.
              </div>
            )}
          </div>
        )}
      </div>
    </main>
  );
}
