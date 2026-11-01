import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  ArrowDownCircle,
  ArrowUpCircle,
  BarChart3,
  CheckCircle2,
  ClipboardList,
  CircleDollarSign,
  Filter,
  LayoutDashboard,
  Landmark,
  Loader2,
  Plus,
  RefreshCw,
  ReceiptText,
  Search,
  Settings,
  SlidersHorizontal,
  Tags,
  Trash2,
  TrendingUp,
  Users,
  Wallet,
  type LucideIcon,
} from "lucide-react";
import { AdminPageTabs, type AdminPageTab } from "@/components/admin/AdminPageChrome";
import AdminGestao from "./AdminGestao";
import {
  financeApi,
  type FinanceAccount,
  type FinanceAccountInput,
  type FinanceCategory,
  type FinanceCategoryInput,
  type FinanceCounterparty,
  type FinanceCounterpartyInput,
  type FinanceEntryType,
  type FinanceOverview,
  type FinanceSettlementInput,
  type FinanceTransaction,
  type FinanceTransactionInput,
} from "@/lib/api";

type FinanceSection = "settings" | "summary" | "registries" | "transactions";

const sections: AdminPageTab<FinanceSection>[] = [
  { id: "summary", label: "Resumo e DRE", icon: LayoutDashboard },
  { id: "registries", label: "Cadastros", icon: Tags },
  { id: "transactions", label: "Lancamentos", icon: ClipboardList },
  { id: "settings", label: "Configuracoes", icon: Settings },
];

const panelClass = "rounded-2xl border border-surface-03 bg-surface-02 p-5 shadow-[0_12px_36px_rgba(0,0,0,0.12)]";
const inputClass = "w-full rounded-xl border border-surface-03 bg-surface-01 px-3 py-2.5 text-sm text-cream outline-none transition placeholder:text-stone/70 focus:border-gold focus:ring-2 focus:ring-gold/10";
const buttonClass = "inline-flex items-center justify-center gap-2 rounded-xl bg-gold px-3.5 py-2.5 text-sm font-black text-black transition hover:bg-gold/90 disabled:cursor-not-allowed disabled:opacity-60";
const mutedButtonClass = "inline-flex items-center justify-center gap-2 rounded-xl border border-surface-03 bg-surface-01 px-3.5 py-2.5 text-sm font-bold text-stone transition hover:border-gold/40 hover:bg-surface-03 hover:text-cream disabled:cursor-not-allowed disabled:opacity-60";

function today() {
  const date = new Date();
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function currency(value: number) {
  return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(value || 0);
}

const emptyAccount: FinanceAccountInput = {
  name: "",
  account_type: "bank",
  opening_balance: 0,
  notes: "",
  active: true,
};

const emptyCategory: FinanceCategoryInput = {
  name: "",
  entry_type: "expense",
  dre_group: "operational",
  parent_id: null,
  notes: "",
  active: true,
};

const emptyCounterparty: FinanceCounterpartyInput = {
  name: "",
  counterparty_type: "supplier",
  document: "",
  phone: "",
  email: "",
  notes: "",
  active: true,
};

const emptyTransaction: FinanceTransactionInput = {
  account_id: null,
  category_id: null,
  cost_center: "",
  counterparty_id: null,
  counterparty_type: null,
  counterparty_name: "",
  counterparty_document: "",
  entry_type: "expense",
  status: "pending",
  description: "",
  amount: 0,
    paid_amount: 0,
    interest_amount: 0,
    fine_amount: 0,
    discount_amount: 0,
    fee_amount: 0,
    net_amount: 0,
  competence_date: today(),
  due_date: today(),
  paid_at: null,
  document_number: "",
  document_date: null,
  payment_method: "",
  payment_reference: "",
  installment_group_id: null,
  installment_number: 1,
  installment_total: 1,
  order_id: null,
  payment_id: null,
  inventory_purchase_id: null,
  origin_type: "manual",
  origin_id: null,
  notes: "",
};

export default function GestaoFinance() {
  const [section, setSection] = useState<FinanceSection>("summary");

  return (
    <AdminGestao
      moduleKey="finance"
      showSettings={section === "settings"}
      moduleTabs={<AdminPageTabs<FinanceSection> tabs={sections} active={section} onChange={setSection} />}
    >
      {section !== "settings" && <FinancePanel section={section} />}
    </AdminGestao>
  );
}

function FinancePanel({ section }: { section: Exclude<FinanceSection, "settings"> }) {
  const [data, setData] = useState<FinanceOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState("");
  const [error, setError] = useState("");
  const [accountDraft, setAccountDraft] = useState<FinanceAccountInput>(emptyAccount);
  const [categoryDraft, setCategoryDraft] = useState<FinanceCategoryInput>(emptyCategory);
  const [counterpartyDraft, setCounterpartyDraft] = useState<FinanceCounterpartyInput>(emptyCounterparty);
  const [transactionDraft, setTransactionDraft] = useState<FinanceTransactionInput>(emptyTransaction);
  const [settlementDrafts, setSettlementDrafts] = useState<Record<string, FinanceSettlementInput>>({});
  const [transactionQuery, setTransactionQuery] = useState("");
  const [transactionStatus, setTransactionStatus] = useState("all");
  const [transactionEntryType, setTransactionEntryType] = useState("all");

  const load = () => {
    setLoading(true);
    setError("");
    financeApi.overview()
      .then(setData)
      .catch((err) => setError(err instanceof Error ? err.message : "Nao foi possivel carregar Financeiro."))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, []);

  const categoriesForEntry = useMemo(() => {
    return (data?.categories ?? []).filter((category) => category.entry_type === transactionDraft.entry_type);
  }, [data?.categories, transactionDraft.entry_type]);

  const filteredTransactions = useMemo(() => {
    const query = transactionQuery.trim().toLocaleLowerCase();
    return (data?.transactions ?? []).filter((transaction) => {
      const searchable = [
        transaction.description,
        transaction.counterparty_name,
        transaction.category_name,
        transaction.document_number,
        transaction.cost_center,
      ].filter(Boolean).join(" ").toLocaleLowerCase();
      const matchesQuery = !query || searchable.includes(query);
      const matchesStatus = transactionStatus === "all" || transaction.status === transactionStatus;
      const matchesEntryType = transactionEntryType === "all" || transaction.entry_type === transactionEntryType;
      return matchesQuery && matchesStatus && matchesEntryType;
    });
  }, [data?.transactions, transactionEntryType, transactionQuery, transactionStatus]);

  const createAccount = async () => {
    if (!accountDraft.name.trim()) return;
    setSaving("account");
    setError("");
    try {
      await financeApi.createAccount({ ...accountDraft, opening_balance: Number(accountDraft.opening_balance || 0) });
      setAccountDraft(emptyAccount);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nao foi possivel salvar conta.");
    } finally {
      setSaving("");
    }
  };

  const createCategory = async () => {
    if (!categoryDraft.name.trim()) return;
    setSaving("category");
    setError("");
    try {
      await financeApi.createCategory(categoryDraft);
      setCategoryDraft(emptyCategory);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nao foi possivel salvar categoria.");
    } finally {
      setSaving("");
    }
  };

  const createCounterparty = async () => {
    if (!counterpartyDraft.name.trim()) return;
    setSaving("counterparty");
    setError("");
    try {
      await financeApi.createCounterparty(counterpartyDraft);
      setCounterpartyDraft(emptyCounterparty);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nao foi possivel salvar favorecido.");
    } finally {
      setSaving("");
    }
  };

  const createTransaction = async () => {
    if (!transactionDraft.description.trim() || Number(transactionDraft.amount || 0) <= 0) return;
    setSaving("transaction");
    setError("");
    try {
      await financeApi.createTransaction({
        ...transactionDraft,
        account_id: transactionDraft.account_id || null,
        category_id: transactionDraft.category_id || null,
        cost_center: transactionDraft.cost_center || null,
        counterparty_id: transactionDraft.counterparty_id || null,
        counterparty_name: transactionDraft.counterparty_name || null,
        counterparty_document: transactionDraft.counterparty_document || null,
        amount: Number(transactionDraft.amount || 0),
        paid_amount: transactionDraft.status === "paid" ? Number(transactionDraft.paid_amount || transactionDraft.amount || 0) : 0,
        interest_amount: Number(transactionDraft.interest_amount || 0),
        fine_amount: Number(transactionDraft.fine_amount || 0),
        discount_amount: Number(transactionDraft.discount_amount || 0),
        fee_amount: Number(transactionDraft.fee_amount || 0),
        net_amount: Number(transactionDraft.net_amount || 0),
        due_date: transactionDraft.due_date || null,
        document_number: transactionDraft.document_number || null,
        document_date: transactionDraft.document_date || null,
        payment_method: transactionDraft.payment_method || null,
        payment_reference: transactionDraft.payment_reference || null,
        installment_number: Number(transactionDraft.installment_number || 1),
        installment_total: Number(transactionDraft.installment_total || 1),
      });
      setTransactionDraft(emptyTransaction);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nao foi possivel salvar lancamento.");
    } finally {
      setSaving("");
    }
  };

  const totalWithAdjustments = (transaction: FinanceTransaction, draft?: FinanceSettlementInput) => {
    return Math.max(
      0,
      Number(transaction.amount || 0)
        + Number(transaction.interest_amount || 0)
        + Number(draft?.interest_amount || 0)
        + Number(transaction.fine_amount || 0)
        + Number(draft?.fine_amount || 0)
        - Number(transaction.discount_amount || 0)
        - Number(draft?.discount_amount || 0),
    );
  };

  const openAmount = (transaction: FinanceTransaction, draft?: FinanceSettlementInput) => {
    return Math.max(0, totalWithAdjustments(transaction, draft) - Number(transaction.paid_amount || 0));
  };

  const settlementDraft = (transaction: FinanceTransaction): FinanceSettlementInput => {
    const current = settlementDrafts[transaction.id] ?? {};
    return {
      account_id: current.account_id ?? transaction.account_id ?? data?.accounts[0]?.id ?? null,
      paid_amount: current.paid_amount ?? openAmount(transaction, current),
      interest_amount: current.interest_amount ?? 0,
      fine_amount: current.fine_amount ?? 0,
      discount_amount: current.discount_amount ?? 0,
      fee_amount: current.fee_amount ?? 0,
      payment_method: current.payment_method ?? transaction.payment_method ?? "",
      payment_reference: current.payment_reference ?? transaction.payment_reference ?? "",
      notes: current.notes ?? transaction.notes ?? "",
    };
  };

  const updateSettlementDraft = (transactionId: string, patch: Partial<FinanceSettlementInput>) => {
    setSettlementDrafts((current) => ({
      ...current,
      [transactionId]: { ...(current[transactionId] ?? {}), ...patch },
    }));
  };

  const settleTransaction = async (transaction: FinanceTransaction) => {
    if (transaction.status === "paid" || transaction.status === "cancelled") {
      return;
    }

    const draft = settlementDraft(transaction);
    const paidAmount = Number(draft.paid_amount);
    if (!Number.isFinite(paidAmount) || paidAmount <= 0) {
      setError("O valor da baixa deve ser maior que zero.");
      return;
    }

    setSaving(transaction.id);
    setError("");
    try {
      await financeApi.settleTransaction(transaction.id, {
        ...draft,
        account_id: draft.account_id || null,
        paid_amount: paidAmount,
        paid_at: new Date().toISOString(),
        interest_amount: Number(draft.interest_amount || 0),
        fine_amount: Number(draft.fine_amount || 0),
        discount_amount: Number(draft.discount_amount || 0),
        fee_amount: Number(draft.fee_amount || 0),
        payment_method: draft.payment_method || null,
        payment_reference: draft.payment_reference || null,
        notes: draft.notes || null,
      });
      setSettlementDrafts((current) => {
        const next = { ...current };
        delete next[transaction.id];
        return next;
      });
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nao foi possivel baixar lancamento.");
    } finally {
      setSaving("");
    }
  };

  const removeTransaction = async (transaction: FinanceTransaction) => {
    if (transaction.status === "paid" || transaction.status === "cancelled") {
      return;
    }

    setSaving(transaction.id);
    setError("");
    try {
      await financeApi.removeTransaction(transaction.id);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nao foi possivel cancelar lancamento.");
    } finally {
      setSaving("");
    }
  };

  return (
    <section className="space-y-6" aria-labelledby="finance-panel-title">
      <div className="relative overflow-hidden rounded-2xl border border-gold/20 bg-gradient-to-br from-surface-02 via-surface-02 to-gold/5 p-5 shadow-[0_16px_48px_rgba(0,0,0,0.16)] sm:p-6">
        <div className="pointer-events-none absolute -right-16 -top-20 h-48 w-48 rounded-full bg-gold/10 blur-3xl" />
        <div className="relative flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex items-start gap-4">
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl border border-gold/30 bg-gold/10 text-gold">
              <CircleDollarSign size={25} aria-hidden="true" />
            </div>
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <p className="text-xs font-black uppercase tracking-[0.18em] text-gold">Gestao financeira</p>
                <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-500/25 bg-emerald-500/10 px-2.5 py-1 text-[10px] font-black uppercase tracking-wide text-emerald-300">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-300" aria-hidden="true" /> Operacional
                </span>
              </div>
              <h2 id="finance-panel-title" className="mt-1 text-2xl font-black tracking-tight text-cream sm:text-3xl">Visao financeira do negocio</h2>
              <p className="mt-2 max-w-2xl text-sm leading-relaxed text-stone">Contas, categorias e lancamentos manuais para acompanhar caixa, competencia e DRE em um unico lugar.</p>
            </div>
          </div>
          <button type="button" onClick={load} disabled={loading} className={mutedButtonClass} aria-label="Atualizar dados financeiros">
            {loading ? <Loader2 size={16} className="animate-spin" aria-hidden="true" /> : <RefreshCw size={16} aria-hidden="true" />}
            Atualizar dados
          </button>
        </div>
        <div className="relative mt-5 grid gap-3 border-t border-surface-03/80 pt-4 text-xs text-stone sm:grid-cols-3">
          <div className="flex items-center gap-2"><Wallet size={15} className="text-gold" aria-hidden="true" /><span>Controle de caixa e liquidações</span></div>
          <div className="flex items-center gap-2"><BarChart3 size={15} className="text-gold" aria-hidden="true" /><span>Resultado por competência e DRE</span></div>
          <div className="flex items-center gap-2"><ReceiptText size={15} className="text-gold" aria-hidden="true" /><span>Registros com rastreabilidade</span></div>
        </div>
      </div>

      {loading && (
        <div className="flex min-h-56 flex-col items-center justify-center rounded-2xl border border-surface-03 bg-surface-02 text-stone" role="status" aria-live="polite">
          <Loader2 size={24} className="mb-3 animate-spin text-gold" aria-hidden="true" />
          <span className="text-sm font-semibold">Carregando financeiro...</span>
        </div>
      )}

      {!loading && error && (
        <div className="rounded-2xl border border-red-500/30 bg-red-500/10 p-5 text-red-200" role="alert">
          <div className="flex items-center gap-2 font-bold">
            <AlertTriangle size={18} aria-hidden="true" /> Nao foi possivel atualizar o financeiro
          </div>
          <p className="mt-2 text-sm">{error}</p>
          <button type="button" onClick={load} className="mt-4 inline-flex items-center gap-2 rounded-lg border border-red-300/30 px-3 py-2 text-xs font-bold text-red-100 transition hover:bg-red-400/10">
            <RefreshCw size={14} aria-hidden="true" /> Tentar novamente
          </button>
        </div>
      )}

      {!loading && data && (
        <>
          {section === "summary" && (
            <>
              <div className="grid gap-4 lg:grid-cols-[1.35fr_1fr_1fr]">
                <div className="relative overflow-hidden rounded-2xl border border-gold/30 bg-gradient-to-br from-gold/15 via-surface-02 to-surface-02 p-5 sm:p-6">
                  <div className="absolute -right-6 -top-8 h-32 w-32 rounded-full bg-gold/10 blur-2xl" />
                  <div className="relative flex items-start justify-between gap-4">
                    <div>
                      <p className="text-xs font-black uppercase tracking-[0.16em] text-gold">Saldo consolidado</p>
                      <p className={`mt-3 text-3xl font-black tracking-tight sm:text-4xl ${data.summary.balance >= 0 ? "text-emerald-200" : "text-amber-200"}`}>{currency(data.summary.balance)}</p>
                      <p className="mt-2 text-sm text-stone">Disponivel nas contas financeiras cadastradas</p>
                    </div>
                    <div className="rounded-2xl border border-gold/25 bg-gold/10 p-3 text-gold"><Wallet size={24} aria-hidden="true" /></div>
                  </div>
                  <div className="relative mt-6 flex flex-wrap gap-x-6 gap-y-2 text-xs text-stone">
                    <span><strong className="text-emerald-300">{currency(data.summary.income_paid)}</strong> receitas pagas</span>
                    <span><strong className="text-amber-300">{currency(data.summary.expense_paid)}</strong> despesas pagas</span>
                  </div>
                </div>
                <Metric title="Resultado de caixa" value={currency(data.management.cash_realized_result)} subtitle="Movimentos efetivamente liquidados" icon={TrendingUp} tone={data.management.cash_realized_result >= 0 ? "success" : "warn"} />
                <Metric title="Pendencias financeiras" value={`${data.summary.pending_count} abertas`} subtitle={data.summary.overdue_count ? `${data.summary.overdue_count} vencidas exigem atencao` : "Nenhuma pendencia vencida"} icon={data.summary.overdue_count ? AlertTriangle : CheckCircle2} tone={data.summary.overdue_count ? "warn" : "success"} />
              </div>

              <div className="grid gap-4 md:grid-cols-3">
                <Metric title="Resultado competencia" value={currency(data.management.accrual_result)} subtitle="Receitas menos despesas por data de competência" icon={BarChart3} tone={data.management.accrual_result >= 0 ? "success" : "warn"} />
                <Metric title="Receita competencia" value={currency(data.management.accrual_income)} subtitle="Entradas reconhecidas no periodo" icon={ArrowUpCircle} tone="success" />
                <Metric title="Status da DRE" value={data.management.dre_label} subtitle="Nivel de cobertura dos dados atuais" icon={ReceiptText} tone={data.management.dre_status.includes("complete") ? "success" : "warn"} />
              </div>

              <div className="grid gap-5 xl:grid-cols-[1.15fr_1fr_1fr]">
                <DimensionList title="DRE por grupo" icon={BarChart3} featured rows={data.management.dre_lines.map((item) => ({ label: item.group, entry_type: item.entry_type, amount: item.amount, count: 1 }))} />
                <DimensionList title="Por canal" icon={Landmark} rows={data.management.by_channel} />
                <DimensionList title="Por categoria" icon={Tags} rows={data.management.by_category} />
                <DimensionList title="Por centro de custo" icon={SlidersHorizontal} rows={data.management.by_cost_center} />
              </div>
            </>
          )}

          {section === "registries" && <div className="grid gap-5 xl:grid-cols-4">
            <div className={`${panelClass} flex flex-col`}>
              <CardHeading icon={Landmark} title="Nova conta" description="Organize bancos, caixas e carteiras." />
              <div className="space-y-3">
                <input aria-label="Nome da conta" className={inputClass} placeholder="Nome da conta" value={accountDraft.name} onChange={(event) => setAccountDraft({ ...accountDraft, name: event.target.value })} />
                <select aria-label="Tipo da conta" className={inputClass} value={accountDraft.account_type} onChange={(event) => setAccountDraft({ ...accountDraft, account_type: event.target.value as FinanceAccount["account_type"] })}>
                  <option value="bank">Banco</option>
                  <option value="cash">Caixa</option>
                  <option value="credit_card">Cartao</option>
                  <option value="wallet">Carteira</option>
                  <option value="other">Outra</option>
                </select>
                <input aria-label="Saldo inicial" className={inputClass} type="number" step="0.01" placeholder="Saldo inicial" value={accountDraft.opening_balance} onChange={(event) => setAccountDraft({ ...accountDraft, opening_balance: Number(event.target.value) })} />
                <button type="button" onClick={createAccount} disabled={saving === "account"} className={buttonClass}>
                  {saving === "account" ? <Loader2 size={15} className="animate-spin" /> : <Plus size={15} />}
                  Criar conta
                </button>
              </div>
            </div>

            <div className={`${panelClass} flex flex-col`}>
              <CardHeading icon={Tags} title="Nova categoria" description="Classifique receitas e despesas na DRE." />
              <div className="space-y-3">
                <input aria-label="Nome da categoria" className={inputClass} placeholder="Nome da categoria" value={categoryDraft.name} onChange={(event) => setCategoryDraft({ ...categoryDraft, name: event.target.value })} />
                <select aria-label="Tipo da categoria" className={inputClass} value={categoryDraft.entry_type} onChange={(event) => setCategoryDraft({ ...categoryDraft, entry_type: event.target.value as FinanceEntryType })}>
                  <option value="expense">Despesa</option>
                  <option value="income">Receita</option>
                </select>
                <input aria-label="Grupo DRE" className={inputClass} placeholder="Grupo DRE" value={categoryDraft.dre_group} onChange={(event) => setCategoryDraft({ ...categoryDraft, dre_group: event.target.value })} />
                <button type="button" onClick={createCategory} disabled={saving === "category"} className={buttonClass}>
                  {saving === "category" ? <Loader2 size={15} className="animate-spin" /> : <Plus size={15} />}
                  Criar categoria
                </button>
              </div>
            </div>

            <div className={`${panelClass} flex flex-col`}>
              <CardHeading icon={Users} title="Novo favorecido" description="Mantenha fornecedores e parceiros acessíveis." />
              <div className="space-y-3">
                <input aria-label="Nome do favorecido" className={inputClass} placeholder="Nome" value={counterpartyDraft.name} onChange={(event) => setCounterpartyDraft({ ...counterpartyDraft, name: event.target.value })} />
                <select aria-label="Tipo do favorecido" className={inputClass} value={counterpartyDraft.counterparty_type} onChange={(event) => setCounterpartyDraft({ ...counterpartyDraft, counterparty_type: event.target.value as FinanceCounterparty["counterparty_type"] })}>
                  <option value="supplier">Fornecedor</option>
                  <option value="customer">Cliente</option>
                  <option value="employee">Colaborador</option>
                  <option value="partner">Parceiro</option>
                  <option value="other">Outro</option>
                </select>
                <input aria-label="Documento do favorecido" className={inputClass} placeholder="Documento" value={counterpartyDraft.document || ""} onChange={(event) => setCounterpartyDraft({ ...counterpartyDraft, document: event.target.value })} />
                <input aria-label="Telefone do favorecido" className={inputClass} placeholder="Telefone" value={counterpartyDraft.phone || ""} onChange={(event) => setCounterpartyDraft({ ...counterpartyDraft, phone: event.target.value })} />
                <button type="button" onClick={createCounterparty} disabled={saving === "counterparty"} className={buttonClass}>
                  {saving === "counterparty" ? <Loader2 size={15} className="animate-spin" /> : <Plus size={15} />}
                  Criar favorecido
                </button>
              </div>
            </div>

            <div className={`${panelClass} flex flex-col`}>
              <CardHeading icon={ReceiptText} title="Novo lancamento" description="Registre uma receita ou despesa manual." />
              <div className="space-y-3">
                <input aria-label="Descricao do lancamento" className={inputClass} placeholder="Descricao" value={transactionDraft.description} onChange={(event) => setTransactionDraft({ ...transactionDraft, description: event.target.value })} />
                <div className="grid grid-cols-2 gap-3">
                  <select aria-label="Tipo do lancamento" className={inputClass} value={transactionDraft.entry_type} onChange={(event) => setTransactionDraft({ ...transactionDraft, entry_type: event.target.value as FinanceEntryType, category_id: null })}>
                    <option value="expense">Despesa</option>
                    <option value="income">Receita</option>
                  </select>
                  <select aria-label="Status do lancamento" className={inputClass} value={transactionDraft.status} onChange={(event) => setTransactionDraft({ ...transactionDraft, status: event.target.value as FinanceTransactionInput["status"] })}>
                    <option value="pending">Pendente</option>
                    <option value="paid">Pago</option>
                  </select>
                </div>
                <input aria-label="Valor do lancamento" className={inputClass} type="number" step="0.01" placeholder="Valor" value={transactionDraft.amount} onChange={(event) => setTransactionDraft({ ...transactionDraft, amount: Number(event.target.value) })} />
                <input aria-label="Numero do documento" className={inputClass} placeholder="Numero do documento" value={transactionDraft.document_number || ""} onChange={(event) => setTransactionDraft({ ...transactionDraft, document_number: event.target.value })} />
                <input aria-label="Centro de custo" className={inputClass} placeholder="Centro de custo" value={transactionDraft.cost_center || ""} onChange={(event) => setTransactionDraft({ ...transactionDraft, cost_center: event.target.value })} />
                <div className="grid grid-cols-2 gap-3">
                  <input aria-label="Data de competencia" className={inputClass} type="date" value={transactionDraft.competence_date} onChange={(event) => setTransactionDraft({ ...transactionDraft, competence_date: event.target.value })} />
                  <input aria-label="Data de vencimento" className={inputClass} type="date" value={transactionDraft.due_date || ""} onChange={(event) => setTransactionDraft({ ...transactionDraft, due_date: event.target.value || null })} />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <input aria-label="Numero da parcela" className={inputClass} type="number" min="1" placeholder="Parcela" value={transactionDraft.installment_number} onChange={(event) => setTransactionDraft({ ...transactionDraft, installment_number: Number(event.target.value || 1) })} />
                  <input aria-label="Total de parcelas" className={inputClass} type="number" min="1" placeholder="Total parcelas" value={transactionDraft.installment_total} onChange={(event) => setTransactionDraft({ ...transactionDraft, installment_total: Number(event.target.value || 1) })} />
                </div>
                <select aria-label="Conta do lancamento" className={inputClass} value={transactionDraft.account_id || ""} onChange={(event) => setTransactionDraft({ ...transactionDraft, account_id: event.target.value || null })}>
                  <option value="">Sem conta</option>
                  {data.accounts.map((account) => <option key={account.id} value={account.id}>{account.name}</option>)}
                </select>
                <select aria-label="Favorecido do lancamento" className={inputClass} value={transactionDraft.counterparty_id || ""} onChange={(event) => {
                  const selected = data.counterparties.find((item) => item.id === event.target.value);
                  setTransactionDraft({
                    ...transactionDraft,
                    counterparty_id: event.target.value || null,
                    counterparty_type: selected?.counterparty_type ?? transactionDraft.counterparty_type,
                    counterparty_name: selected?.name ?? "",
                    counterparty_document: selected?.document ?? "",
                  });
                }}>
                  <option value="">Sem favorecido</option>
                  {data.counterparties.map((counterparty) => <option key={counterparty.id} value={counterparty.id}>{counterparty.name}</option>)}
                </select>
                <select aria-label="Categoria do lancamento" className={inputClass} value={transactionDraft.category_id || ""} onChange={(event) => setTransactionDraft({ ...transactionDraft, category_id: event.target.value || null })}>
                  <option value="">Sem categoria</option>
                  {categoriesForEntry.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}
                </select>
                <div className="grid grid-cols-2 gap-3">
                  <input aria-label="Forma de pagamento" className={inputClass} placeholder="Forma pgto." value={transactionDraft.payment_method || ""} onChange={(event) => setTransactionDraft({ ...transactionDraft, payment_method: event.target.value })} />
                  <input aria-label="Referencia do lancamento" className={inputClass} placeholder="Referencia" value={transactionDraft.payment_reference || ""} onChange={(event) => setTransactionDraft({ ...transactionDraft, payment_reference: event.target.value })} />
                </div>
                <button type="button" onClick={createTransaction} disabled={saving === "transaction"} className={buttonClass}>
                  {saving === "transaction" ? <Loader2 size={15} className="animate-spin" /> : <Plus size={15} />}
                  Criar lancamento
                </button>
              </div>
            </div>
          </div>}

          {section === "transactions" && <div className="grid gap-5 xl:grid-cols-[.85fr_.85fr_1.7fr]">
            <div className={panelClass}>
              <CardHeading icon={Landmark} title="Contas" description={`${data.accounts.length} contas disponiveis`} />
              <div className="space-y-2">
                {data.accounts.map((account) => (
                  <div key={account.id} className="rounded-lg border border-surface-03 bg-surface-01 px-3 py-2">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <p className="font-bold text-cream">{account.name}</p>
                        <p className="text-xs text-stone">{account.account_type.replace(/_/g, " ")}</p>
                      </div>
                      <p className="font-black text-gold">{currency(account.current_balance)}</p>
                    </div>
                  </div>
                ))}
                {data.accounts.length === 0 && <EmptyText text="Nenhuma conta cadastrada." />}
              </div>
            </div>

            <div className={panelClass}>
              <CardHeading icon={Users} title="Favorecidos" description={`${data.counterparties.length} cadastros ativos`} />
              <div className="space-y-2">
                {data.counterparties.map((counterparty) => (
                  <div key={counterparty.id} className="rounded-lg border border-surface-03 bg-surface-01 px-3 py-2">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <p className="font-bold text-cream">{counterparty.name}</p>
                        <p className="text-xs text-stone">{counterparty.counterparty_type} {counterparty.document ? `- ${counterparty.document}` : ""}</p>
                      </div>
                      <p className="font-black text-amber-300">{currency(counterparty.open_amount)}</p>
                    </div>
                  </div>
                ))}
                {data.counterparties.length === 0 && <EmptyText text="Nenhum favorecido cadastrado." />}
              </div>
            </div>

            <div className={panelClass}>
              <div className="flex flex-col gap-4 border-b border-surface-03 pb-4">
                <CardHeading icon={ClipboardList} title="Lancamentos" description={`${filteredTransactions.length} de ${data.transactions.length} registros exibidos`} />
                <div className="grid gap-2 md:grid-cols-[minmax(0,1fr)_10rem_10rem]">
                  <label className="relative block">
                    <span className="sr-only">Buscar lancamentos</span>
                    <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-stone" aria-hidden="true" />
                    <input className={`${inputClass} pl-9`} value={transactionQuery} onChange={(event) => setTransactionQuery(event.target.value)} placeholder="Buscar por descricao, favorecido ou documento" aria-label="Buscar lancamentos" />
                  </label>
                  <label>
                    <span className="sr-only">Filtrar por status</span>
                    <select className={inputClass} value={transactionStatus} onChange={(event) => setTransactionStatus(event.target.value)} aria-label="Filtrar lancamentos por status">
                      <option value="all">Todos os status</option>
                      <option value="pending">Pendentes</option>
                      <option value="partial">Parciais</option>
                      <option value="paid">Pagos</option>
                      <option value="cancelled">Cancelados</option>
                    </select>
                  </label>
                  <label>
                    <span className="sr-only">Filtrar por tipo</span>
                    <select className={inputClass} value={transactionEntryType} onChange={(event) => setTransactionEntryType(event.target.value)} aria-label="Filtrar lancamentos por tipo">
                      <option value="all">Receitas e despesas</option>
                      <option value="income">Somente receitas</option>
                      <option value="expense">Somente despesas</option>
                    </select>
                  </label>
                </div>
                {(transactionQuery || transactionStatus !== "all" || transactionEntryType !== "all") && (
                  <button type="button" className="inline-flex w-fit items-center gap-2 text-xs font-bold text-gold transition hover:text-cream" onClick={() => { setTransactionQuery(""); setTransactionStatus("all"); setTransactionEntryType("all"); }}>
                    <Filter size={13} aria-hidden="true" /> Limpar filtros
                  </button>
                )}
              </div>
              <div className="space-y-2">
                {filteredTransactions.map((transaction) => (
                  <div key={transaction.id} className="group grid gap-3 rounded-xl border border-surface-03 bg-surface-01 p-4 transition hover:border-gold/30 hover:bg-surface-01/80 lg:grid-cols-[minmax(0,1fr)_auto_auto] lg:items-center">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="truncate font-bold text-cream" title={transaction.description}>{transaction.description}</p>
                        <StatusBadge transaction={transaction} />
                      </div>
                      <p className="mt-1 text-xs text-stone">
                        {transaction.counterparty_name || "Sem favorecido"} - {transaction.category_name || "Sem categoria"} - venc. {transaction.due_date || "-"}
                      </p>
                      <p className="mt-1 text-[11px] text-stone">
                        Doc. {transaction.document_number || "-"} - Centro {transaction.cost_center || "-"} - Parcela {transaction.installment_number}/{transaction.installment_total}
                      </p>
                    </div>
                    <p className={`flex items-center gap-1.5 text-right font-black ${transaction.entry_type === "income" ? "text-emerald-300" : "text-amber-300"}`}>
                      {transaction.entry_type === "income" ? <ArrowUpCircle size={15} aria-hidden="true" /> : <ArrowDownCircle size={15} aria-hidden="true" />}
                      {transaction.entry_type === "income" ? "+" : "-"}{currency(transaction.amount)}
                    </p>
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => settleTransaction(transaction)}
                        disabled={saving === transaction.id || transaction.status === "paid" || transaction.status === "cancelled"}
                        className="rounded-lg border border-emerald-500/30 p-2 text-emerald-300 transition hover:bg-emerald-500/10 disabled:cursor-not-allowed disabled:opacity-50"
                        title={transaction.status === "paid" ? "Lancamento ja pago" : transaction.status === "cancelled" ? "Lancamento cancelado" : "Baixar lancamento"}
                        aria-label="Baixar lancamento"
                      >
                        <CheckCircle2 size={16} />
                      </button>
                      <button
                        type="button"
                        onClick={() => removeTransaction(transaction)}
                        disabled={saving === transaction.id || transaction.status === "paid" || transaction.status === "cancelled"}
                        className="rounded-lg border border-red-500/30 p-2 text-red-300 transition hover:bg-red-500/10 disabled:cursor-not-allowed disabled:opacity-50"
                        title={transaction.status === "paid" ? "Lancamento ja pago" : transaction.status === "cancelled" ? "Lancamento ja cancelado" : "Cancelar lancamento"}
                        aria-label="Cancelar lancamento"
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>
                    {transaction.status !== "paid" && transaction.status !== "cancelled" && (
                      <SettlementFields
                        transaction={transaction}
                        accounts={data.accounts}
                        draft={settlementDraft(transaction)}
                        openAmount={openAmount(transaction, settlementDraft(transaction))}
                        onChange={(patch) => updateSettlementDraft(transaction.id, patch)}
                      />
                    )}
                  </div>
                ))}
                {data.transactions.length === 0 && <EmptyText icon={ClipboardList} text="Nenhum lancamento cadastrado." />}
                {data.transactions.length > 0 && filteredTransactions.length === 0 && <EmptyText icon={Search} text="Nenhum lancamento corresponde aos filtros." />}
              </div>
            </div>
          </div>}
        </>
      )}
    </section>
  );
}

function Metric({
  title,
  value,
  subtitle,
  icon: Icon,
  tone = "default",
}: {
  title: string;
  value: string;
  subtitle?: string;
  icon: LucideIcon;
  tone?: "default" | "success" | "warn";
}) {
  const toneClass = tone === "success" ? "text-emerald-300" : tone === "warn" ? "text-amber-300" : "text-gold";
  const iconClass = tone === "success" ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-300" : tone === "warn" ? "border-amber-500/20 bg-amber-500/10 text-amber-300" : "border-gold/20 bg-gold/10 text-gold";
  return (
    <div className={`${panelClass} flex min-h-36 flex-col justify-between`}>
      <div className="flex items-start justify-between gap-3">
        <div className="text-xs font-black uppercase tracking-[0.14em] text-stone">{title}</div>
        <div className={`rounded-xl border p-2 ${iconClass}`}><Icon size={18} aria-hidden="true" /></div>
      </div>
      <div>
        <p className={`mt-4 text-2xl font-black tracking-tight ${toneClass}`}>{value}</p>
        {subtitle && <p className="mt-1 text-xs leading-relaxed text-stone">{subtitle}</p>}
      </div>
    </div>
  );
}

function DimensionList({
  title,
  icon: Icon,
  featured = false,
  rows,
}: {
  title: string;
  icon: LucideIcon;
  featured?: boolean;
  rows: Array<{ label: string; entry_type: FinanceEntryType; amount: number; count: number }>;
}) {
  return (
    <div className={`${panelClass} ${featured ? "xl:row-span-2" : ""}`}>
      <div className="mb-4 flex items-start gap-3">
        <div className="rounded-xl border border-gold/20 bg-gold/10 p-2 text-gold"><Icon size={17} aria-hidden="true" /></div>
        <div>
          <h4 className="text-sm font-black uppercase tracking-wide text-parchment">{title}</h4>
          <p className="mt-1 text-xs text-stone">Distribuicao dos valores registrados</p>
        </div>
      </div>
      <div className="space-y-2">
        {rows.slice(0, 6).map((row) => (
          <div key={`${row.label}-${row.entry_type}`} className="rounded-xl border border-surface-03 bg-surface-01 px-3 py-3 transition hover:border-gold/20">
            <div className="flex items-center justify-between gap-3">
              <div className="min-w-0">
                <p className="truncate text-sm font-bold text-cream" title={row.label}>{row.label}</p>
                <p className="text-[11px] text-stone">{row.entry_type === "income" ? "Receita" : "Despesa"} - {row.count} lanc.</p>
              </div>
              <p className={row.entry_type === "income" ? "font-black text-emerald-300" : "font-black text-amber-300"}>
                {currency(row.amount)}
              </p>
            </div>
          </div>
        ))}
        {rows.length === 0 && <EmptyText text="Sem dados para este resumo." />}
      </div>
    </div>
  );
}

function SettlementFields({
  transaction,
  accounts,
  draft,
  openAmount,
  onChange,
}: {
  transaction: FinanceTransaction;
  accounts: FinanceAccount[];
  draft: FinanceSettlementInput;
  openAmount: number;
  onChange: (patch: Partial<FinanceSettlementInput>) => void;
}) {
  const netPreview = transaction.entry_type === "income"
    ? Math.max(0, Number(draft.paid_amount || 0) - Number(draft.fee_amount || 0))
    : Number(draft.paid_amount || 0) + Number(draft.fee_amount || 0);

  return (
    <div className="grid gap-2 rounded-xl border-t border-surface-03 bg-surface-02/60 pt-3 lg:col-span-3 xl:grid-cols-6">
      <label className="text-[11px] font-bold text-stone">Conta
      <select aria-label="Conta da baixa" className={`${inputClass} mt-1`} value={draft.account_id || ""} onChange={(event) => onChange({ account_id: event.target.value || null })}>
        <option value="">Conta</option>
        {accounts.map((account) => <option key={account.id} value={account.id}>{account.name}</option>)}
      </select>
      </label>
      <label className="text-[11px] font-bold text-stone">Valor da baixa
      <input aria-label="Valor da baixa" className={`${inputClass} mt-1`} type="number" step="0.01" min="0.01" value={draft.paid_amount ?? openAmount} onChange={(event) => onChange({ paid_amount: Number(event.target.value || 0) })} />
      </label>
      <label className="text-[11px] font-bold text-stone">Juros
      <input aria-label="Juros" className={`${inputClass} mt-1`} type="number" step="0.01" min="0" placeholder="0,00" value={draft.interest_amount ?? 0} onChange={(event) => onChange({ interest_amount: Number(event.target.value || 0) })} />
      </label>
      <label className="text-[11px] font-bold text-stone">Multa
      <input aria-label="Multa" className={`${inputClass} mt-1`} type="number" step="0.01" min="0" placeholder="0,00" value={draft.fine_amount ?? 0} onChange={(event) => onChange({ fine_amount: Number(event.target.value || 0) })} />
      </label>
      <label className="text-[11px] font-bold text-stone">Desconto
      <input aria-label="Desconto" className={`${inputClass} mt-1`} type="number" step="0.01" min="0" placeholder="0,00" value={draft.discount_amount ?? 0} onChange={(event) => onChange({ discount_amount: Number(event.target.value || 0) })} />
      </label>
      <label className="text-[11px] font-bold text-stone">Tarifa
      <input aria-label="Tarifa" className={`${inputClass} mt-1`} type="number" step="0.01" min="0" placeholder="0,00" value={draft.fee_amount ?? 0} onChange={(event) => onChange({ fee_amount: Number(event.target.value || 0) })} />
      </label>
      <label className="text-[11px] font-bold text-stone">Metodo
      <input aria-label="Metodo de pagamento" className={`${inputClass} mt-1`} placeholder="Ex.: Pix" value={draft.payment_method || ""} onChange={(event) => onChange({ payment_method: event.target.value })} />
      </label>
      <label className="text-[11px] font-bold text-stone">Referencia
      <input aria-label="Referencia do pagamento" className={`${inputClass} mt-1`} placeholder="Opcional" value={draft.payment_reference || ""} onChange={(event) => onChange({ payment_reference: event.target.value })} />
      </label>
      <div className="rounded-xl border border-surface-03 bg-surface-02 px-3 py-2 text-xs text-stone xl:col-span-2">
        Aberto: <span className="font-black text-cream">{currency(openAmount)}</span>
      </div>
      <div className="rounded-xl border border-gold/20 bg-gold/5 px-3 py-2 text-xs text-stone xl:col-span-2">
        Caixa liquido: <span className="font-black text-gold">{currency(netPreview)}</span>
      </div>
    </div>
  );
}

function StatusBadge({ transaction }: { transaction: FinanceTransaction }) {
  const cls = transaction.status === "paid"
    ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
    : transaction.status === "partial"
      ? "border-blue-500/30 bg-blue-500/10 text-blue-300"
      : transaction.status === "cancelled"
        ? "border-slate-500/30 bg-slate-500/10 text-slate-300"
    : transaction.overdue
      ? "border-red-500/30 bg-red-500/10 text-red-300"
      : "border-amber-500/30 bg-amber-500/10 text-amber-300";
  const label = transaction.status === "paid"
    ? "Pago"
    : transaction.status === "partial"
      ? "Parcial"
      : transaction.status === "cancelled"
        ? "Cancelado"
        : transaction.overdue
          ? "Vencido"
          : "Pendente";
  return <span className={`rounded-full border px-2 py-0.5 text-[10px] font-bold ${cls}`}>{label}</span>;
}

function CardHeading({ icon: Icon, title, description }: { icon: LucideIcon; title: string; description: string }) {
  return (
    <div className="mb-5 flex items-start gap-3">
      <div className="rounded-xl border border-gold/20 bg-gold/10 p-2 text-gold"><Icon size={17} aria-hidden="true" /></div>
      <div className="min-w-0">
        <h4 className="text-sm font-black uppercase tracking-wide text-parchment">{title}</h4>
        <p className="mt-1 text-xs leading-relaxed text-stone">{description}</p>
      </div>
    </div>
  );
}

function EmptyText({ text, icon: Icon = ClipboardList }: { text: string; icon?: LucideIcon }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-surface-03 bg-surface-01/70 p-8 text-center text-sm text-stone">
      <Icon size={22} className="mb-2 text-stone/70" aria-hidden="true" />
      <span>{text}</span>
    </div>
  );
}
