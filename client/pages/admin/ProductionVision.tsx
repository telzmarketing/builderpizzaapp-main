import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type FormEvent,
} from "react";
import {
  Activity,
  AlertTriangle,
  Camera,
  CheckCircle2,
  Clock3,
  Database,
  Eye,
  History,
  Loader2,
  MapPin,
  RefreshCw,
  Save,
  Search,
  Settings,
  ShieldCheck,
  Sparkles,
  Video,
  Wifi,
  XCircle,
} from "lucide-react";
import {
  AdminPageContent,
  AdminPageHeader,
  AdminPageTabs,
  type AdminPageTab,
} from "@/components/admin/AdminPageChrome";
import {
  productionVisionApi,
  type ProductionVisionCamera,
  type ProductionVisionCameraInput,
  type ProductionVisionDashboard,
  type ProductionVisionStatus,
} from "@/lib/productionVision";
import { productionVisionStationOptions } from "@/lib/kdsStations";

type Section =
  | "dashboard"
  | "cameras"
  | "stations"
  | "monitoring"
  | "history"
  | "order"
  | "intelligence"
  | "settings"
  | "retention"
  | "diagnostics";
const sections: AdminPageTab<Section>[] = [
  { id: "dashboard", label: "Dashboard", icon: Activity },
  { id: "cameras", label: "Câmeras", icon: Camera },
  { id: "stations", label: "Estações/Zonas", icon: MapPin },
  { id: "monitoring", label: "Monitoramento", icon: Video },
  { id: "history", label: "Histórico", icon: History },
  { id: "order", label: "Visão por Pedido", icon: Search },
  { id: "intelligence", label: "Inteligência Visual", icon: Sparkles },
  { id: "settings", label: "Configurações", icon: Settings },
  { id: "retention", label: "Retenção", icon: Clock3 },
  { id: "diagnostics", label: "Diagnósticos", icon: ShieldCheck },
];
const inputClass =
  "w-full rounded-lg border border-surface-03 bg-surface-01 px-3 py-2 text-sm text-cream outline-none focus:border-gold";
const buttonClass =
  "inline-flex items-center justify-center gap-2 rounded-lg bg-gold px-3 py-2 text-sm font-black text-black transition hover:bg-gold/90 disabled:cursor-not-allowed disabled:opacity-60";
const ghostClass =
  "inline-flex items-center justify-center gap-2 rounded-lg border border-surface-03 px-3 py-2 text-sm font-bold text-stone transition hover:bg-surface-03 hover:text-cream disabled:opacity-60";
const emptyText = "Nenhum dado disponível para esta área no contrato atual.";

function text(value: unknown, fallback = "Não informado") {
  return value === null || value === undefined || value === ""
    ? fallback
    : String(value);
}
function number(value: unknown) {
  return typeof value === "number" && Number.isFinite(value)
    ? value.toLocaleString("pt-BR")
    : "0";
}
function date(value?: string | null) {
  if (!value) return "Sem horário";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime())
    ? value
    : parsed.toLocaleString("pt-BR");
}
function statusLabel(status?: ProductionVisionStatus | null) {
  return (
    (
      {
        online: "Online",
        active: "Ativa",
        inactive: "Inativa",
        offline: "Offline",
        completed: "Concluída",
        complete: "Concluída",
        partial: "Parcial",
        failed: "Falha",
      } as Record<string, string>
    )[status ?? ""] ?? text(status, "Sem status")
  );
}
function statusClass(status?: ProductionVisionStatus | null) {
  return ["online", "active", "completed", "complete"].includes(status ?? "")
    ? "text-emerald-300"
    : ["offline", "inactive", "failed"].includes(status ?? "")
      ? "text-red-300"
      : "text-amber-300";
}
function Card({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section
      className={`rounded-2xl border border-surface-03 bg-surface-02 p-4 ${className}`}
    >
      {children}
    </section>
  );
}
function Metric({
  label,
  value,
  icon: Icon,
}: {
  label: string;
  value: unknown;
  icon: typeof Camera;
}) {
  return (
    <Card>
      <div className="flex items-center justify-between text-sm text-stone">
        <span>{label}</span>
        <Icon size={17} className="text-gold" />
      </div>
      <p className="mt-3 text-3xl font-black text-cream">{number(value)}</p>
    </Card>
  );
}
function Empty({ message = emptyText }: { message?: string }) {
  return (
    <p className="rounded-xl border border-dashed border-surface-03 p-5 text-sm text-stone">
      {message}
    </p>
  );
}

function CameraForm({
  stations,
  camera,
  onSaved,
}: {
  stations: ProductionVisionDashboard["stations"];
  camera?: ProductionVisionCamera;
  onSaved: () => Promise<void>;
}) {
  const stationOptions = productionVisionStationOptions(stations);
  const [form, setForm] = useState<ProductionVisionCameraInput>({
    name: camera?.name ?? "",
    identifier: camera?.identifier ?? "",
    station_id: camera?.station_id ?? stationOptions[0]?.id ?? "",
    manufacturer: camera?.manufacturer ?? "",
    model: camera?.model ?? "",
    ip_address: camera?.ip_address ?? "",
    port: camera?.port ?? 554,
    protocol: camera?.protocol ?? "rtsp",
    resolution: camera?.resolution ?? "",
    orientation: camera?.orientation ?? "",
    installation_height_cm: camera?.installation_height_cm ?? null,
    status: camera?.status === "active" ? "active" : "inactive",
    password: "",
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  function update<K extends keyof ProductionVisionCameraInput>(
    key: K,
    value: ProductionVisionCameraInput[K],
  ) {
    setForm((current) => ({ ...current, [key]: value }));
  }
  async function submit(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      await productionVisionApi.saveCamera(
        {
          ...form,
          port: form.port ? Number(form.port) : null,
          installation_height_cm: form.installation_height_cm
            ? Number(form.installation_height_cm)
            : null,
        },
        camera?.id,
      );
      await onSaved();
      if (!camera)
        setForm((current) => ({
          ...current,
          name: "",
          identifier: "",
          password: "",
        }));
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Não foi possível salvar a câmera.",
      );
    } finally {
      setSaving(false);
    }
  }
  return (
    <form
      onSubmit={submit}
      className="space-y-3 rounded-xl border border-surface-03 bg-surface-01 p-4"
    >
      <div className="grid gap-3 md:grid-cols-2">
        <label className="text-xs font-bold text-stone">
          Nome
          <input
            required
            className={inputClass}
            value={form.name}
            onChange={(event) => update("name", event.target.value)}
          />
        </label>
        <label className="text-xs font-bold text-stone">
          Identificador
          <input
            required
            className={inputClass}
            value={form.identifier}
            onChange={(event) => update("identifier", event.target.value)}
          />
        </label>
        <label className="text-xs font-bold text-stone">
          Estação
          <select
            required
            className={inputClass}
            value={form.station_id}
            onChange={(event) => update("station_id", event.target.value)}
          >
            <option value="">Selecione</option>
            {stationOptions.map((station) => (
              <option key={station.id} value={station.id}>
                {station.label}
              </option>
            ))}
          </select>
        </label>
        <label className="text-xs font-bold text-stone">
          Protocolo
          <select
            className={inputClass}
            value={form.protocol ?? "rtsp"}
            onChange={(event) => update("protocol", event.target.value)}
          >
            <option value="rtsp">RTSP</option>
            <option value="onvif">ONVIF</option>
            <option value="http">HTTP Snapshot</option>
          </select>
        </label>
        <label className="text-xs font-bold text-stone">
          IP ou host
          <input
            className={inputClass}
            value={form.ip_address ?? ""}
            onChange={(event) => update("ip_address", event.target.value)}
          />
        </label>
        <label className="text-xs font-bold text-stone">
          Porta
          <input
            type="number"
            className={inputClass}
            value={form.port ?? ""}
            onChange={(event) =>
              update(
                "port",
                event.target.value ? Number(event.target.value) : null,
              )
            }
          />
        </label>
        <label className="text-xs font-bold text-stone">
          Usuário
          <input
            className={inputClass}
            value={form.username ?? ""}
            onChange={(event) => update("username", event.target.value)}
          />
        </label>
        <label className="text-xs font-bold text-stone">
          Senha
          <input
            type="password"
            autoComplete="new-password"
            className={inputClass}
            value={form.password ?? ""}
            onChange={(event) => update("password", event.target.value)}
            placeholder={
              camera?.has_credentials ? "Mantida se vazia" : "Opcional"
            }
          />
        </label>
        <label className="text-xs font-bold text-stone">
          URL de conexão
          <input
            className={inputClass}
            value={form.connection_url ?? ""}
            onChange={(event) => update("connection_url", event.target.value)}
          />
        </label>
        <label className="text-xs font-bold text-stone">
          Status
          <select
            className={inputClass}
            value={form.status ?? "inactive"}
            onChange={(event) => update("status", event.target.value)}
          >
            <option value="active">Ativa</option>
            <option value="inactive">Inativa</option>
          </select>
        </label>
      </div>
      {error && (
        <p role="alert" className="text-sm text-red-200">
          {error}
        </p>
      )}
      <button className={buttonClass} disabled={saving}>
        {saving ? (
          <Loader2 size={15} className="animate-spin" />
        ) : (
          <Save size={15} />
        )}
        Salvar câmera
      </button>
    </form>
  );
}

export default function ProductionVision() {
  const [section, setSection] = useState<Section>("dashboard");
  const [data, setData] = useState<ProductionVisionDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState<string | "new" | null>(null);
  const [query, setQuery] = useState("");
  const [settings, setSettings] = useState(() => {
    try {
      return JSON.parse(
        localStorage.getItem("production_vision_settings") ?? "{}",
      ) as {
        autoRefresh?: boolean;
        captureInterval?: string;
        retentionDays?: string;
      };
    } catch {
      return {};
    }
  });
  const load = useCallback(async (manual = false) => {
    if (manual) setRefreshing(true);
    setError("");
    try {
      setData(await productionVisionApi.dashboard());
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Não foi possível carregar o Registro de Produção.",
      );
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);
  useEffect(() => {
    void load();
  }, [load]);
  useEffect(() => {
    if (!settings.autoRefresh) return;
    const timer = window.setInterval(() => void load(), 30000);
    return () => window.clearInterval(timer);
  }, [load, settings.autoRefresh]);
  const filteredHistory = useMemo(
    () =>
      (data?.history ?? []).filter((item) =>
        `${item.order_code ?? ""} ${item.product_name ?? ""}`
          .toLowerCase()
          .includes(query.toLowerCase()),
      ),
    [data?.history, query],
  );
  function saveSettings(next: typeof settings) {
    setSettings(next);
    localStorage.setItem("production_vision_settings", JSON.stringify(next));
  }
  return (
    <>
      <AdminPageHeader
        eyebrow="KDS / Registro de Produção"
        title="Registro de Produção"
        description="Monitoramento fotográfico das bancadas, câmeras e sessões de produção."
        icon={<Camera size={20} />}
        actions={
          <button
            type="button"
            onClick={() => void load(true)}
            disabled={loading || refreshing}
            className={ghostClass}
          >
            <RefreshCw size={15} className={refreshing ? "animate-spin" : ""} />
            Atualizar
          </button>
        }
      />
      <AdminPageContent>
        <AdminPageTabs tabs={sections} active={section} onChange={(tab) => setSection(tab as Section)} />
        {error && (
          <div
            role="alert"
            className="mt-4 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-100"
          >
            {error}
          </div>
        )}
        {loading ? (
          <div className="flex min-h-64 items-center justify-center text-sm text-stone">
            <Loader2 size={24} className="mr-3 animate-spin text-gold" />
            Carregando Registro de Produção...
          </div>
        ) : !data ? (
          <Empty message="Não há dados disponíveis. Tente atualizar novamente." />
        ) : (
          <div className="mt-5 space-y-5">
            {section === "dashboard" && <Dashboard data={data} />}
            {section === "cameras" && (
              <Cameras
                data={data}
                editing={editing}
                setEditing={setEditing}
                reload={() => load(true)}
              />
            )}
            {section === "stations" && <Stations data={data} />}
            {section === "monitoring" && <Monitoring data={data} />}
            {section === "history" && (
              <HistoryList
                items={data.history}
                query={query}
                setQuery={setQuery}
                filtered={filteredHistory}
              />
            )}
            {section === "order" && (
              <OrderView
                items={[...data.sessions, ...data.history]}
                query={query}
                setQuery={setQuery}
              />
            )}
            {section === "intelligence" && (
              <InfoSection
                icon={Sparkles}
                title="Inteligência Visual"
                message="A captura e o processamento por IA ainda não estão disponíveis no contrato atual. As imagens originais devem ser preservadas quando o gateway for integrado."
              />
            )}
            {section === "settings" && (
              <SettingsPanel settings={settings} save={saveSettings} />
            )}
            {section === "retention" && (
              <RetentionPanel settings={settings} save={saveSettings} />
            )}
            {section === "diagnostics" && <Diagnostics data={data} />}
          </div>
        )}
      </AdminPageContent>
    </>
  );
}

function Dashboard({ data }: { data: ProductionVisionDashboard }) {
  const m = data.metrics ?? {};
  return (
    <>
      <div className="grid grid-cols-2 gap-3 xl:grid-cols-5">
        <Metric
          label="Pedidos monitorados"
          value={m.monitored_orders}
          icon={Video}
        />
        <Metric
          label="Sessões concluídas"
          value={m.completed_sessions}
          icon={CheckCircle2}
        />
        <Metric
          label="Sessões parciais"
          value={m.partial_sessions}
          icon={Clock3}
        />
        <Metric
          label="Fotos capturadas"
          value={m.photos_captured}
          icon={Camera}
        />
        <Metric label="Câmeras online" value={m.cameras_online} icon={Wifi} />
      </div>
      <div className="grid gap-4 xl:grid-cols-2">
        <Card>
          <h2 className="text-lg font-black text-cream">Câmeras</h2>
          <p className="mt-1 text-xs text-stone">
            Estado atual das fontes de captura.
          </p>
          <div className="mt-4 space-y-2">
            {data.cameras.length ? (
              data.cameras
                .slice(0, 5)
                .map((camera) => <CameraRow key={camera.id} camera={camera} />)
            ) : (
              <Empty message="Nenhuma câmera cadastrada." />
            )}
          </div>
        </Card>
        <Card>
          <h2 className="text-lg font-black text-cream">
            Estações de trabalho
          </h2>
          <div className="mt-4 grid gap-2 sm:grid-cols-2">
            {data.stations.length ? (
              data.stations.map((station) => (
                <div
                  key={station.id}
                  className="rounded-xl border border-surface-03 bg-surface-01 p-3"
                >
                  <p className="font-bold text-cream">
                    {text(station.name, station.id)}
                  </p>
                  <p className="mt-2 text-xs text-stone">
                    {number(station.camera_count)} câmeras ·{" "}
                    {number(station.active_sessions)} sessões ativas
                  </p>
                  <p
                    className={`mt-1 text-xs font-bold ${statusClass(station.status)}`}
                  >
                    {statusLabel(station.status)}
                  </p>
                </div>
              ))
            ) : (
              <Empty message="Nenhuma estação encontrada nas unidades de produção." />
            )}
          </div>
        </Card>
      </div>
    </>
  );
}
function CameraRow({
  camera,
  onEdit,
}: {
  camera: ProductionVisionCamera;
  onEdit?: () => void;
}) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-xl border border-surface-03 bg-surface-01 p-3">
      <div className="min-w-0">
        <p className="truncate font-bold text-cream">
          {text(camera.name, camera.id)}
        </p>
        <p className="truncate text-xs text-stone">
          {text(
            camera.station_name ?? camera.station_id,
            "Estação não vinculada",
          )}{" "}
          · {text(camera.protocol, "protocolo não informado")}
        </p>
      </div>
      <div className="flex items-center gap-3">
        <span className={`text-xs font-bold ${statusClass(camera.status)}`}>
          {statusLabel(camera.status)}
        </span>
        {onEdit && (
          <button
            type="button"
            className="text-xs font-bold text-gold"
            onClick={onEdit}
          >
            Editar
          </button>
        )}
      </div>
    </div>
  );
}
function Cameras({
  data,
  editing,
  setEditing,
  reload,
}: {
  data: ProductionVisionDashboard;
  editing: string | "new" | null;
  setEditing: (value: string | "new" | null) => void;
  reload: () => Promise<void>;
}) {
  return (
    <div className="grid gap-5 xl:grid-cols-[1fr_420px]">
      <Card>
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-black text-cream">
              Câmeras cadastradas
            </h2>
            <p className="mt-1 text-xs text-stone">
              Credenciais não são exibidas pelo backend.
            </p>
          </div>
          <button
            type="button"
            className={buttonClass}
            onClick={() => setEditing("new")}
          >
            <Camera size={15} />
            Nova câmera
          </button>
        </div>
        <div className="mt-4 space-y-2">
          {data.cameras.length ? (
            data.cameras.map((camera) => (
              <CameraRow
                key={camera.id}
                camera={camera}
                onEdit={() => setEditing(camera.id)}
              />
            ))
          ) : (
            <Empty message="Nenhuma câmera cadastrada." />
          )}
        </div>
      </Card>
      {editing && (
        <CameraForm
          stations={data.stations}
          camera={
            editing === "new"
              ? undefined
              : data.cameras.find((camera) => camera.id === editing)
          }
          onSaved={async () => {
            setEditing(null);
            await reload();
          }}
        />
      )}
    </div>
  );
}
function Stations({ data }: { data: ProductionVisionDashboard }) {
  const fixedStations = productionVisionStationOptions(data.stations);
  return (
    <Card>
      <h2 className="text-lg font-black text-cream">Estações e zonas</h2>
      <p className="mt-1 text-sm text-stone">
        As bancadas de pizza são fixas para direcionar cada câmera e dispositivo.
        As demais estações continuam vindo do contrato atual; o cadastro de zonas
        físicas aguarda contrato backend.
      </p>
      <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {fixedStations.length ? (
          fixedStations.map((station) => (
            <div
              key={station.id}
              className="rounded-xl border border-surface-03 bg-surface-01 p-4"
            >
              <MapPin className="text-gold" size={18} />
              <h3 className="mt-3 font-bold text-cream">{station.label}</h3>
              <p className="mt-1 text-xs text-stone">ID: {station.id}</p>
              <p className="mt-3 text-sm text-stone">
                {number(station.camera_count)} câmeras ·{" "}
                {number(station.active_sessions)} sessões ativas
              </p>
            </div>
          ))
        ) : (
          <Empty message="Nenhuma estação encontrada." />
        )}
      </div>
    </Card>
  );
}
function Monitoring({ data }: { data: ProductionVisionDashboard }) {
  return (
    <Card>
      <h2 className="text-lg font-black text-cream">Monitoramento ativo</h2>
      <p className="mt-1 text-sm text-stone">
        Sessões ativas e cobertura conhecida pelo contrato atual.
      </p>
      {data.sessions.length ? (
        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[640px] text-left text-sm">
            <thead className="text-xs uppercase tracking-wide text-stone">
              <tr>
                <th className="pb-2 pr-3">Unidade</th>
                <th className="pb-2 pr-3">Etapa</th>
                <th className="pb-2 pr-3">Estação</th>
                <th className="pb-2 pr-3">Início</th>
                <th className="pb-2">Fotos</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-03">
              {data.sessions.map((session) => (
                <tr key={session.id}>
                  <td className="py-3 pr-3 font-bold text-cream">
                    {text(
                      session.order_code ?? session.production_unit_id,
                      session.id,
                    )}
                  </td>
                  <td className="py-3 pr-3 text-stone">
                    {text(session.stage)}
                  </td>
                  <td className="py-3 pr-3 text-stone">
                    {text(session.station_name)}
                  </td>
                  <td className="py-3 pr-3 text-stone">
                    {date(session.started_at)}
                  </td>
                  <td className="py-3 text-stone">
                    {number(session.captured_photos)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="mt-4">
          <Empty message="Nenhuma sessão ativa no momento." />
        </div>
      )}
    </Card>
  );
}
function HistoryList({
  items,
  query,
  setQuery,
  filtered,
}: {
  items: ProductionVisionDashboard["history"];
  query: string;
  setQuery: (value: string) => void;
  filtered: ProductionVisionDashboard["history"];
}) {
  return (
    <Card>
      <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
        <div>
          <h2 className="text-lg font-black text-cream">
            Histórico fotográfico
          </h2>
          <p className="mt-1 text-sm text-stone">
            Registros disponíveis no resumo atual.
          </p>
        </div>
        <input
          aria-label="Buscar histórico"
          className={`${inputClass} sm:max-w-xs`}
          placeholder="Pedido ou produto"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
      </div>
      <div className="mt-4 space-y-2">
        {items.length === 0 ? (
          <Empty message="Nenhum registro fotográfico recente." />
        ) : filtered.length ? (
          filtered.map((item) => (
            <div
              key={item.id}
              className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-surface-03 bg-surface-01 p-3"
            >
              <div>
                <p className="font-bold text-cream">
                  {text(item.order_code, item.id)} · {text(item.product_name)}
                </p>
                <p className="mt-1 text-xs text-stone">
                  {text(item.stage, "Etapa não informada")} ·{" "}
                  {date(item.captured_at)} · {number(item.photo_count)} fotos
                </p>
              </div>
              <span className={`text-xs font-bold ${statusClass(item.status)}`}>
                {statusLabel(item.status)}
              </span>
            </div>
          ))
        ) : (
          <Empty message="Nenhum resultado para a busca." />
        )}
      </div>
    </Card>
  );
}
function OrderView({
  items,
  query,
  setQuery,
}: {
  items: Array<{
    id: string;
    order_code?: string | null;
    product_name?: string | null;
    status?: ProductionVisionStatus | null;
  }>;
  query: string;
  setQuery: (value: string) => void;
}) {
  const results = items.filter((item) =>
    `${item.order_code ?? ""} ${item.product_name ?? ""}`
      .toLowerCase()
      .includes(query.toLowerCase()),
  );
  return (
    <Card>
      <h2 className="text-lg font-black text-cream">Visão por pedido</h2>
      <p className="mt-1 text-sm text-stone">
        Consulte sessões e registros quando o backend disponibilizar esses
        vínculos.
      </p>
      <input
        aria-label="Buscar pedido"
        className={`${inputClass} mt-4 max-w-md`}
        placeholder="Código do pedido ou produto"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
      />
      <div className="mt-4 space-y-2">
        {results.length ? (
          results.map((item) => (
            <div
              key={item.id}
              className="rounded-xl border border-surface-03 bg-surface-01 p-3"
            >
              <p className="font-bold text-cream">
                {text(item.order_code, item.id)} · {text(item.product_name)}
              </p>
              <p
                className={`mt-1 text-xs font-bold ${statusClass(item.status)}`}
              >
                {statusLabel(item.status)}
              </p>
            </div>
          ))
        ) : (
          <Empty message="Nenhum pedido localizado no resumo atual." />
        )}
      </div>
    </Card>
  );
}
function InfoSection({
  icon: Icon,
  title,
  message,
}: {
  icon: typeof Sparkles;
  title: string;
  message: string;
}) {
  return (
    <Card>
      <Icon className="text-gold" size={22} />
      <h2 className="mt-3 text-lg font-black text-cream">{title}</h2>
      <p className="mt-2 max-w-2xl text-sm leading-6 text-stone">{message}</p>
      <div className="mt-4 rounded-xl border border-amber-400/20 bg-amber-400/5 p-3 text-xs text-amber-100">
        Fora do escopo do contrato atual: nenhuma inferência visual é
        apresentada como concluída.
      </div>
    </Card>
  );
}
function SettingsPanel({
  settings,
  save,
}: {
  settings: { autoRefresh?: boolean; captureInterval?: string };
  save: (value: { autoRefresh?: boolean; captureInterval?: string }) => void;
}) {
  return (
    <Card>
      <Settings className="text-gold" size={22} />
      <h2 className="mt-3 text-lg font-black text-cream">
        Configurações operacionais
      </h2>
      <p className="mt-1 text-sm text-stone">
        Preferências locais do painel. Não substituem configurações do gateway.
      </p>
      <label className="mt-5 flex items-center gap-3 text-sm text-cream">
        <input
          type="checkbox"
          checked={settings.autoRefresh === true}
          onChange={(event) =>
            save({ ...settings, autoRefresh: event.target.checked })
          }
        />
        Atualizar dashboard a cada 30 segundos
      </label>
      <label className="mt-4 block max-w-sm text-xs font-bold text-stone">
        Intervalo de captura (referência)
        <input
          className={inputClass}
          value={settings.captureInterval ?? "30"}
          onChange={(event) =>
            save({ ...settings, captureInterval: event.target.value })
          }
        />
      </label>
    </Card>
  );
}
function RetentionPanel({
  settings,
  save,
}: {
  settings: { retentionDays?: string };
  save: (value: { retentionDays?: string }) => void;
}) {
  return (
    <Card>
      <Database className="text-gold" size={22} />
      <h2 className="mt-3 text-lg font-black text-cream">
        Retenção de evidências
      </h2>
      <p className="mt-1 text-sm text-stone">
        A política abaixo é uma preferência local até existir worker de retenção
        no backend.
      </p>
      <label className="mt-5 block max-w-sm text-xs font-bold text-stone">
        Dias de retenção
        <input
          type="number"
          min="1"
          className={inputClass}
          value={settings.retentionDays ?? "7"}
          onChange={(event) =>
            save({ ...settings, retentionDays: event.target.value })
          }
        />
      </label>
      <p className="mt-4 text-xs text-amber-100">
        Nenhum arquivo será excluído por esta tela.
      </p>
    </Card>
  );
}
function Diagnostics({ data }: { data: ProductionVisionDashboard }) {
  const offline = data.cameras.filter((camera) =>
    ["offline", "inactive"].includes(camera.status ?? ""),
  ).length;
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <Card>
        <div className="flex items-center gap-2">
          <Wifi className="text-gold" size={20} />
          <h2 className="text-lg font-black text-cream">Conectividade</h2>
        </div>
        <p className="mt-3 text-sm text-stone">
          {data.cameras.length
            ? `${number(data.cameras.length - offline)} de ${number(data.cameras.length)} câmeras marcadas como ativas.`
            : "Nenhuma câmera cadastrada para diagnosticar."}
        </p>
        <p
          className={`mt-3 text-sm font-bold ${offline ? "text-amber-200" : "text-emerald-300"}`}
        >
          {offline
            ? `${number(offline)} câmera(s) exigem atenção.`
            : "Sem incidentes derivados do cadastro."}
        </p>
      </Card>
      <Card>
        <div className="flex items-center gap-2">
          <ShieldCheck className="text-gold" size={20} />
          <h2 className="text-lg font-black text-cream">Segurança</h2>
        </div>
        <p className="mt-3 text-sm text-stone">
          Acesso protegido pela permissão{" "}
          <code className="text-gold">cozinha:view</code>. O frontend não recebe
          senhas de câmera.
        </p>
        <p className="mt-3 text-xs text-stone">
          Gateway local, heartbeat e incidentes persistidos ainda não estão
          disponíveis no contrato atual.
        </p>
      </Card>
    </div>
  );
}
