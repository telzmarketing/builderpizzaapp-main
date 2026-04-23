import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  ChevronLeft, Star, Gift, Trophy, Users, RefreshCw,
  Share2, CheckCircle, Clock, ChevronRight,
} from "lucide-react";
import MoschettieriLogo from "@/components/MoschettieriLogo";
import { useApp } from "@/context/AppContext";
import {
  loyaltyApi,
  ApiCustomerLoyalty, ApiLoyaltyLevel, ApiLoyaltyBenefit,
  ApiReferral,
} from "@/lib/api";

const colorPalette: Record<string, { color: string; bg: string; border: string; gradient: string }> = {
  orange: { color: "text-orange-300",  bg: "bg-orange-400/20",  border: "border-orange-400",  gradient: "from-orange-500 to-orange-700" },
  gray:   { color: "text-slate-300",   bg: "bg-slate-400/20",   border: "border-slate-400",    gradient: "from-slate-500 to-slate-700"  },
  yellow: { color: "text-yellow-300",  bg: "bg-yellow-400/20",  border: "border-yellow-400",   gradient: "from-yellow-500 to-yellow-700" },
  blue:   { color: "text-blue-300",    bg: "bg-blue-400/20",    border: "border-blue-400",     gradient: "from-blue-500 to-blue-700"   },
  green:  { color: "text-green-300",   bg: "bg-green-400/20",   border: "border-green-400",    gradient: "from-green-500 to-green-700"  },
  purple: { color: "text-purple-300",  bg: "bg-purple-400/20",  border: "border-purple-400",   gradient: "from-purple-500 to-purple-700"},
};

const BENEFIT_ICONS: Record<string, string> = {
  product: "🎁",
  discount: "🏷️",
  frete_gratis: "🛵",
  experience: "✨",
};

export default function Fidelidade() {
  const navigate = useNavigate();
  const { customer } = useApp();

  const [account, setAccount] = useState<ApiCustomerLoyalty | null>(null);
  const [levels, setLevels] = useState<ApiLoyaltyLevel[]>([]);
  const [benefits, setBenefits] = useState<ApiLoyaltyBenefit[]>([]);
  const [referral, setReferral] = useState<ApiReferral | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<"overview" | "benefits" | "history" | "referral">("overview");

  useEffect(() => {
    loadData();
  }, [customer?.id]);

  async function loadData() {
    setLoading(true);
    try {
      const [lvls] = await Promise.all([loyaltyApi.levels()]);
      setLevels(lvls);
      if (customer?.id) {
        const [acc, ref] = await Promise.all([
          loyaltyApi.account(customer.id),
          loyaltyApi.getReferral(customer.id),
        ]);
        setAccount(acc);
        setBenefits(acc.benefits ?? []);
        setReferral(ref);
      }
    } catch {
      // silently fail — show empty state
    } finally {
      setLoading(false);
    }
  }

  const sortedLevels = [...levels].sort((a, b) => a.min_points - b.min_points);
  const totalPoints = account?.total_points ?? 0;
  const currentLevel = account?.level ?? null;
  const nextLevel = sortedLevels.find(l => l.min_points > totalPoints);
  const progressToNext = nextLevel && currentLevel
    ? Math.min(100, ((totalPoints - currentLevel.min_points) / (nextLevel.min_points - currentLevel.min_points)) * 100)
    : currentLevel ? 100 : 0;

  const cp = colorPalette[currentLevel?.color ?? "orange"] ?? colorPalette.orange;

  const cycleEnd = account?.cycle_end_date ? new Date(account.cycle_end_date) : null;
  const daysLeft = cycleEnd
    ? Math.max(0, Math.ceil((cycleEnd.getTime() - Date.now()) / 86400000))
    : null;

  function copyReferral() {
    if (!referral) return;
    navigator.clipboard.writeText(referral.referral_code).then(() => {
      alert(`Código copiado: ${referral.referral_code}`);
    });
  }

  if (!customer) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-surface-01 to-surface-00 flex flex-col items-center justify-center gap-4 px-8">
        <Trophy size={48} className="text-gold" />
        <p className="text-cream text-xl font-bold text-center">Faça login para ver sua fidelidade</p>
        <button onClick={() => navigate("/")} className="px-6 py-3 bg-gold text-cream rounded-xl font-semibold">
          Voltar ao início
        </button>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-surface-01 to-surface-00">
      {/* Header */}
      <div className="bg-surface-02 px-4 py-4 flex justify-between items-center sticky top-0 z-30 border-b border-surface-03">
        <button onClick={() => navigate(-1)} className="text-parchment hover:text-cream transition-colors">
          <ChevronLeft size={24} />
        </button>
        <MoschettieriLogo className="text-cream text-base" />
        <button onClick={loadData} className="text-stone hover:text-gold"><RefreshCw size={18} /></button>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-64 text-stone text-sm">Carregando...</div>
      ) : (
        <div className="pb-32">
          {/* Hero — points card */}
          <div className={`bg-gradient-to-br ${cp.gradient} p-6 text-center`}>
            <p className="text-white/70 text-sm mb-1">Seus pontos</p>
            <p className="text-white text-6xl font-black mb-1">{totalPoints}</p>
            <div className="flex items-center justify-center gap-2 mb-4">
              <span className="text-2xl">{currentLevel?.icon ?? "🏆"}</span>
              <p className="text-white font-bold text-lg">{currentLevel?.name ?? "Sem nível"}</p>
            </div>

            {/* Cycle countdown */}
            {daysLeft !== null && (
              <div className="inline-flex items-center gap-1.5 bg-black/20 rounded-full px-3 py-1 text-white/80 text-xs mb-4">
                <Clock size={12} />
                {daysLeft > 0 ? `Ciclo encerra em ${daysLeft} dia(s)` : "Ciclo encerrando hoje!"}
              </div>
            )}

            {/* Progress bar to next level */}
            {nextLevel && (
              <div className="mt-3">
                <div className="flex justify-between text-white/70 text-xs mb-1">
                  <span>{totalPoints} pts</span>
                  <span>{nextLevel.icon} {nextLevel.name} ({nextLevel.min_points} pts)</span>
                </div>
                <div className="h-2 bg-white/20 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-white rounded-full transition-all duration-700"
                    style={{ width: `${progressToNext}%` }}
                  />
                </div>
                <p className="text-white/60 text-xs mt-1">
                  Faltam {nextLevel.min_points - totalPoints} pts para {nextLevel.name}
                </p>
              </div>
            )}
            {!nextLevel && currentLevel && (
              <p className="text-white/70 text-sm mt-2">🎉 Você está no nível máximo!</p>
            )}

            {/* Rollover info */}
            {account && account.rollover_points > 0 && (
              <div className="mt-3 bg-black/20 rounded-xl px-4 py-2 text-white/80 text-xs">
                {account.rollover_points} pts vieram do ciclo anterior (rollover 50%)
              </div>
            )}
          </div>

          {/* Tabs */}
          <div className="bg-surface-02 border-b border-surface-03 px-4 flex gap-1">
            {([
              ["overview",  "Visão Geral", Star],
              ["benefits",  "Benefícios",  Gift],
              ["history",   "Histórico",   Clock],
              ["referral",  "Indicar",     Users],
            ] as ["overview" | "benefits" | "history" | "referral", string, React.ElementType][]).map(([key, label, Icon]) => (
              <button
                key={key}
                onClick={() => setActiveTab(key)}
                className={`flex items-center gap-1.5 px-3 py-3 text-xs font-medium border-b-2 transition-colors flex-1 justify-center ${
                  activeTab === key ? "border-gold text-gold" : "border-transparent text-stone"
                }`}
              >
                <Icon size={14} /> {label}
              </button>
            ))}
          </div>

          <div className="px-4 pt-5 space-y-4">
            {/* ── Overview ─────────────────────────────────────────────── */}
            {activeTab === "overview" && (
              <>
                {/* Stats grid */}
                <div className="grid grid-cols-2 gap-3">
                  <StatCard label="Pontos totais" value={totalPoints.toString()} icon="⭐" />
                  <StatCard label="Pontos vitalícios" value={(account?.lifetime_points ?? 0).toString()} icon="🏆" />
                  <StatCard label="Rollover acumulado" value={(account?.rollover_points ?? 0).toString()} icon="🔄" />
                  <StatCard label="Ciclos completos" value={(account?.cycles?.filter(c => c.status === "closed").length ?? 0).toString()} icon="📅" />
                </div>

                {/* Level ladder */}
                <div className="bg-surface-02 rounded-2xl border border-surface-03 p-5">
                  <p className="text-cream font-bold text-sm mb-4">Escada de Níveis</p>
                  <div className="space-y-3">
                    {sortedLevels.map(level => {
                      const lcp = colorPalette[level.color] ?? colorPalette.orange;
                      const isCurrentLevel = currentLevel?.id === level.id;
                      const isUnlocked = totalPoints >= level.min_points;
                      return (
                        <div
                          key={level.id}
                          className={`flex items-center gap-4 rounded-xl px-4 py-3 border transition-all ${
                            isCurrentLevel
                              ? `${lcp.bg} ${lcp.border}`
                              : "border-surface-03 bg-surface-03/30"
                          }`}
                        >
                          <span className="text-2xl">{level.icon}</span>
                          <div className="flex-1">
                            <p className={`font-bold text-sm ${isCurrentLevel ? lcp.color : isUnlocked ? "text-parchment" : "text-stone"}`}>
                              {level.name}
                            </p>
                            <p className="text-stone text-xs">{level.min_points}+ pts</p>
                          </div>
                          {isCurrentLevel && (
                            <span className="text-xs font-semibold bg-white/10 text-white px-2 py-0.5 rounded-full">
                              Atual
                            </span>
                          )}
                          {isUnlocked && !isCurrentLevel && (
                            <CheckCircle size={16} className="text-green-400" />
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* How to earn */}
                <div className="bg-surface-02 rounded-2xl border border-surface-03 p-5">
                  <p className="text-cream font-bold text-sm mb-3">Como Ganhar Pontos</p>
                  <div className="space-y-2">
                    <EarnRow icon="🛵" label="Pedido entregue" pts="+10 pts" />
                    <EarnRow icon="💸" label="A cada R$1 gasto" pts="+1 pt" />
                    <EarnRow icon="⭐" label="Primeiro pedido" pts="+50 pts" />
                    <EarnRow icon="👥" label="Indicação aceita" pts="+10 pts" />
                  </div>
                </div>

                {/* Rollover explanation */}
                <div className="bg-surface-03/50 rounded-xl p-4 text-xs text-stone space-y-1">
                  <p className="text-parchment font-semibold">ℹ️ Como funciona o ciclo mensal</p>
                  <p>A cada 30 dias, seu ciclo é encerrado. 50% dos pontos restantes são rolados para o próximo ciclo e 50% expiram. Isso mantém o programa dinâmico!</p>
                </div>
              </>
            )}

            {/* ── Benefits ─────────────────────────────────────────────── */}
            {activeTab === "benefits" && (
              <>
                {benefits.length === 0 ? (
                  <div className="text-center text-stone text-sm py-12">
                    <Gift size={40} className="mx-auto mb-3 opacity-40" />
                    <p>Nenhum benefício disponível no seu nível atual.</p>
                    <p className="text-xs mt-1">Continue acumulando pontos para desbloquear!</p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {benefits.map(b => {
                      const levelInfo = levels.find(l => l.id === b.level_id);
                      const lcp = colorPalette[levelInfo?.color ?? "orange"] ?? colorPalette.orange;
                      return (
                        <div key={b.id} className={`bg-surface-02 rounded-2xl border ${lcp.border} p-4`}>
                          <div className="flex items-start gap-3">
                            <span className="text-2xl">{BENEFIT_ICONS[b.benefit_type]}</span>
                            <div className="flex-1">
                              <p className="text-cream font-bold text-sm">{b.label}</p>
                              {b.description && <p className="text-stone text-xs mt-0.5">{b.description}</p>}
                              <div className="flex flex-wrap gap-2 mt-2">
                                {b.value > 0 && (
                                  <span className="text-xs bg-surface-03 text-parchment px-2 py-0.5 rounded-full">
                                    {b.benefit_type === "discount" ? `${b.value}%` : `R$ ${b.value.toFixed(2)}`}
                                  </span>
                                )}
                                {b.min_order_value > 0 && (
                                  <span className="text-xs bg-surface-03 text-stone px-2 py-0.5 rounded-full">
                                    Min R${b.min_order_value.toFixed(2)}
                                  </span>
                                )}
                                <span className="text-xs bg-surface-03 text-stone px-2 py-0.5 rounded-full">
                                  {b.usage_limit}x/ciclo
                                </span>
                                <span className={`text-xs px-2 py-0.5 rounded-full ${lcp.bg} ${lcp.color}`}>
                                  {levelInfo?.name}
                                </span>
                              </div>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </>
            )}

            {/* ── History ──────────────────────────────────────────────── */}
            {activeTab === "history" && (
              <>
                {/* Cycles */}
                {account?.cycles && account.cycles.length > 0 && (
                  <div className="bg-surface-02 rounded-2xl border border-surface-03 p-5">
                    <p className="text-cream font-bold text-sm mb-3">Ciclos Mensais</p>
                    <div className="space-y-3">
                      {account.cycles.map(cycle => (
                        <div key={cycle.id} className="bg-surface-03/50 rounded-xl p-3">
                          <div className="flex items-center justify-between mb-2">
                            <p className="text-parchment text-xs font-medium">
                              {new Date(cycle.start_date).toLocaleDateString("pt-BR")} → {new Date(cycle.end_date).toLocaleDateString("pt-BR")}
                            </p>
                            <span className={`text-xs px-2 py-0.5 rounded-full ${cycle.status === "active" ? "bg-green-500/20 text-green-400" : "bg-surface-03 text-stone"}`}>
                              {cycle.status === "active" ? "Ativo" : "Encerrado"}
                            </span>
                          </div>
                          <div className="grid grid-cols-3 gap-2 text-xs">
                            <div className="text-center">
                              <p className="text-green-400 font-bold">+{cycle.points_earned}</p>
                              <p className="text-stone">Ganhos</p>
                            </div>
                            <div className="text-center">
                              <p className="text-blue-400 font-bold">→{cycle.points_rolled_over}</p>
                              <p className="text-stone">Rollover</p>
                            </div>
                            <div className="text-center">
                              <p className="text-red-400 font-bold">-{cycle.points_expired}</p>
                              <p className="text-stone">Expirados</p>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Transactions */}
                <div className="bg-surface-02 rounded-2xl border border-surface-03 p-5">
                  <p className="text-cream font-bold text-sm mb-3">Últimas Transações</p>
                  {!account?.transactions || account.transactions.length === 0 ? (
                    <p className="text-stone text-xs text-center py-4">Nenhuma transação ainda.</p>
                  ) : (
                    <div className="space-y-2">
                      {account.transactions.slice(0, 20).map(tx => (
                        <div key={tx.id} className="flex items-center gap-3 py-2 border-b border-surface-03 last:border-0">
                          <span className={`text-base font-bold w-14 text-right flex-shrink-0 ${tx.points > 0 ? "text-green-400" : "text-red-400"}`}>
                            {tx.points > 0 ? "+" : ""}{tx.points}
                          </span>
                          <p className="flex-1 text-stone text-xs">{tx.description ?? tx.transaction_type}</p>
                          <p className="text-stone/60 text-xs">{new Date(tx.created_at).toLocaleDateString("pt-BR")}</p>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </>
            )}

            {/* ── Referral ─────────────────────────────────────────────── */}
            {activeTab === "referral" && (
              <>
                <div className="bg-gradient-to-br from-blue-600/30 to-blue-800/30 rounded-2xl border border-blue-500/30 p-6 text-center">
                  <Users size={40} className="text-blue-400 mx-auto mb-3" />
                  <p className="text-cream font-bold text-lg mb-1">Indique amigos</p>
                  <p className="text-stone text-sm mb-4">Você e seu amigo ganham +10 pontos cada quando ele se cadastrar!</p>

                  {referral ? (
                    <>
                      <div className="bg-surface-02 rounded-xl p-4 mb-4">
                        <p className="text-stone text-xs mb-1">Seu código de indicação</p>
                        <p className="text-cream text-3xl font-black tracking-widest">{referral.referral_code}</p>
                      </div>
                      <button
                        onClick={copyReferral}
                        className="flex items-center gap-2 mx-auto px-6 py-3 bg-blue-500 text-white rounded-xl font-semibold text-sm hover:bg-blue-600"
                      >
                        <Share2 size={16} /> Copiar código
                      </button>
                    </>
                  ) : (
                    <p className="text-stone text-sm">Carregando seu código...</p>
                  )}
                </div>

                <div className="bg-surface-02 rounded-2xl border border-surface-03 p-5">
                  <p className="text-cream font-bold text-sm mb-3">Como funciona</p>
                  <div className="space-y-3">
                    <Step n={1} label="Compartilhe seu código com um amigo" />
                    <Step n={2} label="Seu amigo se cadastra usando o código" />
                    <Step n={3} label="Vocês dois ganham +10 pontos de fidelidade" />
                  </div>
                </div>

                {referral && (
                  <div className="bg-surface-02 rounded-2xl border border-surface-03 p-4">
                    <p className="text-stone text-xs">Status da indicação: <span className={`font-medium ${referral.status === "completed" ? "text-green-400" : "text-stone"}`}>{referral.status === "completed" ? "Completada" : "Aguardando"}</span></p>
                    {referral.status === "completed" && referral.completed_at && (
                      <p className="text-stone text-xs mt-1">Completada em {new Date(referral.completed_at).toLocaleDateString("pt-BR")}</p>
                    )}
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function StatCard({ label, value, icon }: { label: string; value: string; icon: string }) {
  return (
    <div className="bg-surface-02 rounded-xl border border-surface-03 p-4 text-center">
      <span className="text-2xl">{icon}</span>
      <p className="text-cream font-black text-xl mt-1">{value}</p>
      <p className="text-stone text-xs">{label}</p>
    </div>
  );
}

function EarnRow({ icon, label, pts }: { icon: string; label: string; pts: string }) {
  return (
    <div className="flex items-center gap-3">
      <span className="text-xl">{icon}</span>
      <p className="text-parchment text-sm flex-1">{label}</p>
      <span className="text-gold font-bold text-sm">{pts}</span>
    </div>
  );
}

function Step({ n, label }: { n: number; label: string }) {
  return (
    <div className="flex items-center gap-3">
      <div className="w-7 h-7 rounded-full bg-blue-500/20 text-blue-400 flex items-center justify-center text-xs font-bold flex-shrink-0">{n}</div>
      <p className="text-parchment text-sm">{label}</p>
    </div>
  );
}
