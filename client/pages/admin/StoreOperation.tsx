import { useEffect, useMemo, useState } from "react";
import AdminSidebar from "@/components/AdminSidebar";
import AdminTopActions from "@/components/admin/AdminTopActions";
import {
  AlertCircle, CalendarDays, Check, Clock, Loader2, Plus, Save, Store,
  Trash2, X,
} from "lucide-react";
import {
  storeOperationApi,
  type StoreOperationConfig,
  type StoreOperationException,
  type StoreOperationSettings,
  type StoreWeeklySchedule,
} from "@/lib/api";

const WEEKDAYS = ["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado", "Domingo"];
const cls = "w-full bg-surface-03 border border-surface-03 rounded-lg px-3 py-2 text-cream placeholder-stone/70 outline-none focus:border-gold";

const defaultSchedules = (): StoreWeeklySchedule[] =>
  WEEKDAYS.map((_, weekday) => ({
    weekday,
    active: true,
    intervals: [{ open_time: "18:00", close_time: "23:30" }],
  }));

export default function StoreOperation() {
  const [config, setConfig] = useState<StoreOperationConfig | null>(null);
  const [settings, setSettings] = useState<StoreOperationSettings | null>(null);
  const [schedules, setSchedules] = useState<StoreWeeklySchedule[]>(defaultSchedules());
  const [exceptions, setExceptions] = useState<StoreOperationException[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [exceptionForm, setExceptionForm] = useState({
    date: "",
    exception_type: "closed" as "closed" | "special_hours",
    open_time: "18:00",
    close_time: "23:30",
    reason: "",
  });

  const sortedSchedules = useMemo(() => {
    const byDay = new Map(schedules.map((schedule) => [schedule.weekday, schedule]));
    return WEEKDAYS.map((_, weekday) => byDay.get(weekday) ?? defaultSchedules()[weekday]);
  }, [schedules]);

  const load = async () => {
    setLoading(true);
    setLoadError("");
    try {
      const data = await storeOperationApi.config();
      setConfig(data);
      setSettings(data.settings);
      setSchedules(data.weekly_schedules.length ? data.weekly_schedules : defaultSchedules());
      setExceptions(data.exceptions);
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : "Erro ao carregar configurações.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const updateSchedule = (weekday: number, patch: Partial<StoreWeeklySchedule>) => {
    setSchedules((prev) => sortedSchedules.map((schedule) =>
      schedule.weekday === weekday ? { ...schedule, ...patch } : schedule
    ));
  };

  const addInterval = (weekday: number) => {
    const schedule = sortedSchedules[weekday];
    updateSchedule(weekday, { intervals: [...schedule.intervals, { open_time: "18:00", close_time: "23:30" }] });
  };

  const updateInterval = (weekday: number, index: number, field: "open_time" | "close_time", value: string) => {
    const schedule = sortedSchedules[weekday];
    updateSchedule(weekday, {
      intervals: schedule.intervals.map((interval, i) => i === index ? { ...interval, [field]: value } : interval),
    });
  };

  const removeInterval = (weekday: number, index: number) => {
    const schedule = sortedSchedules[weekday];
    updateSchedule(weekday, { intervals: schedule.intervals.filter((_, i) => i !== index) });
  };

  const saveAll = async () => {
    if (!settings) return;
    setSaving(true);
    setMessage("");
    try {
      const cleanSchedules = sortedSchedules.map((schedule) => ({
        weekday: schedule.weekday,
        active: schedule.active,
        intervals: schedule.intervals.map((interval) => ({
          open_time: interval.open_time,
          close_time: interval.close_time,
        })),
      }));
      const [savedSettings, savedSchedules] = await Promise.all([
        storeOperationApi.updateSettings(settings),
        storeOperationApi.updateWeeklySchedules(cleanSchedules),
      ]);
      setSettings(savedSettings);
      setSchedules(savedSchedules);
      setMessage("Funcionamento salvo com sucesso.");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Erro ao salvar funcionamento.");
    } finally {
      setSaving(false);
    }
  };

  const createException = async () => {
    if (!exceptionForm.date) return;
    const payload = {
      date: exceptionForm.date,
      exception_type: exceptionForm.exception_type,
      open_time: exceptionForm.exception_type === "special_hours" ? exceptionForm.open_time : null,
      close_time: exceptionForm.exception_type === "special_hours" ? exceptionForm.close_time : null,
      reason: exceptionForm.reason || null,
    };
    try {
      const created = await storeOperationApi.createException(payload);
      setExceptions((prev) => [created, ...prev]);
      setExceptionForm({ date: "", exception_type: "closed", open_time: "18:00", close_time: "23:30", reason: "" });
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Erro ao criar excecao.");
    }
  };

  const deleteException = async (id: string) => {
    if (!confirm("Remover esta excecao?")) return;
    await storeOperationApi.removeException(id);
    setExceptions((prev) => prev.filter((item) => item.id !== id));
  };

  if (loading) {
    return (
      <div className="flex flex-col md:flex-row min-h-screen md:h-screen bg-surface-00 overflow-hidden">
        <AdminSidebar />
        <main className="flex-1 flex items-center justify-center text-stone gap-2">
          <Loader2 size={20} className="animate-spin" /> Carregando funcionamento...
        </main>
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="flex flex-col md:flex-row min-h-screen md:h-screen bg-surface-00 overflow-hidden">
        <AdminSidebar />
        <main className="flex-1 flex flex-col items-center justify-center gap-4 p-8">
          <AlertCircle size={40} className="text-red-400" />
          <p className="text-cream font-semibold text-lg">Erro ao carregar</p>
          <p className="text-stone text-sm text-center max-w-sm">{loadError}</p>
          <button
            onClick={load}
            className="mt-2 bg-gold hover:bg-gold/90 text-cream font-bold px-5 py-2.5 rounded-xl transition-colors"
          >
            Tentar novamente
          </button>
        </main>
      </div>
    );
  }

  if (!settings) return null;

  return (
    <div className="flex flex-col md:flex-row min-h-screen md:h-screen bg-surface-00 overflow-hidden">
      <AdminSidebar />
      <main className="flex-1 overflow-y-auto">
        <header className="bg-surface-02 border-b border-surface-03 px-6 py-5 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <p className="text-gold text-xs font-bold uppercase tracking-[0.2em]">Operacao</p>
            <h1 className="text-cream text-2xl font-bold">Funcionamento da Loja Online</h1>
            <p className="text-stone text-sm mt-1">Controle dias, horarios, excecoes e agendamento de pedidos.</p>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={saveAll}
              disabled={saving}
              className="inline-flex items-center justify-center gap-2 bg-gold hover:bg-gold/90 disabled:opacity-60 text-cream font-bold px-5 py-3 rounded-xl transition-colors"
            >
              {saving ? <Loader2 size={17} className="animate-spin" /> : <Save size={17} />}
              Salvar alteracoes
            </button>
            <AdminTopActions />
          </div>
        </header>

        <div className="p-6 space-y-6">
          {message && (
            <div className="bg-surface-02 border border-surface-03 rounded-xl px-4 py-3 text-parchment flex items-center gap-2">
              <AlertCircle size={16} className="text-gold" /> {message}
            </div>
          )}

          <section className="grid grid-cols-1 xl:grid-cols-[1fr,360px] gap-6">
            <div className="bg-surface-02 border border-surface-03 rounded-2xl p-5">
              <div className="flex items-center gap-3 mb-5">
                <Clock size={20} className="text-gold" />
                <div>
                  <h2 className="text-cream font-bold">Horarios semanais</h2>
                  <p className="text-stone text-sm">Adicione um ou mais intervalos por dia.</p>
                </div>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {sortedSchedules.map((schedule) => (
                  <div key={schedule.weekday} className="bg-surface-01 border border-surface-03 rounded-xl p-4">
                    <div className="flex items-center justify-between gap-3 mb-3">
                      <div>
                        <h3 className="text-cream font-bold">{WEEKDAYS[schedule.weekday]}</h3>
                        <p className="text-stone text-xs">{schedule.active ? "Dia ativo" : "Dia fechado"}</p>
                      </div>
                      <button
                        onClick={() => updateSchedule(schedule.weekday, { active: !schedule.active })}
                        className={`px-3 py-1.5 rounded-full text-xs font-bold ${schedule.active ? "bg-emerald-500/20 text-emerald-300" : "bg-red-500/20 text-red-300"}`}
                      >
                        {schedule.active ? "Aberto" : "Fechado"}
                      </button>
                    </div>

                    <div className="space-y-2">
                      {schedule.intervals.map((interval, index) => (
                        <div key={index} className="grid grid-cols-[1fr,1fr,36px] gap-2">
                          <input type="time" value={interval.open_time.slice(0, 5)} onChange={(e) => updateInterval(schedule.weekday, index, "open_time", e.target.value)} className={cls} disabled={!schedule.active} />
                          <input type="time" value={interval.close_time.slice(0, 5)} onChange={(e) => updateInterval(schedule.weekday, index, "close_time", e.target.value)} className={cls} disabled={!schedule.active} />
                          <button onClick={() => removeInterval(schedule.weekday, index)} className="rounded-lg bg-red-500/10 text-red-300 hover:bg-red-500/20 flex items-center justify-center">
                            <Trash2 size={15} />
                          </button>
                        </div>
                      ))}
                    </div>
                    <button onClick={() => addInterval(schedule.weekday)} className="mt-3 text-gold text-sm font-semibold inline-flex items-center gap-1">
                      <Plus size={14} /> Adicionar intervalo
                    </button>
                  </div>
                ))}
              </div>
            </div>

            <aside className="space-y-5">
              <div className="bg-surface-02 border border-surface-03 rounded-2xl p-5 space-y-4">
                <div className="flex items-center gap-3">
                  <Store size={20} className="text-gold" />
                  <h2 className="text-cream font-bold">Status manual</h2>
                </div>
                <select value={settings.manual_mode} onChange={(e) => setSettings({ ...settings, manual_mode: e.target.value as StoreOperationSettings["manual_mode"] })} className={cls}>
                  <option value="auto">Loja aberta automaticamente conforme horario</option>
                  <option value="manual_closed">Loja fechada manualmente</option>
                  <option value="manual_open">Loja aberta manualmente</option>
                </select>
                <div>
                  <label className="text-parchment text-xs mb-1 block">Mensagem de loja fechada</label>
                  <textarea value={settings.closed_message} onChange={(e) => setSettings({ ...settings, closed_message: e.target.value })} className={`${cls} min-h-24 resize-none`} />
                </div>
                <label className="flex items-center gap-2 text-parchment text-sm">
                  <input type="checkbox" checked={settings.allow_scheduled_orders} onChange={(e) => setSettings({ ...settings, allow_scheduled_orders: e.target.checked })} className="accent-gold" />
                  Permitir pedido agendado fora do horario
                </label>
              </div>

              <div className="bg-surface-02 border border-surface-03 rounded-2xl p-5 space-y-4">
                <div className="flex items-center gap-3">
                  <CalendarDays size={20} className="text-gold" />
                  <h2 className="text-cream font-bold">Excecoes de Funcionamento</h2>
                </div>
                <input type="date" value={exceptionForm.date} onChange={(e) => setExceptionForm((f) => ({ ...f, date: e.target.value }))} className={cls} />
                <select value={exceptionForm.exception_type} onChange={(e) => setExceptionForm((f) => ({ ...f, exception_type: e.target.value as "closed" | "special_hours" }))} className={cls}>
                  <option value="closed">Fechar o dia inteiro</option>
                  <option value="special_hours">Abrir em horario especial</option>
                </select>
                {exceptionForm.exception_type === "special_hours" && (
                  <div className="grid grid-cols-2 gap-2">
                    <input type="time" value={exceptionForm.open_time} onChange={(e) => setExceptionForm((f) => ({ ...f, open_time: e.target.value }))} className={cls} />
                    <input type="time" value={exceptionForm.close_time} onChange={(e) => setExceptionForm((f) => ({ ...f, close_time: e.target.value }))} className={cls} />
                  </div>
                )}
                <input value={exceptionForm.reason} onChange={(e) => setExceptionForm((f) => ({ ...f, reason: e.target.value }))} className={cls} placeholder="Motivo interno" />
                <button onClick={createException} className="w-full bg-surface-03 hover:bg-gold/10 text-gold font-bold rounded-xl py-2.5 transition-colors">
                  Adicionar excecao
                </button>
              </div>
            </aside>
          </section>

          <section className="bg-surface-02 border border-surface-03 rounded-2xl p-5">
            <h2 className="text-cream font-bold mb-4">Feriados e datas especiais</h2>
            {exceptions.length === 0 ? (
              <p className="text-stone text-sm">Nenhuma excecao cadastrada.</p>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
                {exceptions.map((item) => (
                  <div key={item.id} className="bg-surface-01 border border-surface-03 rounded-xl p-4 flex items-start gap-3">
                    <div className={`h-9 w-9 rounded-lg flex items-center justify-center ${item.exception_type === "closed" ? "bg-red-500/20 text-red-300" : "bg-emerald-500/20 text-emerald-300"}`}>
                      {item.exception_type === "closed" ? <X size={17} /> : <Check size={17} />}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-cream font-bold">{new Date(`${item.date}T00:00:00`).toLocaleDateString("pt-BR")}</p>
                      <p className="text-stone text-sm">
                        {item.exception_type === "closed" ? "Fechado o dia inteiro" : `${item.open_time?.slice(0, 5)} as ${item.close_time?.slice(0, 5)}`}
                      </p>
                      {item.reason && <p className="text-stone text-xs mt-1 line-clamp-2">{item.reason}</p>}
                    </div>
                    <button onClick={() => deleteException(item.id)} className="text-stone hover:text-red-300">
                      <Trash2 size={16} />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </section>
        </div>
      </main>
    </div>
  );
}
