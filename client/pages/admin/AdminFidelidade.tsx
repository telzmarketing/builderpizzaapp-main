import { useState } from "react";
import { Plus, Trash2, Edit2, Save, GripVertical } from "lucide-react";
import { useApp, FidelidadeLevel, FidelidadeReward, EarnRule } from "@/context/AppContext";
import AdminSidebar from "@/components/AdminSidebar";

// All color classes must appear literally in this file so Tailwind JIT includes them
const colorPalette: Record<string, { label: string; color: string; bg: string; border: string; preview: string }> = {
  orange: { label: "Laranja", color: "text-orange-400", bg: "bg-orange-400/20", border: "border-orange-400", preview: "bg-orange-400" },
  gray:   { label: "Prata",   color: "text-parchment",  bg: "bg-slate-300/20",  border: "border-slate-300",  preview: "bg-slate-300"  },
  yellow: { label: "Ouro",    color: "text-yellow-400", bg: "bg-yellow-400/20", border: "border-yellow-400", preview: "bg-yellow-400" },
  blue:   { label: "Azul",    color: "text-blue-400",   bg: "bg-blue-400/20",   border: "border-blue-400",   preview: "bg-blue-400"   },
  green:  { label: "Verde",   color: "text-green-400",  bg: "bg-green-400/20",  border: "border-green-400",  preview: "bg-green-400"  },
  purple: { label: "Roxo",    color: "text-purple-400", bg: "bg-purple-400/20", border: "border-purple-400", preview: "bg-purple-400" },
};

const emptyLevel: Partial<FidelidadeLevel> = { name: "", minPoints: 0, icon: "🥉", color: "orange" };
const emptyReward: Partial<FidelidadeReward> = { label: "", points: 100, icon: "🏷️" };
const emptyRule: Partial<EarnRule> = { icon: "🛒", label: "", points: "+10 pts" };

export default function AdminFidelidade() {
  const { fidelidadeLevels, setFidelidadeLevels, fidelidadeRewards, setFidelidadeRewards, earnRules, setEarnRules } = useApp();

  // ── Levels ──
  const [showLevelForm, setShowLevelForm] = useState(false);
  const [editingLevelId, setEditingLevelId] = useState<string | null>(null);
  const [levelForm, setLevelForm] = useState<Partial<FidelidadeLevel>>(emptyLevel);

  const handleSaveLevel = (e: React.FormEvent) => {
    e.preventDefault();
    if (!levelForm.name) { alert("Informe o nome do nível"); return; }
    if (editingLevelId) {
      setFidelidadeLevels(fidelidadeLevels.map((l) => l.id === editingLevelId ? { ...l, ...levelForm } as FidelidadeLevel : l));
      setEditingLevelId(null);
    } else {
      setFidelidadeLevels([...fidelidadeLevels, { id: `lvl-${Date.now()}`, name: levelForm.name!, minPoints: levelForm.minPoints || 0, icon: levelForm.icon || "🥉", color: levelForm.color || "orange" }]);
    }
    setLevelForm(emptyLevel);
    setShowLevelForm(false);
  };

  const editLevel = (level: FidelidadeLevel) => { setLevelForm(level); setEditingLevelId(level.id); setShowLevelForm(true); };
  const deleteLevel = (id: string) => setFidelidadeLevels(fidelidadeLevels.filter((l) => l.id !== id));

  // ── Rewards ──
  const [showRewardForm, setShowRewardForm] = useState(false);
  const [editingRewardId, setEditingRewardId] = useState<string | null>(null);
  const [rewardForm, setRewardForm] = useState<Partial<FidelidadeReward>>(emptyReward);

  const handleSaveReward = (e: React.FormEvent) => {
    e.preventDefault();
    if (!rewardForm.label) { alert("Informe o nome da recompensa"); return; }
    if (editingRewardId) {
      setFidelidadeRewards(fidelidadeRewards.map((r) => r.id === editingRewardId ? { ...r, ...rewardForm } as FidelidadeReward : r));
      setEditingRewardId(null);
    } else {
      setFidelidadeRewards([...fidelidadeRewards, { id: `rew-${Date.now()}`, label: rewardForm.label!, points: rewardForm.points || 100, icon: rewardForm.icon || "🏷️" }]);
    }
    setRewardForm(emptyReward);
    setShowRewardForm(false);
  };

  const editReward = (r: FidelidadeReward) => { setRewardForm(r); setEditingRewardId(r.id); setShowRewardForm(true); };
  const deleteReward = (id: string) => setFidelidadeRewards(fidelidadeRewards.filter((r) => r.id !== id));

  // ── Earn Rules ──
  const [showRuleForm, setShowRuleForm] = useState(false);
  const [editingRuleId, setEditingRuleId] = useState<string | null>(null);
  const [ruleForm, setRuleForm] = useState<Partial<EarnRule>>(emptyRule);

  const handleSaveRule = (e: React.FormEvent) => {
    e.preventDefault();
    if (!ruleForm.label) { alert("Informe a descrição da regra"); return; }
    if (editingRuleId) {
      setEarnRules(earnRules.map((r) => r.id === editingRuleId ? { ...r, ...ruleForm } as EarnRule : r));
      setEditingRuleId(null);
    } else {
      setEarnRules([...earnRules, { id: `rule-${Date.now()}`, icon: ruleForm.icon || "🛒", label: ruleForm.label!, points: ruleForm.points || "+10 pts" }]);
    }
    setRuleForm(emptyRule);
    setShowRuleForm(false);
  };

  const editRule = (r: EarnRule) => { setRuleForm(r); setEditingRuleId(r.id); setShowRuleForm(true); };
  const deleteRule = (id: string) => setEarnRules(earnRules.filter((r) => r.id !== id));

  // Sorted levels by minPoints
  const sortedLevels = [...fidelidadeLevels].sort((a, b) => a.minPoints - b.minPoints);
  const sortedRewards = [...fidelidadeRewards].sort((a, b) => a.points - b.points);

  return (
    <div className="min-h-screen bg-gradient-to-br from-surface-00 to-surface-00">
      <div className="flex h-screen">
        <AdminSidebar />

        <div className="flex-1 overflow-auto">
          <div className="bg-surface-02 px-8 py-4 border-b border-surface-03 sticky top-0 z-20">
            <h2 className="text-2xl font-bold text-cream">Programa de Fidelidade</h2>
            <p className="text-stone text-sm">Configure níveis, recompensas e regras de pontos</p>
          </div>

          <div className="p-8 space-y-10">

            {/* ─── LEVELS ─── */}
            <section>
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="text-lg font-bold text-cream">🏆 Níveis</h3>
                  <p className="text-stone text-sm">Defina os níveis de fidelidade e a pontuação mínima de cada um</p>
                </div>
                <button
                  onClick={() => { setShowLevelForm(!showLevelForm); setEditingLevelId(null); setLevelForm(emptyLevel); }}
                  className="flex items-center gap-2 bg-gold hover:bg-gold/90 text-cream font-bold py-2 px-4 rounded-lg transition-colors text-sm"
                >
                  <Plus size={16} />
                  Novo Nível
                </button>
              </div>

              {showLevelForm && (
                <form onSubmit={handleSaveLevel} className="bg-surface-02 rounded-xl p-5 border border-gold/40 mb-4 space-y-4">
                  <h4 className="text-cream font-bold">{editingLevelId ? "Editar Nível" : "Novo Nível"}</h4>
                  <div className="grid grid-cols-3 gap-4">
                    <div>
                      <label className="block text-parchment text-xs font-medium mb-1">Nome *</label>
                      <input type="text" value={levelForm.name || ""} onChange={(e) => setLevelForm({ ...levelForm, name: e.target.value })}
                        className="w-full bg-surface-03 border border-surface-03 rounded-lg px-3 py-2 text-cream text-sm focus:outline-none focus:border-gold" placeholder="Ex: Bronze" />
                    </div>
                    <div>
                      <label className="block text-parchment text-xs font-medium mb-1">Pontos mínimos *</label>
                      <input type="number" min="0" value={levelForm.minPoints ?? ""} onChange={(e) => setLevelForm({ ...levelForm, minPoints: parseInt(e.target.value) || 0 })}
                        className="w-full bg-surface-03 border border-surface-03 rounded-lg px-3 py-2 text-cream text-sm focus:outline-none focus:border-gold" placeholder="0" />
                    </div>
                    <div>
                      <label className="block text-parchment text-xs font-medium mb-1">Ícone / Emoji</label>
                      <input type="text" value={levelForm.icon || ""} onChange={(e) => setLevelForm({ ...levelForm, icon: e.target.value })}
                        className="w-full bg-surface-03 border border-surface-03 rounded-lg px-3 py-2 text-cream text-2xl focus:outline-none focus:border-gold" placeholder="🥉" />
                    </div>
                  </div>
                  <div>
                    <label className="block text-parchment text-xs font-medium mb-2">Cor do nível</label>
                    <div className="flex gap-2 flex-wrap">
                      {Object.entries(colorPalette).map(([key, val]) => (
                        <button key={key} type="button" onClick={() => setLevelForm({ ...levelForm, color: key })}
                          className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border text-sm transition-colors ${levelForm.color === key ? "border-gold bg-surface-03" : "border-surface-03 bg-surface-03/50 hover:border-slate-500"}`}>
                          <span className={`w-3 h-3 rounded-full ${val.preview}`} />
                          <span className={val.color}>{val.label}</span>
                        </button>
                      ))}
                    </div>
                  </div>
                  <div className="flex gap-3">
                    <button type="submit" className="flex items-center gap-2 bg-gold hover:bg-gold/90 text-cream font-bold py-2 px-4 rounded-lg transition-colors text-sm">
                      <Save size={14} />
                      {editingLevelId ? "Salvar" : "Criar Nível"}
                    </button>
                    <button type="button" onClick={() => { setShowLevelForm(false); setEditingLevelId(null); }}
                      className="px-4 py-2 rounded-lg border border-surface-03 text-stone hover:border-slate-500 transition-colors text-sm">
                      Cancelar
                    </button>
                  </div>
                </form>
              )}

              <div className="space-y-3">
                {sortedLevels.map((level, idx) => {
                  const palette = colorPalette[level.color] || colorPalette.orange;
                  const nextLevel = sortedLevels[idx + 1];
                  return (
                    <div key={level.id} className={`flex items-center gap-4 p-4 rounded-xl border ${palette.bg} ${palette.border}`}>
                      <span className="text-3xl">{level.icon}</span>
                      <div className="flex-1">
                        <p className={`font-bold ${palette.color}`}>{level.name}</p>
                        <p className="text-stone text-xs">
                          {nextLevel ? `${level.minPoints} – ${nextLevel.minPoints - 1} pontos` : `${level.minPoints}+ pontos`}
                        </p>
                      </div>
                      <div className="flex gap-2">
                        <button onClick={() => editLevel(level)} className="p-2 bg-blue-500/20 hover:bg-blue-500/30 text-blue-400 rounded-lg transition-colors">
                          <Edit2 size={14} />
                        </button>
                        <button onClick={() => deleteLevel(level.id)} className="p-2 bg-red-500/20 hover:bg-red-500/30 text-red-400 rounded-lg transition-colors">
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </section>

            {/* ─── REWARDS ─── */}
            <section>
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="text-lg font-bold text-cream">🎁 Recompensas</h3>
                  <p className="text-stone text-sm">Prêmios que os clientes podem resgatar com seus pontos</p>
                </div>
                <button
                  onClick={() => { setShowRewardForm(!showRewardForm); setEditingRewardId(null); setRewardForm(emptyReward); }}
                  className="flex items-center gap-2 bg-gold hover:bg-gold/90 text-cream font-bold py-2 px-4 rounded-lg transition-colors text-sm"
                >
                  <Plus size={16} />
                  Nova Recompensa
                </button>
              </div>

              {showRewardForm && (
                <form onSubmit={handleSaveReward} className="bg-surface-02 rounded-xl p-5 border border-gold/40 mb-4 space-y-4">
                  <h4 className="text-cream font-bold">{editingRewardId ? "Editar Recompensa" : "Nova Recompensa"}</h4>
                  <div className="grid grid-cols-3 gap-4">
                    <div className="col-span-2">
                      <label className="block text-parchment text-xs font-medium mb-1">Nome da recompensa *</label>
                      <input type="text" value={rewardForm.label || ""} onChange={(e) => setRewardForm({ ...rewardForm, label: e.target.value })}
                        className="w-full bg-surface-03 border border-surface-03 rounded-lg px-3 py-2 text-cream text-sm focus:outline-none focus:border-gold" placeholder="Ex: 10% de desconto" />
                    </div>
                    <div>
                      <label className="block text-parchment text-xs font-medium mb-1">Ícone / Emoji</label>
                      <input type="text" value={rewardForm.icon || ""} onChange={(e) => setRewardForm({ ...rewardForm, icon: e.target.value })}
                        className="w-full bg-surface-03 border border-surface-03 rounded-lg px-3 py-2 text-cream text-2xl focus:outline-none focus:border-gold" placeholder="🏷️" />
                    </div>
                  </div>
                  <div>
                    <label className="block text-parchment text-xs font-medium mb-1">Pontos necessários *</label>
                    <input type="number" min="1" value={rewardForm.points ?? ""} onChange={(e) => setRewardForm({ ...rewardForm, points: parseInt(e.target.value) || 0 })}
                      className="w-full bg-surface-03 border border-surface-03 rounded-lg px-3 py-2 text-cream text-sm focus:outline-none focus:border-gold" placeholder="300" />
                  </div>
                  <div className="flex gap-3">
                    <button type="submit" className="flex items-center gap-2 bg-gold hover:bg-gold/90 text-cream font-bold py-2 px-4 rounded-lg transition-colors text-sm">
                      <Save size={14} />
                      {editingRewardId ? "Salvar" : "Criar Recompensa"}
                    </button>
                    <button type="button" onClick={() => { setShowRewardForm(false); setEditingRewardId(null); }}
                      className="px-4 py-2 rounded-lg border border-surface-03 text-stone hover:border-slate-500 transition-colors text-sm">
                      Cancelar
                    </button>
                  </div>
                </form>
              )}

              <div className="grid grid-cols-2 gap-3">
                {sortedRewards.map((reward) => (
                  <div key={reward.id} className="bg-surface-02 rounded-xl p-4 border border-surface-03 flex items-center gap-3">
                    <span className="text-3xl">{reward.icon}</span>
                    <div className="flex-1 min-w-0">
                      <p className="text-cream text-sm font-bold truncate">{reward.label}</p>
                      <p className="text-orange-400 text-xs">{reward.points} pts</p>
                    </div>
                    <div className="flex gap-1 flex-shrink-0">
                      <button onClick={() => editReward(reward)} className="p-1.5 bg-blue-500/20 hover:bg-blue-500/30 text-blue-400 rounded-lg transition-colors">
                        <Edit2 size={13} />
                      </button>
                      <button onClick={() => deleteReward(reward.id)} className="p-1.5 bg-red-500/20 hover:bg-red-500/30 text-red-400 rounded-lg transition-colors">
                        <Trash2 size={13} />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </section>

            {/* ─── EARN RULES ─── */}
            <section>
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="text-lg font-bold text-cream">⚡ Como ganhar pontos</h3>
                  <p className="text-stone text-sm">Regras que explicam aos clientes como acumular pontos</p>
                </div>
                <button
                  onClick={() => { setShowRuleForm(!showRuleForm); setEditingRuleId(null); setRuleForm(emptyRule); }}
                  className="flex items-center gap-2 bg-gold hover:bg-gold/90 text-cream font-bold py-2 px-4 rounded-lg transition-colors text-sm"
                >
                  <Plus size={16} />
                  Nova Regra
                </button>
              </div>

              {showRuleForm && (
                <form onSubmit={handleSaveRule} className="bg-surface-02 rounded-xl p-5 border border-gold/40 mb-4 space-y-4">
                  <h4 className="text-cream font-bold">{editingRuleId ? "Editar Regra" : "Nova Regra"}</h4>
                  <div className="grid grid-cols-3 gap-4">
                    <div>
                      <label className="block text-parchment text-xs font-medium mb-1">Ícone / Emoji</label>
                      <input type="text" value={ruleForm.icon || ""} onChange={(e) => setRuleForm({ ...ruleForm, icon: e.target.value })}
                        className="w-full bg-surface-03 border border-surface-03 rounded-lg px-3 py-2 text-cream text-2xl focus:outline-none focus:border-gold" placeholder="🛒" />
                    </div>
                    <div className="col-span-2">
                      <label className="block text-parchment text-xs font-medium mb-1">Descrição *</label>
                      <input type="text" value={ruleForm.label || ""} onChange={(e) => setRuleForm({ ...ruleForm, label: e.target.value })}
                        className="w-full bg-surface-03 border border-surface-03 rounded-lg px-3 py-2 text-cream text-sm focus:outline-none focus:border-gold" placeholder="Ex: A cada R$1 gasto" />
                    </div>
                  </div>
                  <div>
                    <label className="block text-parchment text-xs font-medium mb-1">Pontos ganhos</label>
                    <input type="text" value={ruleForm.points || ""} onChange={(e) => setRuleForm({ ...ruleForm, points: e.target.value })}
                      className="w-full bg-surface-03 border border-surface-03 rounded-lg px-3 py-2 text-cream text-sm focus:outline-none focus:border-gold" placeholder="+10 pts" />
                  </div>
                  <div className="flex gap-3">
                    <button type="submit" className="flex items-center gap-2 bg-gold hover:bg-gold/90 text-cream font-bold py-2 px-4 rounded-lg transition-colors text-sm">
                      <Save size={14} />
                      {editingRuleId ? "Salvar" : "Criar Regra"}
                    </button>
                    <button type="button" onClick={() => { setShowRuleForm(false); setEditingRuleId(null); }}
                      className="px-4 py-2 rounded-lg border border-surface-03 text-stone hover:border-slate-500 transition-colors text-sm">
                      Cancelar
                    </button>
                  </div>
                </form>
              )}

              <div className="space-y-3">
                {earnRules.map((rule) => (
                  <div key={rule.id} className="flex items-center gap-4 bg-surface-02 rounded-xl p-4 border border-surface-03">
                    <span className="text-2xl">{rule.icon}</span>
                    <p className="text-cream text-sm flex-1">{rule.label}</p>
                    <span className="text-orange-400 font-bold text-sm">{rule.points}</span>
                    <div className="flex gap-1">
                      <button onClick={() => editRule(rule)} className="p-1.5 bg-blue-500/20 hover:bg-blue-500/30 text-blue-400 rounded-lg transition-colors">
                        <Edit2 size={13} />
                      </button>
                      <button onClick={() => deleteRule(rule.id)} className="p-1.5 bg-red-500/20 hover:bg-red-500/30 text-red-400 rounded-lg transition-colors">
                        <Trash2 size={13} />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </section>

          </div>
        </div>
      </div>
    </div>
  );
}
