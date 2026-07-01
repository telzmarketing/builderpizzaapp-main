import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, CheckCircle2, Loader2, Plus, RefreshCw, Trash2 } from "lucide-react";
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

const panelClass = "rounded-lg border border-surface-03 bg-surface-02 p-5";
const inputClass = "w-full rounded-lg border border-surface-03 bg-surface-01 px-3 py-2 text-sm text-cream outline-none transition focus:border-gold";
const buttonClass = "inline-flex items-center justify-center gap-2 rounded-lg bg-gold px-3 py-2 text-sm font-black text-black transition hover:bg-gold/90 disabled:cursor-not-allowed disabled:opacity-60";

function today() {
  return new Date().toISOString().slice(0, 10);
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
  return (
    <AdminGestao moduleKey="finance">
      <FinancePanel />
    </AdminGestao>
  );
}

function FinancePanel() {
  const [data, setData] = useState<FinanceOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState("");
  const [error, setError] = useState("");
  const [accountDraft, setAccountDraft] = useState<FinanceAccountInput>(emptyAccount);
  const [categoryDraft, setCategoryDraft] = useState<FinanceCategoryInput>(emptyCategory);
  const [counterpartyDraft, setCounterpartyDraft] = useState<FinanceCounterpartyInput>(emptyCounterparty);
  const [transactionDraft, setTransactionDraft] = useState<FinanceTransactionInput>(emptyTransaction);
  const [settlementDrafts, setSettlementDrafts] = useState<Record<string, FinanceSettlementInput>>({});

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
    const draft = settlementDraft(transaction);
    setSaving(transaction.id);
    setError("");
    try {
      await financeApi.settleTransaction(transaction.id, {
        ...draft,
        account_id: draft.account_id || null,
        paid_amount: Number(draft.paid_amount || openAmount(transaction, draft)),
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
    <section className="space-y-5">
      <div className={panelClass}>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h3 className="text-lg font-black text-cream">Financeiro operacional</h3>
            <p className="text-sm text-stone">Contas, categorias e lancamentos manuais para base de caixa, competencia e DRE.</p>
          </div>
          <button type="button" onClick={load} disabled={loading} className="inline-flex items-center justify-center gap-2 rounded-lg border border-surface-03 px-3 py-2 text-sm font-bold text-stone transition hover:bg-surface-03 hover:text-cream disabled:opacity-60">
            {loading ? <Loader2 size={15} className="animate-spin" /> : <RefreshCw size={15} />}
            Atualizar
          </button>
        </div>
      </div>

      {loading && (
        <div className="flex min-h-48 items-center justify-center rounded-lg border border-surface-03 bg-surface-02 text-stone">
          <Loader2 size={18} className="mr-2 animate-spin" /> Carregando financeiro...
        </div>
      )}

      {!loading && error && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-5 text-red-200">
          <div className="flex items-center gap-2 font-bold">
            <AlertTriangle size={18} /> Erro ao carregar
          </div>
          <p className="mt-2 text-sm">{error}</p>
        </div>
      )}

      {!loading && data && (
        <>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <Metric title="Saldo caixa" value={currency(data.summary.balance)} tone={data.summary.balance >= 0 ? "success" : "warn"} />
            <Metric title="Receitas pagas" value={currency(data.summary.income_paid)} tone="success" />
            <Metric title="Despesas pagas" value={currency(data.summary.expense_paid)} tone="warn" />
            <Metric title="Pendencias" value={`${data.summary.pending_count} abertas`} tone={data.summary.overdue_count ? "warn" : "default"} />
          </div>

          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <Metric title="Resultado caixa" value={currency(data.management.cash_realized_result)} tone={data.management.cash_realized_result >= 0 ? "success" : "warn"} />
            <Metric title="Resultado competencia" value={currency(data.management.accrual_result)} tone={data.management.accrual_result >= 0 ? "success" : "warn"} />
            <Metric title="DRE" value={data.management.dre_label} tone={data.management.dre_status.includes("complete") ? "success" : "warn"} />
            <Metric title="Receita competencia" value={currency(data.management.accrual_income)} tone="success" />
          </div>

          <div className="grid gap-5 xl:grid-cols-4">
            <DimensionList title="DRE por grupo" rows={data.management.dre_lines.map((item) => ({ label: item.group, entry_type: item.entry_type, amount: item.amount, count: 1 }))} />
            <DimensionList title="Por canal" rows={data.management.by_channel} />
            <DimensionList title="Por categoria" rows={data.management.by_category} />
            <DimensionList title="Por centro de custo" rows={data.management.by_cost_center} />
          </div>

          <div className="grid gap-5 xl:grid-cols-4">
            <div className={panelClass}>
              <h4 className="mb-4 text-sm font-black uppercase tracking-wide text-parchment">Nova conta</h4>
              <div className="space-y-3">
                <input className={inputClass} placeholder="Nome da conta" value={accountDraft.name} onChange={(event) => setAccountDraft({ ...accountDraft, name: event.target.value })} />
                <select className={inputClass} value={accountDraft.account_type} onChange={(event) => setAccountDraft({ ...accountDraft, account_type: event.target.value as FinanceAccount["account_type"] })}>
                  <option value="bank">Banco</option>
                  <option value="cash">Caixa</option>
                  <option value="credit_card">Cartao</option>
                  <option value="wallet">Carteira</option>
                  <option value="other">Outra</option>
                </select>
                <input className={inputClass} type="number" step="0.01" placeholder="Saldo inicial" value={accountDraft.opening_balance} onChange={(event) => setAccountDraft({ ...accountDraft, opening_balance: Number(event.target.value) })} />
                <button type="button" onClick={createAccount} disabled={saving === "account"} className={buttonClass}>
                  {saving === "account" ? <Loader2 size={15} className="animate-spin" /> : <Plus size={15} />}
                  Criar conta
                </button>
              </div>
            </div>

            <div className={panelClass}>
              <h4 className="mb-4 text-sm font-black uppercase tracking-wide text-parchment">Nova categoria</h4>
              <div className="space-y-3">
                <input className={inputClass} placeholder="Nome da categoria" value={categoryDraft.name} onChange={(event) => setCategoryDraft({ ...categoryDraft, name: event.target.value })} />
                <select className={inputClass} value={categoryDraft.entry_type} onChange={(event) => setCategoryDraft({ ...categoryDraft, entry_type: event.target.value as FinanceEntryType })}>
                  <option value="expense">Despesa</option>
                  <option value="income">Receita</option>
                </select>
                <input className={inputClass} placeholder="Grupo DRE" value={categoryDraft.dre_group} onChange={(event) => setCategoryDraft({ ...categoryDraft, dre_group: event.target.value })} />
                <button type="button" onClick={createCategory} disabled={saving === "category"} className={buttonClass}>
                  {saving === "category" ? <Loader2 size={15} className="animate-spin" /> : <Plus size={15} />}
                  Criar categoria
                </button>
              </div>
            </div>

            <div className={panelClass}>
              <h4 className="mb-4 text-sm font-black uppercase tracking-wide text-parchment">Novo favorecido</h4>
              <div className="space-y-3">
                <input className={inputClass} placeholder="Nome" value={counterpartyDraft.name} onChange={(event) => setCounterpartyDraft({ ...counterpartyDraft, name: event.target.value })} />
                <select className={inputClass} value={counterpartyDraft.counterparty_type} onChange={(event) => setCounterpartyDraft({ ...counterpartyDraft, counterparty_type: event.target.value as FinanceCounterparty["counterparty_type"] })}>
                  <option value="supplier">Fornecedor</option>
                  <option value="customer">Cliente</option>
                  <option value="employee">Colaborador</option>
                  <option value="partner">Parceiro</option>
                  <option value="other">Outro</option>
                </select>
                <input className={inputClass} placeholder="Documento" value={counterpartyDraft.document || ""} onChange={(event) => setCounterpartyDraft({ ...counterpartyDraft, document: event.target.value })} />
                <input className={inputClass} placeholder="Telefone" value={counterpartyDraft.phone || ""} onChange={(event) => setCounterpartyDraft({ ...counterpartyDraft, phone: event.target.value })} />
                <button type="button" onClick={createCounterparty} disabled={saving === "counterparty"} className={buttonClass}>
                  {saving === "counterparty" ? <Loader2 size={15} className="animate-spin" /> : <Plus size={15} />}
                  Criar favorecido
                </button>
              </div>
            </div>

            <div className={panelClass}>
              <h4 className="mb-4 text-sm font-black uppercase tracking-wide text-parchment">Novo lancamento</h4>
              <div className="space-y-3">
                <input className={inputClass} placeholder="Descricao" value={transactionDraft.description} onChange={(event) => setTransactionDraft({ ...transactionDraft, description: event.target.value })} />
                <div className="grid grid-cols-2 gap-3">
                  <select className={inputClass} value={transactionDraft.entry_type} onChange={(event) => setTransactionDraft({ ...transactionDraft, entry_type: event.target.value as FinanceEntryType, category_id: null })}>
                    <option value="expense">Despesa</option>
                    <option value="income">Receita</option>
                  </select>
                  <select className={inputClass} value={transactionDraft.status} onChange={(event) => setTransactionDraft({ ...transactionDraft, status: event.target.value as FinanceTransactionInput["status"] })}>
                    <option value="pending">Pendente</option>
                    <option value="paid">Pago</option>
                  </select>
                </div>
                <input className={inputClass} type="number" step="0.01" placeholder="Valor" value={transactionDraft.amount} onChange={(event) => setTransactionDraft({ ...transactionDraft, amount: Number(event.target.value) })} />
                <input className={inputClass} placeholder="Numero do documento" value={transactionDraft.document_number || ""} onChange={(event) => setTransactionDraft({ ...transactionDraft, document_number: event.target.value })} />
                <input className={inputClass} placeholder="Centro de custo" value={transactionDraft.cost_center || ""} onChange={(event) => setTransactionDraft({ ...transactionDraft, cost_center: event.target.value })} />
                <div className="grid grid-cols-2 gap-3">
                  <input className={inputClass} type="date" value={transactionDraft.competence_date} onChange={(event) => setTransactionDraft({ ...transactionDraft, competence_date: event.target.value })} />
                  <input className={inputClass} type="date" value={transactionDraft.due_date || ""} onChange={(event) => setTransactionDraft({ ...transactionDraft, due_date: event.target.value || null })} />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <input className={inputClass} type="number" min="1" placeholder="Parcela" value={transactionDraft.installment_number} onChange={(event) => setTransactionDraft({ ...transactionDraft, installment_number: Number(event.target.value || 1) })} />
                  <input className={inputClass} type="number" min="1" placeholder="Total parcelas" value={transactionDraft.installment_total} onChange={(event) => setTransactionDraft({ ...transactionDraft, installment_total: Number(event.target.value || 1) })} />
                </div>
                <select className={inputClass} value={transactionDraft.account_id || ""} onChange={(event) => setTransactionDraft({ ...transactionDraft, account_id: event.target.value || null })}>
                  <option value="">Sem conta</option>
                  {data.accounts.map((account) => <option key={account.id} value={account.id}>{account.name}</option>)}
                </select>
                <select className={inputClass} value={transactionDraft.counterparty_id || ""} onChange={(event) => {
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
                <select className={inputClass} value={transactionDraft.category_id || ""} onChange={(event) => setTransactionDraft({ ...transactionDraft, category_id: event.target.value || null })}>
                  <option value="">Sem categoria</option>
                  {categoriesForEntry.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}
                </select>
                <div className="grid grid-cols-2 gap-3">
                  <input className={inputClass} placeholder="Forma pgto." value={transactionDraft.payment_method || ""} onChange={(event) => setTransactionDraft({ ...transactionDraft, payment_method: event.target.value })} />
                  <input className={inputClass} placeholder="Referencia" value={transactionDraft.payment_reference || ""} onChange={(event) => setTransactionDraft({ ...transactionDraft, payment_reference: event.target.value })} />
                </div>
                <button type="button" onClick={createTransaction} disabled={saving === "transaction"} className={buttonClass}>
                  {saving === "transaction" ? <Loader2 size={15} className="animate-spin" /> : <Plus size={15} />}
                  Criar lancamento
                </button>
              </div>
            </div>
          </div>

          <div className="grid gap-5 xl:grid-cols-[.9fr_.9fr_1.4fr]">
            <div className={panelClass}>
              <h4 className="mb-4 text-sm font-black uppercase tracking-wide text-parchment">Contas</h4>
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
              <h4 className="mb-4 text-sm font-black uppercase tracking-wide text-parchment">Favorecidos</h4>
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
              <h4 className="mb-4 text-sm font-black uppercase tracking-wide text-parchment">Lancamentos recentes</h4>
              <div className="space-y-2">
                {data.transactions.map((transaction) => (
                  <div key={transaction.id} className="grid gap-3 rounded-lg border border-surface-03 bg-surface-01 px-3 py-3 lg:grid-cols-[1fr_auto_auto] lg:items-center">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="truncate font-bold text-cream">{transaction.description}</p>
                        <StatusBadge transaction={transaction} />
                      </div>
                      <p className="mt-1 text-xs text-stone">
                        {transaction.counterparty_name || "Sem favorecido"} - {transaction.category_name || "Sem categoria"} - venc. {transaction.due_date || "-"}
                      </p>
                      <p className="mt-1 text-[11px] text-stone">
                        Doc. {transaction.document_number || "-"} - Centro {transaction.cost_center || "-"} - Parcela {transaction.installment_number}/{transaction.installment_total}
                      </p>
                    </div>
                    <p className={transaction.entry_type === "income" ? "font-black text-emerald-300" : "font-black text-amber-300"}>
                      {transaction.entry_type === "income" ? "+" : "-"}{currency(transaction.amount)}
                    </p>
                    <div className="flex items-center gap-2">
                      {transaction.status !== "paid" && transaction.status !== "cancelled" && (
                        <button type="button" onClick={() => settleTransaction(transaction)} disabled={saving === transaction.id} className="rounded-lg border border-emerald-500/30 p-2 text-emerald-300 transition hover:bg-emerald-500/10" title="Baixar lancamento">
                          <CheckCircle2 size={16} />
                        </button>
                      )}
                      <button type="button" onClick={() => removeTransaction(transaction)} disabled={saving === transaction.id} className="rounded-lg border border-red-500/30 p-2 text-red-300 transition hover:bg-red-500/10" title="Cancelar lancamento">
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
                {data.transactions.length === 0 && <EmptyText text="Nenhum lancamento cadastrado." />}
              </div>
            </div>
          </div>
        </>
      )}
    </section>
  );
}

function Metric({ title, value, tone = "default" }: { title: string; value: string; tone?: "default" | "success" | "warn" }) {
  const toneClass = tone === "success" ? "text-emerald-300" : tone === "warn" ? "text-amber-300" : "text-gold";
  return (
    <div className={panelClass}>
      <div className="mb-2 text-xs font-black uppercase tracking-wide text-stone">{title}</div>
      <p className={`text-xl font-black ${toneClass}`}>{value}</p>
    </div>
  );
}

function DimensionList({
  title,
  rows,
}: {
  title: string;
  rows: Array<{ label: string; entry_type: FinanceEntryType; amount: number; count: number }>;
}) {
  return (
    <div className={panelClass}>
      <h4 className="mb-4 text-sm font-black uppercase tracking-wide text-parchment">{title}</h4>
      <div className="space-y-2">
        {rows.slice(0, 6).map((row) => (
          <div key={`${row.label}-${row.entry_type}`} className="rounded-lg border border-surface-03 bg-surface-01 px-3 py-2">
            <div className="flex items-center justify-between gap-3">
              <div className="min-w-0">
                <p className="truncate text-sm font-bold text-cream">{row.label}</p>
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
    <div className="grid gap-2 border-t border-surface-03 pt-3 lg:col-span-3 xl:grid-cols-6">
      <select className={inputClass} value={draft.account_id || ""} onChange={(event) => onChange({ account_id: event.target.value || null })}>
        <option value="">Conta</option>
        {accounts.map((account) => <option key={account.id} value={account.id}>{account.name}</option>)}
      </select>
      <input className={inputClass} type="number" step="0.01" min="0.01" value={draft.paid_amount ?? openAmount} onChange={(event) => onChange({ paid_amount: Number(event.target.value || 0) })} />
      <input className={inputClass} type="number" step="0.01" min="0" placeholder="Juros" value={draft.interest_amount ?? 0} onChange={(event) => onChange({ interest_amount: Number(event.target.value || 0) })} />
      <input className={inputClass} type="number" step="0.01" min="0" placeholder="Multa" value={draft.fine_amount ?? 0} onChange={(event) => onChange({ fine_amount: Number(event.target.value || 0) })} />
      <input className={inputClass} type="number" step="0.01" min="0" placeholder="Desconto" value={draft.discount_amount ?? 0} onChange={(event) => onChange({ discount_amount: Number(event.target.value || 0) })} />
      <input className={inputClass} type="number" step="0.01" min="0" placeholder="Tarifa" value={draft.fee_amount ?? 0} onChange={(event) => onChange({ fee_amount: Number(event.target.value || 0) })} />
      <input className={inputClass} placeholder="Metodo" value={draft.payment_method || ""} onChange={(event) => onChange({ payment_method: event.target.value })} />
      <input className={inputClass} placeholder="Referencia" value={draft.payment_reference || ""} onChange={(event) => onChange({ payment_reference: event.target.value })} />
      <div className="rounded-lg border border-surface-03 bg-surface-02 px-3 py-2 text-xs text-stone xl:col-span-2">
        Aberto: <span className="font-black text-cream">{currency(openAmount)}</span>
      </div>
      <div className="rounded-lg border border-surface-03 bg-surface-02 px-3 py-2 text-xs text-stone xl:col-span-2">
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
    : transaction.overdue
      ? "border-red-500/30 bg-red-500/10 text-red-300"
      : "border-amber-500/30 bg-amber-500/10 text-amber-300";
  const label = transaction.status === "paid" ? "Pago" : transaction.status === "partial" ? "Parcial" : transaction.overdue ? "Vencido" : "Pendente";
  return <span className={`rounded-full border px-2 py-0.5 text-[10px] font-bold ${cls}`}>{label}</span>;
}

function EmptyText({ text }: { text: string }) {
  return <div className="rounded-lg border border-surface-03 bg-surface-01 p-5 text-center text-sm text-stone">{text}</div>;
}
