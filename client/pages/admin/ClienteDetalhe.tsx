import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  ArrowLeft, User, ShoppingBag, Clock, BarChart2, Phone,
  MapPin, Star, ShoppingCart, Eye, MessageSquare, Tag, Gift,
  CreditCard, Package, ChevronDown, ChevronUp, Loader2, AlertCircle,
  TrendingUp, Calendar, DollarSign, Repeat,
  type LucideIcon,
} from "lucide-react";
import { customersApi, ApiCustomer, ApiCustomerOrder, ApiCustomerEvent, ApiCustomerSummary } from "@/lib/api";

type Tab = "overview" | "orders" | "timeline" | "behavior";

const EVENT_CATEGORIES: Record<string, { label: string; icon: LucideIcon; color: string }> = {
  order: { label: "Pedido", icon: ShoppingBag, color: "text-green-400" },
  cart: { label: "Carrinho", icon: ShoppingCart, color: "text-yellow-400" },
  checkout: { label: "Checkout", icon: CreditCard, color: "text-blue-400" },
  product: { label: "Produto", icon: Package, color: "text-purple-400" },
  navigation: { label: "Navegação", icon: Eye, color: "text-stone/60" },
  campaign: { label: "Campanha", icon: Star, color: "text-orange-400" },
  coupon: { label: "Cupom", icon: Tag, color: "text-pink-400" },
  loyalty: { label: "Fidelidade", icon: Gift, color: "text-gold" },
  chatbot: { label: "Chatbot", icon: MessageSquare, color: "text-sky-400" },
  customer: { label: "Cliente", icon: User, color: "text-cream" },
};

function getEventCategory(eventType: string): keyof typeof EVENT_CATEGORIES {
  if (eventType.startsWith("order_")) return "order";
  if (eventType.startsWith("cart_")) return "cart";
  if (eventType.startsWith("checkout_")) return "checkout";
  if (eventType.startsWith("product_")) return "product";
  if (eventType.startsWith("campaign_")) return "campaign";
  if (eventType.startsWith("coupon_")) return "coupon";
  if (eventType.startsWith("loyalty_")) return "loyalty";
  if (eventType.startsWith("chatbot_")) return "chatbot";
  if (eventType.startsWith("customer_")) return "customer";
  return "navigation";
}

function EventIcon({ eventType, size = 16 }: { eventType: string; size?: number }) {
  const cat = getEventCategory(eventType);
  const config = EVENT_CATEGORIES[cat];
  const Icon = config.icon;
  return <Icon size={size} className={config.color} />;
}

function StatCard({ label, value, sub, icon: Icon, color = "text-gold" }: {
  label: string; value: string | number; sub?: string;
  icon: LucideIcon; color?: string;
}) {
  return (
    <div className="bg-surface-02 rounded-xl p-4 border border-surface-03 flex items-start gap-3">
      <div className={`mt-0.5 ${color}`}><Icon size={20} /></div>
      <div>
        <p className="text-stone/60 text-xs mb-0.5">{label}</p>
        <p className="text-parchment font-semibold text-lg leading-tight">{value}</p>
        {sub && <p className="text-stone/50 text-xs mt-0.5">{sub}</p>}
      </div>
    </div>
  );
}

function OrderCard({ order }: { order: ApiCustomerOrder }) {
  const [expanded, setExpanded] = useState(false);
  const statusColors: Record<string, string> = {
    pending: "bg-yellow-500/20 text-yellow-400",
    confirmed: "bg-blue-500/20 text-blue-400",
    preparing: "bg-orange-500/20 text-orange-400",
    ready: "bg-purple-500/20 text-purple-400",
    delivering: "bg-sky-500/20 text-sky-400",
    delivered: "bg-green-500/20 text-green-400",
    paid: "bg-green-500/20 text-green-400",
    cancelled: "bg-red-500/20 text-red-400",
  };
  const statusLabels: Record<string, string> = {
    pending: "Pendente", confirmed: "Confirmado", preparing: "Preparando",
    ready: "Pronto", delivering: "Entregando", delivered: "Entregue",
    paid: "Pago", cancelled: "Cancelado",
  };
  const date = new Date(order.created_at);
  const dateStr = date.toLocaleDateString("pt-BR", { day: "2-digit", month: "short", year: "numeric" });
  const timeStr = date.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
  const deliveryAddress = [order.delivery_street, order.delivery_complement, order.delivery_city]
    .filter(Boolean)
    .join(" - ");

  return (
    <div className="bg-surface-02 rounded-xl border border-surface-03 overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full px-4 py-3 flex items-center justify-between hover:bg-surface-03/50 transition-colors"
      >
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-surface-03 flex items-center justify-center">
            <ShoppingBag size={14} className="text-gold" />
          </div>
          <div className="text-left">
            <p className="text-parchment text-sm font-medium">
              Pedido #{order.id.slice(-6).toUpperCase()}
            </p>
            <p className="text-stone/50 text-xs">{dateStr} às {timeStr}</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${statusColors[order.status] ?? "bg-surface-03 text-stone/60"}`}>
            {statusLabels[order.status] ?? order.status}
          </span>
          <span className="text-parchment text-sm font-semibold">
            R$ {(order.total ?? 0).toFixed(2).replace(".", ",")}
          </span>
          {expanded ? <ChevronUp size={14} className="text-stone/40" /> : <ChevronDown size={14} className="text-stone/40" />}
        </div>
      </button>
      {expanded && (
        <div className="px-4 pb-4 pt-1 border-t border-surface-03 space-y-3">
          {order.items && order.items.length > 0 && (
            <div className="space-y-1.5">
              {order.items.map((item: any, i: number) => (
                <div key={i} className="flex items-start justify-between gap-2">
                  <div className="flex-1">
                    <span className="text-parchment text-sm">
                      {item.quantity}x {item.product_name ?? item.name ?? "Produto"}
                    </span>
                    {item.flavors && item.flavors.length > 0 && (
                      <p className="text-stone/50 text-xs">{item.flavors.map((f: any) => f.name ?? f).join(", ")}</p>
                    )}
                  </div>
                  <span className="text-stone/60 text-sm flex-shrink-0">
                    R$ {((item.unit_price ?? item.price ?? 0) * (item.quantity ?? 1)).toFixed(2).replace(".", ",")}
                  </span>
                </div>
              ))}
            </div>
          )}
          <div className="flex flex-wrap gap-x-4 gap-y-1 pt-1 border-t border-surface-03/50 text-xs text-stone/50">
            {deliveryAddress && (
              <span className="flex items-center gap-1">
                <MapPin size={11} /> {deliveryAddress}
              </span>
            )}
            {order.payment_status && (
              <span className="flex items-center gap-1">
                <CreditCard size={11} /> {order.payment_status}
              </span>
            )}
            {order.coupon_id && (
              <span className="flex items-center gap-1">
                <Tag size={11} /> Cupom aplicado
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

const FILTER_OPTIONS = [
  { key: "", label: "Todos" },
  { key: "order", label: "Pedidos" },
  { key: "cart", label: "Carrinho" },
  { key: "checkout", label: "Checkout" },
  { key: "navigation", label: "Navegação" },
  { key: "campaign", label: "Campanhas" },
  { key: "coupon", label: "Cupons" },
  { key: "chatbot", label: "Chatbot" },
  { key: "customer", label: "Cliente" },
];

function behaviorStatusConfig(status: string) {
  const configs: Record<string, { label: string; color: string; description: string }> = {
    recorrente: { label: "Recorrente", color: "bg-green-500/20 text-green-400", description: "5+ pedidos realizados" },
    ativo: { label: "Ativo", color: "bg-blue-500/20 text-blue-400", description: "2+ pedidos realizados" },
    novo_comprador: { label: "Novo Comprador", color: "bg-purple-500/20 text-purple-400", description: "Primeiro pedido" },
    interessado: { label: "Interessado", color: "bg-yellow-500/20 text-yellow-400", description: "Interagiu mas não comprou" },
    visitante: { label: "Visitante", color: "bg-stone/20 text-stone/60", description: "Visitou a loja" },
    lead: { label: "Lead", color: "bg-orange-500/20 text-orange-400", description: "Cadastrado" },
  };
  return configs[status] ?? { label: status, color: "bg-surface-03 text-stone/60", description: "" };
}

export default function ClienteDetalhe() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [tab, setTab] = useState<Tab>("overview");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [customer, setCustomer] = useState<ApiCustomer | null>(null);
  const [orders, setOrders] = useState<ApiCustomerOrder[]>([]);
  const [events, setEvents] = useState<ApiCustomerEvent[]>([]);
  const [summary, setSummary] = useState<ApiCustomerSummary | null>(null);

  const [eventFilter, setEventFilter] = useState("");

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    setError(null);
    Promise.allSettled([
      customersApi.get(id),
      customersApi.getOrders(id),
      customersApi.getEvents(id),
      customersApi.getSummary(id),
    ]).then(([c, o, e, s]) => {
      if (c.status === "fulfilled") setCustomer(c.value as ApiCustomer);
      else setError("Não foi possível carregar o cliente.");
      if (o.status === "fulfilled") setOrders(o.value as ApiCustomerOrder[]);
      if (e.status === "fulfilled") setEvents(e.value as ApiCustomerEvent[]);
      if (s.status === "fulfilled") setSummary(s.value as ApiCustomerSummary);
    }).finally(() => setLoading(false));
  }, [id]);

  const filteredEvents = eventFilter
    ? events.filter(ev => getEventCategory(ev.event_type) === eventFilter)
    : events;

  const tabs: { key: Tab; label: string; icon: LucideIcon }[] = [
    { key: "overview", label: "Visão Geral", icon: BarChart2 },
    { key: "orders", label: "Pedidos", icon: ShoppingBag },
    { key: "timeline", label: "Linha do Tempo", icon: Clock },
    { key: "behavior", label: "Comportamento", icon: TrendingUp },
  ];

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 size={28} className="animate-spin text-gold" />
      </div>
    );
  }

  if (error || !customer) {
    return (
      <div className="p-6">
        <button onClick={() => navigate(-1)} className="flex items-center gap-2 text-stone/60 hover:text-parchment mb-6 transition-colors text-sm">
          <ArrowLeft size={16} /> Voltar
        </button>
        <div className="flex items-center gap-3 text-red-400">
          <AlertCircle size={20} />
          <p>{error ?? "Cliente não encontrado."}</p>
        </div>
      </div>
    );
  }

  const behaviorStatus = summary?.behavior.status ?? "visitante";
  const bsConfig = behaviorStatusConfig(behaviorStatus);
  const joinDate = new Date(customer.created_at ?? "").toLocaleDateString("pt-BR", { day: "2-digit", month: "long", year: "numeric" });
  const defaultAddress = customer.addresses?.find((address) => address.is_default) ?? customer.addresses?.[0];
  const addressText = defaultAddress
    ? [defaultAddress.street, defaultAddress.number, defaultAddress.neighborhood, defaultAddress.city]
        .filter(Boolean)
        .join(", ")
    : null;
  const loyaltyPoints = (customer as ApiCustomer & { loyalty_points?: number | null }).loyalty_points;
  const totalOrders = summary?.orders.total ?? 0;
  const totalSpent = summary?.orders.total_spent ?? 0;
  const averageTicket = summary?.orders.avg_ticket ?? 0;
  const lastOrderAt = summary?.orders.last_order_at ?? null;
  const productViews = summary?.behavior.products_viewed ?? 0;
  const cartEvents = summary?.behavior.cart_abandonments ?? 0;
  const checkoutEvents = summary?.behavior.checkout_abandonments ?? 0;
  const campaignEvents = events.filter((event) => getEventCategory(event.event_type) === "campaign").length;
  const couponEvents = events.filter((event) => getEventCategory(event.event_type) === "coupon").length;
  const cancelledOrders = summary?.orders.cancelled ?? 0;

  return (
    <div className="max-w-4xl mx-auto p-4 md:p-6 space-y-6">
      <div>
        <button
          onClick={() => navigate(-1)}
          className="flex items-center gap-1.5 text-stone/60 hover:text-parchment transition-colors text-sm"
        >
          <ArrowLeft size={16} /> Clientes
        </button>
      </div>

      <div className="bg-surface-02 rounded-2xl border border-surface-03 p-5 flex flex-col sm:flex-row items-start sm:items-center gap-4">
        <div className="w-14 h-14 rounded-2xl bg-surface-03 flex items-center justify-center flex-shrink-0">
          <User size={24} className="text-stone/60" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h1 className="text-parchment text-xl font-bold truncate">{customer.name || "Sem nome"}</h1>
            <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${bsConfig.color}`}>
              {bsConfig.label}
            </span>
          </div>
          <div className="flex flex-wrap gap-x-4 gap-y-1 mt-1.5">
            {customer.phone && (
              <span className="flex items-center gap-1.5 text-stone/60 text-sm">
                <Phone size={13} /> {customer.phone}
              </span>
            )}
            {addressText && (
              <span className="flex items-center gap-1.5 text-stone/60 text-sm">
                <MapPin size={13} /> {addressText}
              </span>
            )}
            <span className="flex items-center gap-1.5 text-stone/50 text-xs">
              <Calendar size={12} /> Cliente desde {joinDate}
            </span>
          </div>
        </div>
        {loyaltyPoints !== undefined && loyaltyPoints !== null && (
          <div className="flex items-center gap-2 bg-gold/10 px-4 py-2 rounded-xl border border-gold/20">
            <Gift size={16} className="text-gold" />
            <div>
              <p className="text-gold font-bold text-lg leading-tight">{loyaltyPoints}</p>
              <p className="text-gold/70 text-xs">pontos</p>
            </div>
          </div>
        )}
      </div>

      <div className="flex gap-1 bg-surface-02 rounded-xl p-1 border border-surface-03">
        {tabs.map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`flex-1 flex items-center justify-center gap-1.5 py-2 rounded-lg text-sm font-medium transition-colors ${
              tab === key ? "bg-brand-mid text-parchment" : "text-stone/60 hover:text-parchment"
            }`}
          >
            <Icon size={14} />
            <span className="hidden sm:inline">{label}</span>
          </button>
        ))}
      </div>

      {tab === "overview" && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <StatCard label="Total de pedidos" value={totalOrders} icon={ShoppingBag} color="text-green-400" />
            <StatCard label="Ticket médio" value={`R$ ${averageTicket.toFixed(2).replace(".", ",")}`} icon={DollarSign} color="text-gold" />
            <StatCard label="Total gasto" value={`R$ ${totalSpent.toFixed(2).replace(".", ",")}`} icon={TrendingUp} color="text-blue-400" />
            <StatCard
              label="Último pedido"
              value={lastOrderAt ? new Date(lastOrderAt).toLocaleDateString("pt-BR", { day: "2-digit", month: "short" }) : "—"}
              icon={Calendar}
              color="text-purple-400"
            />
          </div>
          {summary && (
            <div className="bg-surface-02 rounded-xl border border-surface-03 p-4">
              <h3 className="text-parchment font-medium mb-3">Status Comportamental</h3>
              <div className="flex items-start gap-3">
                <span className={`px-3 py-1 rounded-full text-sm font-medium ${bsConfig.color}`}>{bsConfig.label}</span>
                <p className="text-stone/60 text-sm mt-0.5">{bsConfig.description}</p>
              </div>
            </div>
          )}
          {summary && (
            <div className="bg-surface-02 rounded-xl border border-surface-03 p-4 space-y-3">
              <h3 className="text-parchment font-medium">Resumo de Atividade</h3>
              <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
                {[
                  { label: "Visualizações de produto", value: productViews },
                  { label: "Carrinhos abandonados", value: cartEvents },
                  { label: "Checkouts abandonados", value: checkoutEvents },
                  { label: "Interações com campanhas", value: campaignEvents },
                  { label: "Eventos de cupom", value: couponEvents },
                  { label: "Pedidos cancelados", value: cancelledOrders },
                ].map(({ label, value }) => (
                  <div key={label} className="flex justify-between items-center">
                    <span className="text-stone/60">{label}</span>
                    <span className="text-parchment font-medium">{value}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {tab === "orders" && (
        <div className="space-y-3">
          {orders.length === 0 ? (
            <div className="text-center py-12 text-stone/40">
              <ShoppingBag size={32} className="mx-auto mb-2 opacity-40" />
              <p>Nenhum pedido encontrado</p>
            </div>
          ) : (
            orders.map(order => <OrderCard key={order.id} order={order} />)
          )}
        </div>
      )}

      {tab === "timeline" && (
        <div className="space-y-4">
          <div className="flex flex-wrap gap-2">
            {FILTER_OPTIONS.map(({ key, label }) => (
              <button
                key={key}
                onClick={() => setEventFilter(key)}
                className={`px-3 py-1 rounded-full text-xs font-medium transition-colors border ${
                  eventFilter === key
                    ? "bg-brand-mid text-parchment border-brand-mid"
                    : "border-surface-03 text-stone/60 hover:text-parchment"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
          {filteredEvents.length === 0 ? (
            <div className="text-center py-12 text-stone/40">
              <Clock size={32} className="mx-auto mb-2 opacity-40" />
              <p>Nenhum evento{eventFilter ? " nessa categoria" : ""}</p>
            </div>
          ) : (
            <div className="relative pl-6">
              <div className="absolute left-2 top-0 bottom-0 w-px bg-surface-03" />
              <div className="space-y-3">
                {filteredEvents.map((ev, i) => {
                  const evDate = new Date(ev.created_at);
                  return (
                    <div key={ev.id ?? i} className="relative">
                      <div className="absolute -left-4 top-3 w-2 h-2 rounded-full bg-surface-03 border border-surface-02" />
                      <div className="bg-surface-02 rounded-xl border border-surface-03 p-3 ml-2">
                        <div className="flex items-start justify-between gap-2">
                          <div className="flex items-center gap-2">
                            <EventIcon eventType={ev.event_type} size={14} />
                            <span className="text-parchment text-sm font-medium">{ev.event_name ?? ev.event_type}</span>
                          </div>
                          <span className="text-stone/40 text-xs flex-shrink-0">
                            {evDate.toLocaleDateString("pt-BR", { day: "2-digit", month: "short" })} {evDate.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}
                          </span>
                        </div>
                        {ev.event_description && <p className="text-stone/60 text-xs mt-1">{ev.event_description}</p>}
                        {(ev.source || ev.device_type) && (
                          <div className="flex gap-3 mt-1.5">
                            {ev.source && <span className="text-stone/40 text-xs">{ev.source}</span>}
                            {ev.device_type && <span className="text-stone/40 text-xs">{ev.device_type}</span>}
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}

      {tab === "behavior" && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            {[
              { label: "Visualizações", value: productViews, icon: Eye, color: "text-purple-400" },
              { label: "Carrinhos", value: cartEvents, icon: ShoppingCart, color: "text-yellow-400" },
              { label: "Checkouts", value: checkoutEvents, icon: CreditCard, color: "text-blue-400" },
              { label: "Campanhas", value: campaignEvents, icon: Star, color: "text-orange-400" },
              { label: "Cupons", value: couponEvents, icon: Tag, color: "text-pink-400" },
              { label: "Total de eventos", value: events.length, icon: Repeat, color: "text-gold" },
            ].map(stat => (
              <StatCard key={stat.label} label={stat.label} value={stat.value} icon={stat.icon} color={stat.color} />
            ))}
          </div>
          {summary && totalOrders > 0 && (
            <div className="bg-surface-02 rounded-xl border border-surface-03 p-4 space-y-3">
              <h3 className="text-parchment font-medium">Taxa de Conversão</h3>
              {cartEvents > 0 && (
                <div>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-stone/60">Carrinho → Pedido</span>
                    <span className="text-parchment font-medium">{Math.min(100, Math.round((totalOrders / cartEvents) * 100))}%</span>
                  </div>
                  <div className="h-1.5 bg-surface-03 rounded-full overflow-hidden">
                    <div className="h-full bg-green-500 rounded-full" style={{ width: `${Math.min(100, Math.round((totalOrders / cartEvents) * 100))}%` }} />
                  </div>
                </div>
              )}
              {checkoutEvents > 0 && (
                <div>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-stone/60">Checkout → Pedido</span>
                    <span className="text-parchment font-medium">{Math.min(100, Math.round((totalOrders / checkoutEvents) * 100))}%</span>
                  </div>
                  <div className="h-1.5 bg-surface-03 rounded-full overflow-hidden">
                    <div className="h-full bg-blue-500 rounded-full" style={{ width: `${Math.min(100, Math.round((totalOrders / checkoutEvents) * 100))}%` }} />
                  </div>
                </div>
              )}
            </div>
          )}
          {loyaltyPoints !== undefined && loyaltyPoints !== null && (
            <div className="bg-gold/10 rounded-xl border border-gold/20 p-4 flex items-center gap-4">
              <Gift size={24} className="text-gold flex-shrink-0" />
              <div>
                <p className="text-parchment font-semibold">{loyaltyPoints} pontos de fidelidade</p>
                <p className="text-gold/70 text-sm">Acumulados no programa de fidelidade</p>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
