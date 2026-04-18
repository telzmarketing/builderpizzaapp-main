import { useNavigate } from "react-router-dom";
import { ChevronLeft, Star, Gift, Zap, Trophy } from "lucide-react";
import { useApp } from "@/context/AppContext";

// All color classes must appear literally here so Tailwind JIT includes them
const colorPalette: Record<string, { color: string; bg: string; border: string }> = {
  orange: { color: "text-gold-light", bg: "bg-orange-400/20", border: "border-orange-400" },
  gray:   { color: "text-parchment",  bg: "bg-slate-300/20",  border: "border-slate-300"  },
  yellow: { color: "text-yellow-400", bg: "bg-yellow-400/20", border: "border-yellow-400" },
  blue:   { color: "text-blue-400",   bg: "bg-blue-400/20",   border: "border-blue-400"   },
  green:  { color: "text-green-400",  bg: "bg-green-400/20",  border: "border-green-400"  },
  purple: { color: "text-purple-400", bg: "bg-purple-400/20", border: "border-purple-400" },
};

export default function Fidelidade() {
  const navigate = useNavigate();
  const { orders, fidelidadeLevels, fidelidadeRewards, earnRules } = useApp();

  const sortedLevels = [...fidelidadeLevels].sort((a, b) => a.minPoints - b.minPoints);
  const sortedRewards = [...fidelidadeRewards].sort((a, b) => a.points - b.points);

  const totalPoints = Math.floor(orders.reduce((sum, order) => sum + order.total * 10, 0));
  const currentLevel = [...sortedLevels].reverse().find((l) => totalPoints >= l.minPoints) || sortedLevels[0];
  const nextLevel = sortedLevels.find((l) => l.minPoints > totalPoints);
  const progressToNext = nextLevel && currentLevel
    ? ((totalPoints - currentLevel.minPoints) / (nextLevel.minPoints - currentLevel.minPoints)) * 100
    : 100;

  const currentPalette = colorPalette[currentLevel?.color] || colorPalette.orange;

  return (
    <div className="min-h-screen bg-gradient-to-br from-surface-01 to-surface-00">

      {/* Header */}
      <div className="bg-brand-dark px-4 py-4 flex justify-between items-center sticky top-0 z-30">
        <button onClick={() => navigate(-1)} className="text-parchment hover:text-cream transition-colors">
          <ChevronLeft size={24} />
        </button>
        <h1 className="text-cream font-bold flex-1 text-center">Programa de Fidelidade</h1>
        <div className="w-6"></div>
      </div>

      <div className="px-4 pt-6 pb-32 space-y-6">
        {/* Points Hero */}
        <div className="bg-gradient-to-r from-orange-500 to-orange-600 rounded-2xl p-6 text-center shadow-lg">
          <p className="text-orange-100 text-sm mb-1">Seus pontos</p>
          <p className="text-cream text-5xl font-bold mb-1">{totalPoints}</p>
          <p className="text-orange-100 text-sm">pontos acumulados</p>
          {currentLevel && (
            <div className="inline-flex items-center gap-2 mt-4 px-4 py-2 rounded-full bg-white/20">
              <span className="text-xl">{currentLevel.icon}</span>
              <span className="text-cream font-bold">{currentLevel.name}</span>
            </div>
          )}
        </div>

        {/* Progress to Next Level */}
        {nextLevel && currentLevel && (
          <div className="bg-surface-02 rounded-xl p-4 border border-surface-03">
            <div className="flex justify-between items-center mb-3">
              <span className="text-stone text-sm">Progresso para {nextLevel.name}</span>
              <span className="text-cream text-sm font-bold">{totalPoints} / {nextLevel.minPoints} pts</span>
            </div>
            <div className="w-full bg-surface-03 rounded-full h-3">
              <div className="bg-gold h-3 rounded-full transition-all duration-500" style={{ width: `${Math.min(progressToNext, 100)}%` }} />
            </div>
            <p className="text-stone text-xs mt-2">
              Faltam <span className="text-gold-light font-bold">{nextLevel.minPoints - totalPoints} pts</span> para o nível {nextLevel.name}
            </p>
          </div>
        )}

        {/* Levels */}
        <div>
          <h2 className="text-cream font-bold text-lg mb-4 flex items-center gap-2">
            <Trophy size={20} className="text-gold" />
            Níveis
          </h2>
          <div className="space-y-3">
            {sortedLevels.map((level, idx) => {
              const palette = colorPalette[level.color] || colorPalette.orange;
              const isCurrentLevel = currentLevel?.id === level.id;
              const nextLvl = sortedLevels[idx + 1];
              return (
                <div key={level.id} className={`flex items-center gap-4 p-4 rounded-xl border ${isCurrentLevel ? `${palette.bg} ${palette.border}` : "bg-surface-02 border-surface-03"}`}>
                  <span className="text-3xl">{level.icon}</span>
                  <div className="flex-1">
                    <p className={`font-bold ${isCurrentLevel ? palette.color : "text-cream"}`}>{level.name}</p>
                    <p className="text-stone text-xs">
                      {nextLvl ? `${level.minPoints} – ${nextLvl.minPoints - 1} pontos` : `${level.minPoints}+ pontos`}
                    </p>
                  </div>
                  {isCurrentLevel && (
                    <span className="text-xs text-cream bg-gold px-2 py-1 rounded-full">Atual</span>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Rewards */}
        <div>
          <h2 className="text-cream font-bold text-lg mb-4 flex items-center gap-2">
            <Gift size={20} className="text-gold" />
            Recompensas
          </h2>
          <div className="grid grid-cols-2 gap-3">
            {sortedRewards.map((reward) => {
              const unlocked = totalPoints >= reward.points;
              return (
                <div key={reward.id} className={`p-4 rounded-xl border text-center ${unlocked ? "bg-gold/10 border-gold" : "bg-surface-02 border-surface-03 opacity-50"}`}>
                  <span className="text-3xl">{reward.icon}</span>
                  <p className="text-cream text-xs font-bold mt-2">{reward.label}</p>
                  <p className={`text-xs mt-1 ${unlocked ? "text-gold-light" : "text-stone"}`}>{reward.points} pts</p>
                  {unlocked && (
                    <span className="inline-block text-xs bg-gold text-cream px-2 py-0.5 rounded-full mt-2">Disponível</span>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* How to Earn */}
        <div>
          <h2 className="text-cream font-bold text-lg mb-4 flex items-center gap-2">
            <Zap size={20} className="text-gold" />
            Como ganhar pontos
          </h2>
          <div className="space-y-3">
            {earnRules.map((item) => (
              <div key={item.id} className="flex items-center gap-4 bg-surface-02 rounded-xl p-4 border border-surface-03">
                <span className="text-2xl">{item.icon}</span>
                <p className="text-cream text-sm flex-1">{item.label}</p>
                <span className="text-gold-light font-bold text-sm">{item.points}</span>
              </div>
            ))}
          </div>
        </div>

        {/* History */}
        {orders.length > 0 && (
          <div>
            <h2 className="text-cream font-bold text-lg mb-4 flex items-center gap-2">
              <Star size={20} className="text-gold" />
              Histórico de pontos
            </h2>
            <div className="space-y-3">
              {orders.slice().reverse().map((order) => (
                <div key={order.id} className="flex items-center gap-4 bg-surface-02 rounded-xl p-4 border border-surface-03">
                  <div className="w-10 h-10 rounded-full bg-gold/20 flex items-center justify-center">
                    <span className="text-lg">🍕</span>
                  </div>
                  <div className="flex-1">
                    <p className="text-cream text-sm font-semibold">Pedido {order.id.split("-")[1]}</p>
                    <p className="text-stone text-xs">{new Date(order.created_at).toLocaleDateString("pt-BR")}</p>
                  </div>
                  <span className="text-gold-light font-bold text-sm">+{Math.floor(order.total * 10)} pts</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {orders.length === 0 && (
          <div className="text-center py-8">
            <span className="text-5xl">🏆</span>
            <p className="text-cream font-bold mt-4">Faça seu primeiro pedido!</p>
            <p className="text-stone text-sm mt-2">Cada pedido gera pontos para você trocar por recompensas.</p>
          </div>
        )}
      </div>
    </div>
  );
}
