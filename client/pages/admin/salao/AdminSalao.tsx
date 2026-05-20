import { useEffect, useMemo, useState } from "react";
import {
  CalendarDays,
  Check,
  ClipboardList,
  Clock,
  CreditCard,
  Loader2,
  Plus,
  RefreshCw,
  Search,
  TableProperties,
  Users,
  Utensils,
} from "lucide-react";
import {
  AdminPageContent,
  AdminPageHeader,
  AdminPageShell,
  AdminPageTabs,
  type AdminPageTab,
} from "@/components/admin/AdminPageChrome";
import {
  ordersApi,
  productsApi,
  salaoApi,
  type ApiOrder,
  type ApiProduct,
  type ApiReservation,
  type ApiReservationStatus,
  type ApiRestaurantTable,
  type ApiRestaurantTableStatus,
  type ApiTableSession,
  type ApiTableSessionStatus,
} from "@/lib/api";

type Tab = "dashboard" | "tables" | "reservations" | "orders" | "sessions" | "customers";

const TABS: AdminPageTab<Tab>[] = [
  { id: "dashboard", icon: <ClipboardList size={15} />, label: "Dashboard" },
  { id: "tables", icon: <TableProperties size={15} />, label: "Mesas" },
  { id: "reservations", icon: <CalendarDays size={15} />, label: "Reservas" },
  { id: "orders", icon: <Utensils size={15} />, label: "Pedidos do Salao" },
  { id: "sessions", icon: <CreditCard size={15} />, label: "Comandas" },
  { id: "customers", icon: <Users size={15} />, label: "Clientes do Salao" },
];

const tableStatusLabel: Record<ApiRestaurantTableStatus, string> = {
  available: "Disponivel",
  occupied: "Ocupada",
  reserved: "Reservada",
  cleaning: "Limpeza",
  inactive: "Inativa",
};

const reservationStatusLabel: Record<ApiReservationStatus, string> = {
  pending: "Pendente",
  confirmed: "Confirmada",
  seated: "Na mesa",
  cancelled: "Cancelada",
  no_show: "No-show",
  completed: "Concluida",
};

const sessionStatusLabel: Record<ApiTableSessionStatus, string> = {
  open: "Aberta",
  pending_payment: "Pgto pendente",
  paid: "Paga",
  closed: "Fechada",
  cancelled: "Cancelada",
};

function statusClass(status: string) {
  if (["available", "confirmed", "paid", "closed", "completed"].includes(status)) return "bg-emerald-500/15 text-emerald-300";
  if (["occupied", "open", "seated"].includes(status)) return "bg-gold/15 text-gold";
  if (["reserved", "pending", "pending_payment"].includes(status)) return "bg-blue-500/15 text-blue-300";
  if (["cancelled", "no_show", "inactive"].includes(status)) return "bg-red-500/15 text-red-300";
  return "bg-stone/20 text-stone";
}

function Badge({ children, tone }: { children: string; tone: string }) {
  return <span className={`inline-flex rounded-full px-2 py-0.5 text-[11px] font-bold ${statusClass(tone)}`}>{children}</span>;
}

function formatCurrency(value: number) {
  return value.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function formatDate(value?: string | null) {
  if (!value) return "-";
  return new Date(`${value}T00:00:00`).toLocaleDateString("pt-BR");
}

function formatDateTime(value?: string | null) {
  if (!value) return "-";
  return new Date(value).toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}

function today() {
  return new Date().toISOString().slice(0, 10);
}

function Kpi({ label, value, icon }: { label: string; value: string | number; icon: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-surface-03 bg-surface-02 p-4">
      <div className="mb-3 flex items-center justify-between text-gold">{icon}</div>
      <p className="text-2xl font-black text-cream">{value}</p>
      <p className="mt-1 text-xs text-stone">{label}</p>
    </div>
  );
}

export default function AdminSalao() {
  const [tab, setTab] = useState<Tab>("dashboard");
  const [tables, setTables] = useState<ApiRestaurantTable[]>([]);
  const [reservations, setReservations] = useState<ApiReservation[]>([]);
  const [sessions, setSessions] = useState<ApiTableSession[]>([]);
  const [orders, setOrders] = useState<ApiOrder[]>([]);
  const [products, setProducts] = useState<ApiProduct[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");

  const [tableForm, setTableForm] = useState({ number: "", name: "", capacity: 2, location: "" });
  const [reservationForm, setReservationForm] = useState({
    customer_name: "",
    customer_phone: "",
    customer_email: "",
    table_id: "",
    reservation_date: today(),
    reservation_time: "20:00",
    guests_count: 2,
    notes: "",
  });
  const [sessionForm, setSessionForm] = useState({ table_id: "", waiter_name: "", notes: "" });
  const [sessionItemForm, setSessionItemForm] = useState({ session_id: "", product_id: "", quantity: 1, notes: "" });

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const [nextTables, nextReservations, nextSessions, nextOrders, nextProducts] = await Promise.all([
        salaoApi.tables.list({ include_inactive: true }),
        salaoApi.reservations.list(),
        salaoApi.sessions.list(),
        ordersApi.list({ sales_channel: "dine_in", limit: 100 }),
        productsApi.list(true, undefined, "dine_in"),
      ]);
      setTables(nextTables);
      setReservations(nextReservations);
      setSessions(nextSessions);
      setOrders(nextOrders);
      setProducts(nextProducts);
    } catch {
      setError("Nao foi possivel carregar os dados do modulo Salao & Reservas.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const activeSessions = sessions.filter((session) => ["open", "pending_payment"].includes(session.status));
  const editableSessions = sessions.filter((session) => session.status === "open");
  const todayReservations = reservations.filter((reservation) => reservation.reservation_date === today());
  const salaoCustomers = useMemo(() => {
    const map = new Map<string, ApiReservation>();
    reservations.forEach((reservation) => {
      const key = `${reservation.customer_phone}-${reservation.customer_email ?? ""}`;
      if (!map.has(key)) map.set(key, reservation);
    });
    return Array.from(map.values());
  }, [reservations]);

  const filteredReservations = reservations.filter((reservation) => {
    const needle = query.trim().toLowerCase();
    if (!needle) return true;
    return [reservation.customer_name, reservation.customer_phone, reservation.customer_email, reservation.source]
      .filter(Boolean)
      .some((value) => String(value).toLowerCase().includes(needle));
  });

  const createTable = async () => {
    if (!tableForm.number.trim()) return;
    setSaving(true);
    try {
      await salaoApi.tables.create({
        number: tableForm.number.trim(),
        name: tableForm.name.trim() || null,
        capacity: Number(tableForm.capacity) || 2,
        location: tableForm.location.trim() || null,
        status: "available",
        active: true,
      });
      setTableForm({ number: "", name: "", capacity: 2, location: "" });
      await load();
    } finally {
      setSaving(false);
    }
  };

  const createReservation = async () => {
    if (!reservationForm.customer_name.trim() || !reservationForm.customer_phone.trim()) return;
    setSaving(true);
    try {
      await salaoApi.reservations.create({
        customer_id: null,
        customer_name: reservationForm.customer_name.trim(),
        customer_phone: reservationForm.customer_phone.trim(),
        customer_email: reservationForm.customer_email.trim() || null,
        table_id: reservationForm.table_id || null,
        reservation_date: reservationForm.reservation_date,
        reservation_time: reservationForm.reservation_time,
        guests_count: Number(reservationForm.guests_count) || 2,
        status: "pending",
        notes: reservationForm.notes.trim() || null,
        source: "erp",
      });
      setReservationForm((current) => ({ ...current, customer_name: "", customer_phone: "", customer_email: "", notes: "" }));
      await load();
    } finally {
      setSaving(false);
    }
  };

  const openSession = async () => {
    if (!sessionForm.table_id) return;
    setSaving(true);
    try {
      await salaoApi.sessions.open({
        table_id: sessionForm.table_id,
        customer_id: null,
        status: "open",
        subtotal: 0,
        service_fee: 0,
        discount: 0,
        total: 0,
        waiter_name: sessionForm.waiter_name.trim() || null,
        notes: sessionForm.notes.trim() || null,
      });
      setSessionForm({ table_id: "", waiter_name: "", notes: "" });
      await load();
    } finally {
      setSaving(false);
    }
  };

  const closeSession = async (session: ApiTableSession) => {
    await salaoApi.sessions.close(session.id, { status: "closed", total: session.total, notes: session.notes });
    await load();
  };

  const createSessionOrder = async (session: ApiTableSession) => {
    setSaving(true);
    setError("");
    try {
      await salaoApi.sessions.createOrder(session.id, { payment_method: "cash" });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nao foi possivel gerar o pedido do salao.");
    } finally {
      setSaving(false);
    }
  };

  const confirmSessionPayment = async (session: ApiTableSession) => {
    setSaving(true);
    setError("");
    try {
      await salaoApi.sessions.confirmPayment(session.id, { payment_method: "cash" });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nao foi possivel confirmar o pagamento da comanda.");
    } finally {
      setSaving(false);
    }
  };

  const addSessionItem = async () => {
    if (!sessionItemForm.session_id || !sessionItemForm.product_id) return;
    setSaving(true);
    try {
      await salaoApi.sessions.addItem(sessionItemForm.session_id, {
        product_id: sessionItemForm.product_id,
        quantity: Number(sessionItemForm.quantity) || 1,
        notes: sessionItemForm.notes.trim() || null,
      });
      setSessionItemForm({ session_id: sessionItemForm.session_id, product_id: "", quantity: 1, notes: "" });
      await load();
    } finally {
      setSaving(false);
    }
  };

  const deleteSessionItem = async (sessionId: string, itemId: string) => {
    await salaoApi.sessions.deleteItem(sessionId, itemId);
    await load();
  };

  const updateTableStatus = async (tableId: string, status: ApiRestaurantTableStatus) => {
    await salaoApi.tables.updateStatus(tableId, status);
    await load();
  };

  const updateReservationStatus = async (reservationId: string, status: ApiReservationStatus) => {
    await salaoApi.reservations.updateStatus(reservationId, status);
    await load();
  };

  return (
    <AdminPageShell>
      <AdminPageHeader
        icon={<Utensils size={20} />}
        title="Salao & Reservas"
        description="Operacao de mesas, reservas, comandas e pedidos do salao"
        actions={
          <button
            type="button"
            onClick={load}
            className="inline-flex items-center gap-2 rounded-xl border border-surface-03 bg-surface-02 px-3 py-2 text-sm font-semibold text-parchment hover:text-cream"
          >
            <RefreshCw size={15} />
            Atualizar
          </button>
        }
      />
      <AdminPageTabs tabs={TABS} active={tab} onChange={(next) => setTab(next as Tab)} />
      <AdminPageContent>
        {loading ? (
          <div className="flex items-center justify-center gap-2 py-24 text-stone">
            <Loader2 className="animate-spin" size={22} />
            Carregando modulo do salao...
          </div>
        ) : error ? (
          <div className="rounded-xl border border-red-500/25 bg-red-500/10 p-4 text-sm text-red-300">{error}</div>
        ) : (
          <>
            {tab === "dashboard" && (
              <div className="space-y-6">
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
                  <Kpi label="Mesas ativas" value={tables.filter((table) => table.active).length} icon={<TableProperties size={20} />} />
                  <Kpi label="Mesas ocupadas" value={tables.filter((table) => table.status === "occupied").length} icon={<Utensils size={20} />} />
                  <Kpi label="Reservas hoje" value={todayReservations.length} icon={<CalendarDays size={20} />} />
                  <Kpi label="Comandas abertas" value={activeSessions.length} icon={<CreditCard size={20} />} />
                  <Kpi label="Faturamento salao" value={formatCurrency(orders.reduce((sum, order) => sum + (order.total || 0), 0))} icon={<Check size={20} />} />
                </div>
                <div className="grid gap-4 lg:grid-cols-2">
                  <Panel title="Reservas recentes">
                    <ReservationList reservations={reservations.slice(0, 6)} tables={tables} onStatus={updateReservationStatus} />
                  </Panel>
                  <Panel title="Comandas abertas">
                    <SessionList sessions={activeSessions} tables={tables} orders={orders} onClose={closeSession} onCreateOrder={createSessionOrder} onConfirmPayment={confirmSessionPayment} onDeleteItem={deleteSessionItem} />
                  </Panel>
                </div>
              </div>
            )}

            {tab === "tables" && (
              <div className="grid gap-4 xl:grid-cols-[360px_minmax(0,1fr)]">
                <Panel title="Nova mesa">
                  <div className="grid gap-3">
                    <Input label="Numero" value={tableForm.number} onChange={(value) => setTableForm((f) => ({ ...f, number: value }))} />
                    <Input label="Nome" value={tableForm.name} onChange={(value) => setTableForm((f) => ({ ...f, name: value }))} />
                    <Input label="Capacidade" type="number" value={String(tableForm.capacity)} onChange={(value) => setTableForm((f) => ({ ...f, capacity: Number(value) }))} />
                    <Input label="Localizacao" value={tableForm.location} onChange={(value) => setTableForm((f) => ({ ...f, location: value }))} />
                    <PrimaryButton onClick={createTable} disabled={saving || !tableForm.number.trim()}>Criar mesa</PrimaryButton>
                  </div>
                </Panel>
                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                  {tables.map((table) => (
                    <div key={table.id} className="rounded-xl border border-surface-03 bg-surface-02 p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="text-lg font-black text-cream">Mesa {table.number}</p>
                          <p className="text-xs text-stone">{table.name || table.location || "Sem descricao"}</p>
                        </div>
                        <Badge tone={table.status}>{tableStatusLabel[table.status]}</Badge>
                      </div>
                      <p className="mt-4 text-sm text-parchment">{table.capacity} lugares</p>
                      <div className="mt-4 flex flex-wrap gap-2">
                        {(["available", "reserved", "occupied", "cleaning"] as ApiRestaurantTableStatus[]).map((status) => (
                          <button key={status} onClick={() => updateTableStatus(table.id, status)} className="rounded-lg border border-surface-03 px-2 py-1 text-xs text-stone hover:text-cream">
                            {tableStatusLabel[status]}
                          </button>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {tab === "reservations" && (
              <div className="grid gap-4 xl:grid-cols-[360px_minmax(0,1fr)]">
                <Panel title="Nova reserva">
                  <div className="grid gap-3">
                    <Input label="Cliente" value={reservationForm.customer_name} onChange={(value) => setReservationForm((f) => ({ ...f, customer_name: value }))} />
                    <Input label="Telefone" value={reservationForm.customer_phone} onChange={(value) => setReservationForm((f) => ({ ...f, customer_phone: value }))} />
                    <Input label="Email" value={reservationForm.customer_email} onChange={(value) => setReservationForm((f) => ({ ...f, customer_email: value }))} />
                    <div className="grid grid-cols-2 gap-3">
                      <Input label="Data" type="date" value={reservationForm.reservation_date} onChange={(value) => setReservationForm((f) => ({ ...f, reservation_date: value }))} />
                      <Input label="Hora" type="time" value={reservationForm.reservation_time} onChange={(value) => setReservationForm((f) => ({ ...f, reservation_time: value }))} />
                    </div>
                    <Select label="Mesa" value={reservationForm.table_id} onChange={(value) => setReservationForm((f) => ({ ...f, table_id: value }))}>
                      <option value="">Sem mesa definida</option>
                      {tables.map((table) => <option key={table.id} value={table.id}>Mesa {table.number}</option>)}
                    </Select>
                    <Input label="Pessoas" type="number" value={String(reservationForm.guests_count)} onChange={(value) => setReservationForm((f) => ({ ...f, guests_count: Number(value) }))} />
                    <Input label="Observacoes" value={reservationForm.notes} onChange={(value) => setReservationForm((f) => ({ ...f, notes: value }))} />
                    <PrimaryButton onClick={createReservation} disabled={saving || !reservationForm.customer_name.trim() || !reservationForm.customer_phone.trim()}>Criar reserva</PrimaryButton>
                  </div>
                </Panel>
                <Panel title="Reservas">
                  <div className="mb-4 flex items-center gap-2 rounded-xl border border-surface-03 bg-surface-03/50 px-3 py-2">
                    <Search size={15} className="text-stone" />
                    <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Buscar reservas..." className="min-w-0 flex-1 bg-transparent text-sm text-cream outline-none placeholder:text-stone" />
                  </div>
                  <ReservationList reservations={filteredReservations} tables={tables} onStatus={updateReservationStatus} />
                </Panel>
              </div>
            )}

            {tab === "orders" && (
              <Panel title="Pedidos do Salao">
                {orders.length === 0 ? (
                  <Empty text="Nenhum pedido do salao encontrado. O fluxo de criacao de pedido dine_in entra na proxima etapa." />
                ) : (
                  <div className="grid gap-3">
                    {orders.map((order) => (
                      <div key={order.id} className="rounded-xl border border-surface-03 bg-surface-01 p-4">
                        <div className="flex flex-wrap items-center justify-between gap-3">
                          <div>
                            <p className="font-bold text-cream">Pedido {order.order_code || order.id.slice(0, 8)}</p>
                            <p className="text-xs text-stone">{formatDateTime(order.created_at)}</p>
                          </div>
                          <p className="font-black text-gold">{formatCurrency(order.total)}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </Panel>
            )}

            {tab === "sessions" && (
              <div className="grid gap-4 xl:grid-cols-[360px_minmax(0,1fr)]">
                <Panel title="Abrir comanda">
                  <div className="grid gap-3">
                    <Select label="Mesa" value={sessionForm.table_id} onChange={(value) => setSessionForm((f) => ({ ...f, table_id: value }))}>
                      <option value="">Selecione uma mesa</option>
                      {tables.filter((table) => table.active && !["occupied", "inactive"].includes(table.status)).map((table) => (
                        <option key={table.id} value={table.id}>Mesa {table.number}</option>
                      ))}
                    </Select>
                    <Input label="Atendente" value={sessionForm.waiter_name} onChange={(value) => setSessionForm((f) => ({ ...f, waiter_name: value }))} />
                    <Input label="Observacoes" value={sessionForm.notes} onChange={(value) => setSessionForm((f) => ({ ...f, notes: value }))} />
                    <PrimaryButton onClick={openSession} disabled={saving || !sessionForm.table_id}>Abrir comanda</PrimaryButton>
                  </div>
                </Panel>
                <Panel title="Comandas">
                  <div className="mb-5 rounded-xl border border-surface-03 bg-surface-01 p-4">
                    <h3 className="mb-3 text-sm font-black text-cream">Adicionar consumo</h3>
                    <div className="grid gap-3 md:grid-cols-[1fr_1fr_100px]">
                      <Select label="Comanda" value={sessionItemForm.session_id} onChange={(value) => setSessionItemForm((f) => ({ ...f, session_id: value }))}>
                        <option value="">Selecione</option>
                        {editableSessions.map((session) => (
                          <option key={session.id} value={session.id}>
                            Mesa {tables.find((table) => table.id === session.table_id)?.number ?? "-"}
                          </option>
                        ))}
                      </Select>
                      <Select label="Produto" value={sessionItemForm.product_id} onChange={(value) => setSessionItemForm((f) => ({ ...f, product_id: value }))}>
                        <option value="">Selecione</option>
                        {products.map((product) => (
                          <option key={product.id} value={product.id}>
                            {product.name} - {formatCurrency(product.dine_in_price ?? product.current_price ?? product.price)}
                          </option>
                        ))}
                      </Select>
                      <Input label="Qtd" type="number" value={String(sessionItemForm.quantity)} onChange={(value) => setSessionItemForm((f) => ({ ...f, quantity: Number(value) || 1 }))} />
                    </div>
                    <div className="mt-3 grid gap-3 md:grid-cols-[1fr_auto] md:items-end">
                      <Input label="Observacoes" value={sessionItemForm.notes} onChange={(value) => setSessionItemForm((f) => ({ ...f, notes: value }))} />
                      <PrimaryButton onClick={addSessionItem} disabled={saving || !sessionItemForm.session_id || !sessionItemForm.product_id}>Adicionar item</PrimaryButton>
                    </div>
                  </div>
                  <SessionList sessions={sessions} tables={tables} orders={orders} onClose={closeSession} onCreateOrder={createSessionOrder} onConfirmPayment={confirmSessionPayment} onDeleteItem={deleteSessionItem} />
                </Panel>
              </div>
            )}

            {tab === "customers" && (
              <Panel title="Clientes do Salao">
                {salaoCustomers.length === 0 ? (
                  <Empty text="Nenhum cliente de reserva registrado ainda." />
                ) : (
                  <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                    {salaoCustomers.map((customer) => (
                      <div key={`${customer.customer_phone}-${customer.id}`} className="rounded-xl border border-surface-03 bg-surface-01 p-4">
                        <p className="font-bold text-cream">{customer.customer_name}</p>
                        <p className="text-sm text-stone">{customer.customer_phone}</p>
                        {customer.customer_email && <p className="text-xs text-stone">{customer.customer_email}</p>}
                        <p className="mt-3 text-xs text-gold">Ultima reserva: {formatDate(customer.reservation_date)}</p>
                      </div>
                    ))}
                  </div>
                )}
              </Panel>
            )}
          </>
        )}
      </AdminPageContent>
    </AdminPageShell>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-xl border border-surface-03 bg-surface-02 p-4">
      <h2 className="mb-4 text-sm font-black uppercase tracking-[0.16em] text-cream">{title}</h2>
      {children}
    </section>
  );
}

function Input({ label, value, onChange, type = "text" }: { label: string; value: string; onChange: (value: string) => void; type?: string }) {
  return (
    <label className="grid gap-1.5">
      <span className="text-xs font-semibold text-stone">{label}</span>
      <input
        type={type}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="h-10 rounded-xl border border-surface-03 bg-surface-01 px-3 text-sm text-cream outline-none focus:border-gold"
      />
    </label>
  );
}

function Select({ label, value, onChange, children }: { label: string; value: string; onChange: (value: string) => void; children: React.ReactNode }) {
  return (
    <label className="grid gap-1.5">
      <span className="text-xs font-semibold text-stone">{label}</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="h-10 rounded-xl border border-surface-03 bg-surface-01 px-3 text-sm text-cream outline-none focus:border-gold"
      >
        {children}
      </select>
    </label>
  );
}

function PrimaryButton({ children, onClick, disabled }: { children: React.ReactNode; onClick: () => void; disabled?: boolean }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="inline-flex h-10 items-center justify-center gap-2 rounded-xl bg-gold px-4 text-sm font-black text-black transition hover:bg-gold/90 disabled:cursor-not-allowed disabled:opacity-50"
    >
      <Plus size={15} />
      {children}
    </button>
  );
}

function Empty({ text }: { text: string }) {
  return <div className="rounded-xl border border-dashed border-surface-03 bg-surface-01/60 p-8 text-center text-sm text-stone">{text}</div>;
}

function ReservationList({
  reservations,
  tables,
  onStatus,
}: {
  reservations: ApiReservation[];
  tables: ApiRestaurantTable[];
  onStatus: (reservationId: string, status: ApiReservationStatus) => void;
}) {
  if (reservations.length === 0) return <Empty text="Nenhuma reserva encontrada." />;
  const tableById = new Map(tables.map((table) => [table.id, table]));
  return (
    <div className="grid gap-3">
      {reservations.map((reservation) => (
        <div key={reservation.id} className="rounded-xl border border-surface-03 bg-surface-01 p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="font-bold text-cream">{reservation.customer_name}</p>
              <p className="text-xs text-stone">{reservation.customer_phone}</p>
            </div>
            <Badge tone={reservation.status}>{reservationStatusLabel[reservation.status]}</Badge>
          </div>
          <div className="mt-3 flex flex-wrap gap-3 text-xs text-stone">
            <span><CalendarDays size={12} className="mr-1 inline" />{formatDate(reservation.reservation_date)} {reservation.reservation_time.slice(0, 5)}</span>
            <span><Users size={12} className="mr-1 inline" />{reservation.guests_count} pessoas</span>
            <span><TableProperties size={12} className="mr-1 inline" />{reservation.table_id ? `Mesa ${tableById.get(reservation.table_id)?.number ?? "-"}` : "Sem mesa"}</span>
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            {(["confirmed", "seated", "completed", "cancelled", "no_show"] as ApiReservationStatus[]).map((status) => (
              <button key={status} onClick={() => onStatus(reservation.id, status)} className="rounded-lg border border-surface-03 px-2 py-1 text-xs text-stone hover:text-cream">
                {reservationStatusLabel[status]}
              </button>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function SessionList({
  sessions,
  tables,
  orders,
  onClose,
  onCreateOrder,
  onConfirmPayment,
  onDeleteItem,
}: {
  sessions: ApiTableSession[];
  tables: ApiRestaurantTable[];
  orders: ApiOrder[];
  onClose: (session: ApiTableSession) => void;
  onCreateOrder: (session: ApiTableSession) => void;
  onConfirmPayment: (session: ApiTableSession) => void;
  onDeleteItem: (sessionId: string, itemId: string) => void;
}) {
  if (sessions.length === 0) return <Empty text="Nenhuma comanda encontrada." />;
  const tableById = new Map(tables.map((table) => [table.id, table]));
  const orderBySessionId = new Map(orders.filter((order) => order.table_session_id).map((order) => [order.table_session_id, order]));
  return (
    <div className="grid gap-3">
      {sessions.map((session) => {
        const items = session.items ?? [];
        const canEditItems = session.status === "open";
        const linkedOrder = orderBySessionId.get(session.id);
        const paymentConfirmed = ["approved", "paid"].includes(String(linkedOrder?.payment_status ?? ""));
        return (
          <div key={session.id} className="rounded-xl border border-surface-03 bg-surface-01 p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="font-bold text-cream">Mesa {tableById.get(session.table_id)?.number ?? "-"}</p>
                <p className="text-xs text-stone"><Clock size={12} className="mr-1 inline" />Aberta em {formatDateTime(session.opened_at)}</p>
              </div>
              <Badge tone={session.status}>{sessionStatusLabel[session.status]}</Badge>
            </div>
            <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
              <p className="text-sm text-stone">Atendente: {session.waiter_name || "-"}</p>
              <p className="font-black text-gold">{formatCurrency(session.total || 0)}</p>
            </div>
            <div className="mt-3 rounded-xl border border-surface-03 bg-surface-02/60">
              {items.length === 0 ? (
                <p className="px-3 py-4 text-xs text-stone">Nenhum item na comanda.</p>
              ) : (
                <div className="divide-y divide-surface-03">
                  {items.map((item) => (
                    <div key={item.id} className="flex flex-wrap items-center justify-between gap-3 px-3 py-2">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-bold text-cream">
                          {item.quantity}x {item.product_name}
                        </p>
                        <p className="text-xs text-stone">
                          {formatCurrency(item.unit_price)}
                          {item.notes ? ` - ${item.notes}` : ""}
                        </p>
                      </div>
                      <div className="flex items-center gap-3">
                        <p className="text-sm font-black text-gold">{formatCurrency(item.total_price)}</p>
                        {canEditItems && (
                          <button
                            type="button"
                            onClick={() => onDeleteItem(session.id, item.id)}
                            className="rounded-lg border border-red-500/30 px-2 py-1 text-[11px] font-bold text-red-300 hover:bg-red-500/10"
                          >
                            Remover
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
            {["open", "pending_payment"].includes(session.status) && (
              <div className="mt-3 flex flex-wrap gap-2">
                {paymentConfirmed ? (
                  <span className="rounded-lg border border-emerald-500/25 bg-emerald-500/10 px-3 py-1.5 text-xs font-bold text-emerald-300">
                    Pagamento confirmado
                  </span>
                ) : linkedOrder ? (
                  <button
                    onClick={() => onConfirmPayment(session)}
                    className="rounded-lg border border-emerald-400/35 px-3 py-1.5 text-xs font-bold text-emerald-300 hover:bg-emerald-500/10"
                  >
                    Confirmar pagamento
                  </button>
                ) : (
                  <button
                    onClick={() => onCreateOrder(session)}
                    disabled={items.length === 0}
                    className="rounded-lg border border-blue-400/35 px-3 py-1.5 text-xs font-bold text-blue-300 hover:bg-blue-500/10 disabled:cursor-not-allowed disabled:opacity-45"
                  >
                    Gerar pedido
                  </button>
                )}
                {canEditItems && (
                  <button onClick={() => onClose(session)} className="rounded-lg border border-gold/35 px-3 py-1.5 text-xs font-bold text-gold hover:bg-gold/10">
                    Fechar sem pagamento
                  </button>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
