import { useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  ArrowDownCircle,
  ArrowUpCircle,
  BarChart3,
  CheckCircle2,
  ClipboardList,
  CircleDollarSign,
  CreditCard,
  Filter,
  LayoutDashboard,
  Landmark,
  Loader2,
  Plus,
  RefreshCw,
  ReceiptText,
  Route,
  Search,
  Settings,
  SlidersHorizontal,
  Tags,
  Trash2,
  TrendingUp,
  Users,
  Wallet,
  LineChart,
  CalendarCheck2,
  BrainCircuit,
  FileText,
  ShoppingBag,
  Target,
  type LucideIcon,
} from "lucide-react";
import AdminGestao from "./AdminGestao";
import {
  financeApi,
  type FinanceAccount,
  type FinanceBankStatement,
  type FinanceBankStatementImportInput,
  type FinanceBankReconciliationLine,
  type FinancePaymentOverview,
  type FinanceDeliveryOverview,
  type FinanceCashFlow,
  type FinanceBudget,
  type FinanceBudgetInput,
  type FinanceForecast,
  type FinanceBi,
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

type FinanceModuleId = "overview" | "payables" | "receivables" | "cash" | "banks" | "cards" | "delivery" | "couriers" | "cmv" | "cashflow" | "dre" | "budget" | "planning" | "bi" | "intelligence" | "suppliers" | "fiscal" | "settings" | "registries" | "transactions";
type FinanceRegistryPanel = "account" | "category" | "counterparty" | "transaction";

const focusClass = "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold focus-visible:ring-offset-2 focus-visible:ring-offset-surface-01";

const panelClass = "rounded-2xl border border-surface-03 bg-surface-02 p-5 shadow-[0_12px_36px_rgba(0,0,0,0.12)]";
const inputClass = "min-h-11 min-w-0 w-full rounded-xl border border-surface-03 bg-surface-01 px-3 py-2.5 text-sm text-cream outline-none transition placeholder:text-stone/70 focus-visible:border-gold focus-visible:ring-2 focus-visible:ring-gold";
const buttonClass = `inline-flex min-h-11 items-center justify-center gap-2 rounded-xl bg-gold px-3.5 py-2.5 text-sm font-black text-black transition hover:bg-gold/90 disabled:cursor-not-allowed disabled:opacity-60 ${focusClass}`;
const mutedButtonClass = `inline-flex min-h-11 items-center justify-center gap-2 rounded-xl border border-surface-03 bg-surface-01 px-3.5 py-2.5 text-sm font-bold text-stone transition hover:border-gold/40 hover:bg-surface-03 hover:text-cream disabled:cursor-not-allowed disabled:opacity-60 ${focusClass}`;

const sha256File = async (file: File): Promise<string> => {
  const digest = await crypto.subtle.digest("SHA-256", await file.arrayBuffer());
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
};

type FinanceModuleStatus = "Base disponível" | "Cobertura parcial" | "Não disponível";
type FinanceModule = { id: FinanceModuleId; title: string; description: string; status: FinanceModuleStatus; icon: LucideIcon };
const financeModuleStatuses: Record<FinanceModuleStatus, { className: string; description: string }> = {
  "Base disponível": { className: "border-emerald-500/25 bg-emerald-500/10 text-emerald-300", description: "Já existe operação disponível nesta área." },
  "Cobertura parcial": { className: "border-amber-500/25 bg-amber-500/10 text-amber-300", description: "Há dados ou operação parcial; o escopo completo ainda não está disponível." },
  "Não disponível": { className: "border-surface-03 bg-surface-01 text-stone", description: "A área está mapeada, mas ainda não possui operação financeira neste painel." },
};

// Coverage describes the operations exposed here, not a promise of a complete module.
const financeModuleGroups: Array<{ id: string; title: string; modules: FinanceModule[] }> = [
  { id: "overview", title: "Visão executiva", modules: [
    { id: "overview", title: "Visão Geral", description: "Indicadores consolidados, pendências e acesso às áreas financeiras.", status: "Base disponível", icon: LayoutDashboard },
  ] },
  { id: "operations", title: "Operação", modules: [
    { id: "payables", title: "Contas a Pagar", description: "Despesas registradas, vencimentos e baixas parciais ou integrais.", status: "Base disponível", icon: ArrowDownCircle },
    { id: "receivables", title: "Contas a Receber", description: "Receitas registradas, vencimentos e registro de recebimentos.", status: "Base disponível", icon: ArrowUpCircle },
    { id: "cash", title: "Caixa e Tesouraria", description: "Saldos por conta, liquidações e movimentações efetivamente realizadas.", status: "Base disponível", icon: Wallet },
  ] },
  { id: "controlling", title: "Controladoria", modules: [
    { id: "dre", title: "DRE e Resultados", description: "Receitas e despesas por competência, com CMV operacional separado e pendências de cobertura explícitas.", status: "Base disponível", icon: BarChart3 },
    { id: "cmv", title: "Custos e CMV", description: "Custos por snapshot de venda, cobertura, pendências e impacto operacional apresentados junto da DRE.", status: "Base disponível", icon: Tags },
    { id: "budget", title: "Orçamento Empresarial", description: "Criação de períodos orçamentários e comparação entre valores planejados e lançamentos realizados.", status: "Base disponível", icon: Target },
    { id: "bi", title: "BI Financeiro", description: "Distribuição dos valores por período, origem, canal, categoria e centro de custo.", status: "Base disponível", icon: TrendingUp },
  ] },
  { id: "treasury", title: "Tesouraria", modules: [
    { id: "banks", title: "Bancos e Conciliação", description: "Contas bancárias cadastradas. Importação de extratos, conciliação e tratamento de divergências ainda não estão disponíveis.", status: "Cobertura parcial", icon: Landmark },
    { id: "cards", title: "Cartões e Pix", description: "Forma de pagamento, referência e tarifa podem ser informadas na baixa. Agenda de repasses e conciliação por adquirente ainda não estão disponíveis.", status: "Cobertura parcial", icon: CreditCard },
    { id: "delivery", title: "Aplicativos de Delivery", description: "Valores agrupados por canal. Comissões, lotes de repasse e conciliação por aplicativo ainda não estão disponíveis.", status: "Cobertura parcial", icon: ShoppingBag },
    { id: "couriers", title: "Gestão Financeira de Entregadores", description: "Diárias, adiantamentos e acertos integrados ao caixa ainda não estão disponíveis neste Financeiro. Consulte a operação existente em Logística.", status: "Não disponível", icon: Route },
    { id: "cashflow", title: "Fluxo de Caixa", description: "Fluxo mensal com saldo inicial, realizado, projetado e extrato cronológico dos lançamentos.", status: "Base disponível", icon: LineChart },
    { id: "planning", title: "Planejamento Financeiro", description: "Previsão mensal baseada exclusivamente em lançamentos existentes, vencimentos e saldos cadastrados.", status: "Base disponível", icon: CalendarCheck2 },
    { id: "intelligence", title: "Inteligência Financeira", description: "Recomendações automáticas, detecção de anomalias e análises por IA ainda não estão disponíveis neste painel.", status: "Não disponível", icon: BrainCircuit },
  ] },
  { id: "administration", title: "Administração", modules: [
    { id: "suppliers", title: "Fornecedores e Contratos", description: "Consulta e cadastro de fornecedores e favorecidos. Contratos, vigências e renovações ainda não estão disponíveis.", status: "Cobertura parcial", icon: Users },
    { id: "fiscal", title: "Fiscal e Contábil", description: "O módulo Fiscal SEFAZ possui operação própria no ERP. Escrituração e fechamento contábil ainda não estão disponíveis neste Financeiro.", status: "Cobertura parcial", icon: FileText },
    { id: "settings", title: "Configurações Financeiras", description: "Parâmetros e estado de ativação do módulo. Políticas avançadas de aprovação e fechamento ainda não estão disponíveis.", status: "Cobertura parcial", icon: Settings },
  ] },
];
const financeModules = financeModuleGroups.flatMap((group) => group.modules);
const operationalPages: FinanceModule[] = [
  { id: "transactions", title: "Lançamentos", description: "Consulta e baixa das receitas e despesas já registradas.", status: "Base disponível", icon: ClipboardList },
  { id: "registries", title: "Cadastros", description: "Contas, categorias e favorecidos em formulários separados.", status: "Base disponível", icon: Tags },
];

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

function parseBankCsv(text: string): FinanceBankStatementImportInput["lines"] {
  const rows = text.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
  if (rows.length === 0) throw new Error("O CSV do extrato esta vazio.");
  const delimiter = rows[0].includes(";") ? ";" : ",";
  const start = /date|data|description|descricao/i.test(rows[0]) ? 1 : 0;
  const lines = rows.slice(start).map((row, index) => {
    const columns = row.split(delimiter).map((value) => value.trim().replace(/^\"|\"$/g, ""));
    const [external_id, transaction_date, description, amount, balance] = columns;
    if (!external_id || !transaction_date || !description || !amount) {
      throw new Error(`Linha ${index + start + 1} do CSV esta incompleta.`);
    }
    const normalizeNumber = (value: string) => value.includes(",") ? value.replace(/\./g, "").replace(",", ".") : value;
    const normalizedAmount = normalizeNumber(amount);
    const normalizedBalance = balance ? normalizeNumber(balance) : null;
    if (!Number.isFinite(Number(normalizedAmount))) throw new Error(`Valor invalido na linha ${index + start + 1}.`);
    return { external_id, transaction_date, description, amount: normalizedAmount, balance: normalizedBalance };
  });
  if (lines.length === 0) throw new Error("O CSV nao possui movimentacoes.");
  return lines;
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
    <AdminGestao moduleKey="finance" showSettings={false}>
      <FinancePanel />
    </AdminGestao>
  );
}

function FinancePanel() {
  const [activeModule, setActiveModule] = useState<FinanceModuleId>("overview");
  const headingRef = useRef<HTMLHeadingElement>(null);
  const [data, setData] = useState<FinanceOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState("");
  const [error, setError] = useState("");
  const [accountDraft, setAccountDraft] = useState<FinanceAccountInput>(emptyAccount);
  const [categoryDraft, setCategoryDraft] = useState<FinanceCategoryInput>(emptyCategory);
  const [counterpartyDraft, setCounterpartyDraft] = useState<FinanceCounterpartyInput>(emptyCounterparty);
  const [transactionDraft, setTransactionDraft] = useState<FinanceTransactionInput>(emptyTransaction);
  const [registryPanel, setRegistryPanel] = useState<FinanceRegistryPanel>("account");
  const [bankStatements, setBankStatements] = useState<FinanceBankStatement[]>([]);
  const [bankLoading, setBankLoading] = useState(false);
  const [bankError, setBankError] = useState("");
  const [selectedStatement, setSelectedStatement] = useState<string | null>(null);
  const [reconciliationLines, setReconciliationLines] = useState<FinanceBankReconciliationLine[]>([]);
  const [paymentOverview, setPaymentOverview] = useState<FinancePaymentOverview | null>(null);
  const [paymentLoading, setPaymentLoading] = useState(false);
  const [deliveryOverview, setDeliveryOverview] = useState<FinanceDeliveryOverview | null>(null);
  const [deliveryLoading, setDeliveryLoading] = useState(false);
  const [cashFlow, setCashFlow] = useState<FinanceCashFlow | null>(null);
  const [cashFlowLoading, setCashFlowLoading] = useState(false);
  const [forecast, setForecast] = useState<FinanceForecast | null>(null);
  const [forecastLoading, setForecastLoading] = useState(false);
  const [bi, setBi] = useState<FinanceBi | null>(null);
  const [biLoading, setBiLoading] = useState(false);
  const [biPeriod, setBiPeriod] = useState({ date_from: `${today().slice(0, 8)}01`, date_to: today() });
  const [budgets, setBudgets] = useState<FinanceBudget[]>([]);
  const [budgetLoading, setBudgetLoading] = useState(false);
  const [budgetSaving, setBudgetSaving] = useState(false);
  const [budgetDraft, setBudgetDraft] = useState<FinanceBudgetInput>({
    name: "",
    period_start: `${today().slice(0, 8)}01`,
    period_end: today(),
    status: "draft",
    notes: "",
    lines: [{ category_id: null, cost_center: "", entry_type: "expense", planned_amount: 0, notes: "" }],
  });
  const bankFileRef = useRef<HTMLInputElement>(null);
  const [settlementDrafts, setSettlementDrafts] = useState<Record<string, FinanceSettlementInput>>({});
  const [transactionQuery, setTransactionQuery] = useState("");
  const [transactionStatus, setTransactionStatus] = useState("all");
  const [transactionEntryType, setTransactionEntryType] = useState("all");
  const currentModule = [...financeModules, ...operationalPages].find((item) => item.id === activeModule)!;
  const CurrentIcon = currentModule.icon;
  // Ledger pages render only financial entries. Account/counterparty
  // registries belong to Cadastros and must never be repeated inside
  // payables, receivables, cash or reconciliation views.
  const isTransactionArea = ["payables", "receivables", "transactions"].includes(activeModule);

  const selectModule = (id: FinanceModuleId) => {
    setActiveModule(id);
    setTransactionQuery("");
    setTransactionStatus("all");
    setTransactionEntryType("all");
  };

  useEffect(() => {
    headingRef.current?.focus({ preventScroll: true });
  }, [activeModule]);

  useEffect(() => {
    if (activeModule !== "bi") return;
    setBiLoading(true);
    financeApi.bi(biPeriod)
      .then(setBi)
      .catch((err) => setError(err instanceof Error ? err.message : "Nao foi possivel carregar o BI financeiro."))
      .finally(() => setBiLoading(false));
  }, [activeModule, biPeriod]);

  useEffect(() => {
    if (activeModule !== "budget") return;
    setBudgetLoading(true);
    financeApi.listBudgets()
      .then(setBudgets)
      .catch((err) => setError(err instanceof Error ? err.message : "Nao foi possivel carregar os orcamentos."))
      .finally(() => setBudgetLoading(false));
  }, [activeModule]);

  useEffect(() => {
    if (activeModule !== "cashflow") return;
    setCashFlowLoading(true);
    financeApi.cashFlow()
      .then(setCashFlow)
      .catch((err) => setError(err instanceof Error ? err.message : "Nao foi possivel carregar o fluxo de caixa."))
      .finally(() => setCashFlowLoading(false));
  }, [activeModule]);

  useEffect(() => {
    if (activeModule !== "planning") return;
    setForecastLoading(true);
    financeApi.forecast(6)
      .then(setForecast)
      .catch((err) => setError(err instanceof Error ? err.message : "Nao foi possivel carregar a previsao financeira."))
      .finally(() => setForecastLoading(false));
  }, [activeModule]);

  useEffect(() => {
    if (activeModule !== "delivery" && activeModule !== "couriers") return;
    setDeliveryLoading(true);
    financeApi.deliveryOverview()
      .then(setDeliveryOverview)
      .catch((err) => setBankError(err instanceof Error ? err.message : "Nao foi possivel carregar os repasses dos entregadores."))
      .finally(() => setDeliveryLoading(false));
  }, [activeModule]);

  const newTransaction = (entryType?: FinanceEntryType) => {
    setActiveModule("registries");
    setRegistryPanel("transaction");
    if (entryType) setTransactionDraft((draft) => ({ ...draft, entry_type: entryType, category_id: null }));
  };

  const load = () => {
    setLoading(true);
    setError("");
    financeApi.overview()
      .then(setData)
      .catch((err) => setError(err instanceof Error ? err.message : "Nao foi possivel carregar Financeiro."))
      .finally(() => setLoading(false));
  };

  const loadBankStatements = () => {
    setBankLoading(true);
    setBankError("");
    financeApi.listBankStatements()
      .then(setBankStatements)
      .catch((err) => setBankError(err instanceof Error ? err.message : "Nao foi possivel carregar os extratos."))
      .finally(() => setBankLoading(false));
  };

  const loadReconciliation = (statementId: string) => {
    setSelectedStatement(statementId);
    setBankLoading(true);
    setBankError("");
    financeApi.listBankReconciliation(statementId)
      .then(setReconciliationLines)
      .catch((err) => setBankError(err instanceof Error ? err.message : "Nao foi possivel carregar a conciliacao."))
      .finally(() => setBankLoading(false));
  };

  const matchBankLine = async (lineId: string, transactionId: string) => {
    setSaving(`match-${lineId}`);
    setBankError("");
    try {
      await financeApi.matchBankStatementLine(lineId, transactionId);
      if (selectedStatement) loadReconciliation(selectedStatement);
      loadBankStatements();
    } catch (err) {
      setBankError(err instanceof Error ? err.message : "Nao foi possivel conciliar a linha.");
    } finally {
      setSaving("");
    }
  };

  const changeBankLineStatus = async (lineId: string, action: "unmatch" | "ignore") => {
    const reason = window.prompt(action === "unmatch" ? "Informe o motivo da desconciliacao:" : "Informe o motivo para ignorar esta linha:");
    if (!reason?.trim()) return;
    setSaving(`${action}-${lineId}`);
    setBankError("");
    try {
      if (action === "unmatch") await financeApi.unmatchBankStatementLine(lineId, reason.trim());
      else await financeApi.ignoreBankStatementLine(lineId, reason.trim());
      if (selectedStatement) loadReconciliation(selectedStatement);
      loadBankStatements();
    } catch (err) {
      setBankError(err instanceof Error ? err.message : "Nao foi possivel atualizar a linha bancaria.");
    } finally {
      setSaving("");
    }
  };

  useEffect(() => {
    load();
  }, []);

  useEffect(() => {
    if (activeModule === "banks") loadBankStatements();
  }, [activeModule]);

  useEffect(() => {
    if (activeModule !== "cards") return;
    setPaymentLoading(true);
    financeApi.paymentOverview()
      .then(setPaymentOverview)
      .catch((err) => setBankError(err instanceof Error ? err.message : "Nao foi possivel carregar pagamentos."))
      .finally(() => setPaymentLoading(false));
  }, [activeModule]);

  const importBankFile = async (file: File) => {
    if (!data?.accounts.length) {
      setBankError("Cadastre uma conta financeira antes de importar um extrato.");
      return;
    }
    setSaving("bank-import");
    setBankError("");
    try {
      const content = await file.text();
      const lines = parseBankCsv(content);
      const fileHash = await sha256File(file);
      const payload: FinanceBankStatementImportInput = {
        account_id: data.accounts.find((account) => account.account_type === "bank")?.id ?? data.accounts[0].id,
        source: "csv",
        external_reference: file.name,
        file_hash: fileHash,
        period_start: lines.map((line) => line.transaction_date).sort()[0],
        period_end: lines.map((line) => line.transaction_date).sort().at(-1),
        lines,
      };
      await financeApi.importBankStatement(payload);
      loadBankStatements();
    } catch (err) {
      setBankError(err instanceof Error ? err.message : "Nao foi possivel importar o extrato.");
    } finally {
      setSaving("");
      if (bankFileRef.current) bankFileRef.current.value = "";
    }
  };

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
      const matchesModule = activeModule === "payables" ? transaction.entry_type === "expense" : activeModule === "receivables" ? transaction.entry_type === "income" : true;
      return matchesQuery && matchesStatus && matchesEntryType && matchesModule;
    });
  }, [data?.transactions, transactionEntryType, transactionQuery, transactionStatus, activeModule]);

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

  const createBudget = async () => {
    if (!budgetDraft.name.trim() || budgetDraft.lines.some((line) => Number(line.planned_amount) < 0)) return;
    setBudgetSaving(true);
    setError("");
    try {
      await financeApi.createBudget({ ...budgetDraft, name: budgetDraft.name.trim(), lines: budgetDraft.lines.map((line) => ({ ...line, planned_amount: Number(line.planned_amount || 0) })) });
      setBudgetDraft((draft) => ({ ...draft, name: "", notes: "", lines: [{ category_id: null, cost_center: "", entry_type: "expense", planned_amount: 0, notes: "" }] }));
      setBudgets(await financeApi.listBudgets());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nao foi possivel salvar o orcamento.");
    } finally {
      setBudgetSaving(false);
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

      <div className="grid gap-4 xl:grid-cols-[15rem_minmax(0,1fr)]">
        <aside className="rounded-2xl border border-surface-03 bg-surface-02 p-3" aria-label="Navegação financeira">
          <p className="px-3 pb-3 pt-1 text-[10px] font-black uppercase tracking-[0.18em] text-stone">Áreas financeiras</p>
          <nav className="space-y-1">
            {financeModuleGroups.map((group) => (
              <div key={group.id} className="space-y-1 pb-3 last:pb-0">
                <p className="px-3 pt-2 text-[10px] font-black uppercase tracking-[0.14em] text-gold/80">{group.title}</p>
                {group.modules.map((module) => {
                  const Icon = module.icon;
                  const selected = activeModule === module.id;
                  return (
                    <button key={module.id} type="button" onClick={() => selectModule(module.id)} className={`flex w-full items-center gap-2.5 rounded-xl px-3 py-2.5 text-left text-xs font-bold transition ${focusClass} ${selected ? "bg-gold text-black" : "text-stone hover:bg-surface-03 hover:text-cream"}`} aria-current={selected ? "page" : undefined}>
                      <Icon size={15} aria-hidden="true" />
                      <span className="min-w-0 flex-1 truncate">{module.title}</span>
                      {module.status === "Não disponível" && <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-stone/60" aria-label="Não disponível" />}
                    </button>
                  );
                })}
              </div>
            ))}
            <div className="border-t border-surface-03 pt-3">
              <p className="px-3 pt-1 text-[10px] font-black uppercase tracking-[0.14em] text-gold/80">Operação e dados</p>
              {operationalPages.map((module) => {
                const Icon = module.icon;
                const selected = activeModule === module.id;
                return <button key={module.id} type="button" onClick={() => selectModule(module.id)} className={`mt-1 flex w-full items-center gap-2.5 rounded-xl px-3 py-2.5 text-left text-xs font-bold transition ${focusClass} ${selected ? "bg-gold text-black" : "text-stone hover:bg-surface-03 hover:text-cream"}`} aria-current={selected ? "page" : undefined}><Icon size={15} aria-hidden="true" /><span className="truncate">{module.title}</span></button>;
              })}
            </div>
          </nav>
        </aside>

        <div className="min-w-0 space-y-4">
          <div className="flex flex-col gap-3 rounded-2xl border border-surface-03 bg-surface-02 p-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex min-w-0 items-center gap-3">
              <div className="rounded-xl border border-gold/25 bg-gold/10 p-2.5 text-gold"><CurrentIcon size={19} aria-hidden="true" /></div>
              <div className="min-w-0"><p className="text-[10px] font-black uppercase tracking-[0.16em] text-stone">Financeiro / {currentModule.title}</p><h3 ref={headingRef} tabIndex={-1} className="mt-1 text-lg font-black text-cream">{currentModule.title}</h3></div>
            </div>
            <div className="flex flex-wrap gap-2">
              {isTransactionArea && <button type="button" onClick={() => newTransaction(activeModule === "payables" ? "expense" : activeModule === "receivables" ? "income" : undefined)} className={buttonClass}><Plus size={15} aria-hidden="true" /> Novo lançamento</button>}
              {activeModule === "registries" && <span className="inline-flex min-h-11 items-center gap-2 rounded-xl border border-surface-03 bg-surface-01 px-3.5 py-2.5 text-sm font-bold text-stone"><Tags size={15} aria-hidden="true" /> Cadastros e lançamentos</span>}
            </div>
          </div>

          {activeModule !== "overview" && activeModule !== "registries" && activeModule !== "banks" && activeModule !== "planning" && activeModule !== "bi" && !isTransactionArea && (
            <div className={`${panelClass} min-h-64 flex flex-col items-center justify-center text-center`}>
              <div className="rounded-2xl border border-surface-03 bg-surface-01 p-4 text-gold"><CurrentIcon size={28} aria-hidden="true" /></div>
              <h4 className="mt-4 text-xl font-black text-cream">{currentModule.title}</h4>
              <p className="mt-2 max-w-xl text-sm leading-relaxed text-stone">{currentModule.description}</p>
              <span className={`mt-4 rounded-full border px-3 py-1.5 text-[10px] font-black uppercase tracking-wide ${financeModuleStatuses[currentModule.status].className}`}>{currentModule.status}</span>
            </div>
          )}

          {activeModule === "bi" && (
            <div className="space-y-5">
              <div className={panelClass}>
                <CardHeading icon={TrendingUp} title="Análise financeira" description="Valores por competência, sem alterar os lançamentos. Use o período para comparar origem, categoria, centro de custo e canal." />
                <div className="mt-4 grid gap-3 sm:grid-cols-[1fr_1fr_auto]"><input aria-label="Início do BI" className={inputClass} type="date" value={biPeriod.date_from} onChange={(event) => setBiPeriod({ ...biPeriod, date_from: event.target.value })} /><input aria-label="Fim do BI" className={inputClass} type="date" value={biPeriod.date_to} onChange={(event) => setBiPeriod({ ...biPeriod, date_to: event.target.value })} /><button type="button" className={buttonClass} onClick={() => setBiPeriod({ ...biPeriod })} disabled={biLoading}>{biLoading ? <Loader2 size={15} className="animate-spin" /> : <RefreshCw size={15} />} Atualizar</button></div>
              </div>
              {biLoading ? <div className="flex min-h-40 items-center justify-center rounded-2xl border border-surface-03 bg-surface-02 text-stone"><Loader2 size={22} className="mr-2 animate-spin text-gold" />Carregando BI...</div> : bi && <>
                <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"><Metric title="Receitas" value={currency(bi.total_income)} subtitle={`${bi.transaction_count} lançamentos no período`} icon={ArrowUpCircle} tone="success" /><Metric title="Despesas" value={currency(bi.total_expense)} subtitle="Valores por competência" icon={ArrowDownCircle} tone="warn" /><Metric title="Resultado" value={currency(bi.result)} subtitle="Receitas menos despesas" icon={BarChart3} tone={bi.result >= 0 ? "success" : "warn"} /><Metric title="Período" value={`${bi.date_from} a ${bi.date_to}`} subtitle="Filtro aplicado" icon={CalendarCheck2} /></div>
                <div className="grid gap-5 xl:grid-cols-2"><DimensionList title="Por origem" icon={ReceiptText} rows={bi.by_origin.map((row) => ({ label: row.origin_type, entry_type: row.entry_type, amount: row.amount, count: row.count }))} /><DimensionList title="Por canal" icon={Landmark} rows={bi.by_channel} /><DimensionList title="Por categoria" icon={Tags} rows={bi.by_category} /><DimensionList title="Por centro de custo" icon={SlidersHorizontal} rows={bi.by_cost_center} /></div>
              </>}
            </div>
          )}

          {activeModule === "planning" && (
            <div className="space-y-5">
              <div className={panelClass}>
                <CardHeading icon={CalendarCheck2} title="Previsão de saldo" description="A projeção usa somente lançamentos já registrados: pendentes e parciais usam o vencimento; liquidados usam a competência. Nenhum valor é inventado." />
              </div>
              {forecastLoading ? <div className="flex min-h-40 items-center justify-center rounded-2xl border border-surface-03 bg-surface-02 text-stone"><Loader2 size={22} className="mr-2 animate-spin text-gold" />Carregando previsão...</div> : forecast && <div className={`${panelClass} overflow-x-auto`}>
                <div className="mb-4 flex flex-wrap items-center justify-between gap-3"><div><h4 className="font-black text-cream">Próximos {forecast.months} meses</h4><p className="mt-1 text-xs text-stone">{forecast.methodology}</p></div><span className="rounded-full border border-surface-03 bg-surface-01 px-3 py-1 text-xs font-bold text-stone">Saldo inicial {currency(forecast.periods[0]?.opening_balance || 0)}</span></div>
                <table className="w-full min-w-[760px] text-left text-sm"><thead className="border-b border-surface-03 text-xs uppercase tracking-wide text-stone"><tr><th className="px-3 py-3">Período</th><th className="px-3 py-3 text-right">Entradas</th><th className="px-3 py-3 text-right">Saídas</th><th className="px-3 py-3 text-right">Resultado</th><th className="px-3 py-3 text-right">Saldo final</th><th className="px-3 py-3 text-right">Fontes</th></tr></thead><tbody>{forecast.periods.map((period) => <tr key={period.period_start} className="border-b border-surface-03/70"><td className="px-3 py-3 font-bold text-cream">{period.period_start} a {period.period_end}</td><td className="px-3 py-3 text-right text-emerald-300">{currency(period.projected_income)}</td><td className="px-3 py-3 text-right text-amber-300">{currency(period.projected_expense)}</td><td className={`px-3 py-3 text-right font-bold ${period.projected_result >= 0 ? "text-emerald-300" : "text-red-300"}`}>{currency(period.projected_result)}</td><td className="px-3 py-3 text-right font-black text-cream">{currency(period.closing_balance)}</td><td className="px-3 py-3 text-right text-stone">{period.source_count}</td></tr>)}</tbody></table>
              </div>}
            </div>
          )}

          {activeModule === "banks" && (
            <div className="space-y-4">
              <div className={`${panelClass} flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between`}>
                <div>
                  <p className="text-xs font-black uppercase tracking-[0.16em] text-gold">Extratos bancarios</p>
                  <h4 className="mt-1 text-xl font-black text-cream">Importacao e pendencias de conciliacao</h4>
                  <p className="mt-1 max-w-2xl text-sm leading-relaxed text-stone">Importe um CSV para registrar as movimentacoes sem alterar lancamentos existentes. A conciliacao sera confirmada em uma etapa separada.</p>
                </div>
                <div>
                  <input
                    ref={bankFileRef}
                    type="file"
                    accept=".csv,text/csv"
                    className="sr-only"
                    onChange={(event) => {
                      const file = event.target.files?.[0];
                      if (file) void importBankFile(file);
                    }}
                  />
                  <button type="button" onClick={() => bankFileRef.current?.click()} disabled={saving === "bank-import" || bankLoading} className={buttonClass}>
                    {saving === "bank-import" ? <Loader2 size={15} className="animate-spin" /> : <Plus size={15} />}
                    Importar CSV
                  </button>
                </div>
              </div>

              {bankError && <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-200" role="alert">{bankError}</div>}

              <div className={`${panelClass} overflow-x-auto`}>
                <div className="mb-4 flex items-center justify-between gap-3">
                  <div>
                    <h4 className="font-black text-cream">Extratos importados</h4>
                    <p className="mt-1 text-xs text-stone">Cada arquivo importado fica preservado e auditavel.</p>
                  </div>
                  <span className="rounded-full border border-surface-03 bg-surface-01 px-3 py-1 text-xs font-bold text-stone">{bankStatements.length} extratos</span>
                </div>
                {bankLoading ? (
                  <div className="flex min-h-32 items-center justify-center text-sm text-stone"><Loader2 size={18} className="mr-2 animate-spin text-gold" /> Carregando extratos...</div>
                ) : bankStatements.length === 0 ? (
                  <EmptyText icon={Landmark} text="Nenhum extrato importado para esta empresa." />
                ) : (
                  <div className="min-w-[720px] divide-y divide-surface-03">
                    <div className="grid grid-cols-[1.5fr_1fr_1fr_1fr_auto_auto] gap-4 px-3 pb-3 text-[10px] font-black uppercase tracking-wide text-stone">
                      <span>Conta</span><span>Periodo</span><span>Movimentacoes</span><span>Pendencias</span><span>Status</span><span />
                    </div>
                    {bankStatements.map((statement) => (
                      <div key={statement.id} className="grid grid-cols-[1.5fr_1fr_1fr_1fr_auto_auto] items-center gap-4 px-3 py-4 text-sm">
                        <div><p className="font-bold text-cream">{statement.account_name}</p><p className="mt-1 text-xs text-stone">{statement.external_reference || statement.source}</p></div>
                        <span className="text-stone">{statement.period_start || "-"} a {statement.period_end || "-"}</span>
                        <span className="text-stone">{statement.line_count}</span>
                        <span className={statement.unmatched_count ? "font-bold text-amber-300" : "text-emerald-300"}>{statement.unmatched_count}</span>
                        <span className="rounded-full border border-amber-500/25 bg-amber-500/10 px-2 py-1 text-[10px] font-black uppercase text-amber-300">{statement.status}</span>
                        <button type="button" onClick={() => loadReconciliation(statement.id)} className={mutedButtonClass}>Revisar</button>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {selectedStatement && (
                <div className={panelClass}>
                  <div className="mb-4 flex items-center justify-between gap-3">
                    <div><h4 className="font-black text-cream">Linhas para conciliacao</h4><p className="mt-1 text-xs text-stone">Escolha uma sugestao compativel para confirmar o vinculo.</p></div>
                    <span className="rounded-full border border-surface-03 bg-surface-01 px-3 py-1 text-xs font-bold text-stone">{reconciliationLines.length} linhas</span>
                  </div>
                  {reconciliationLines.length === 0 ? <EmptyText icon={ClipboardList} text="Nenhuma linha encontrada neste extrato." /> : (
                    <div className="space-y-3">
                      {reconciliationLines.map((line) => (
                        <div key={line.id} className="rounded-xl border border-surface-03 bg-surface-01 p-4">
                          <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                            <div><p className="font-bold text-cream">{line.description}</p><p className="mt-1 text-xs text-stone">{line.transaction_date} · {line.external_id}</p></div>
                            <div className="text-right"><p className={`font-black ${Number(line.amount) >= 0 ? "text-emerald-300" : "text-amber-300"}`}>{currency(Number(line.amount))}</p><span className="text-[10px] font-black uppercase text-amber-300">{line.reconciliation_status}</span></div>
                          </div>
                          {line.reconciliation_status === "matched" ? (
                            <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
                              <p className="text-xs text-emerald-300">Linha conciliada com o lancamento {line.matched_transaction_id}.</p>
                              <button type="button" onClick={() => void changeBankLineStatus(line.id, "unmatch")} disabled={saving === `unmatch-${line.id}`} className={mutedButtonClass}>{saving === `unmatch-${line.id}` && <Loader2 size={14} className="animate-spin" />} Desconciliar</button>
                            </div>
                          ) : (
                            <div className="mt-3 space-y-2">
                              {line.candidates.length === 0 ? <p className="text-xs text-stone">Nenhum lancamento compativel encontrado automaticamente.</p> : line.candidates.map((candidate) => (
                                <div key={candidate.id} className="flex flex-col gap-2 rounded-lg border border-surface-03 bg-surface-02 p-3 sm:flex-row sm:items-center sm:justify-between">
                                  <div><p className="text-sm font-bold text-cream">{candidate.description}</p><p className="text-xs text-stone">{candidate.competence_date} · {candidate.id}</p></div>
                                  <button type="button" onClick={() => void matchBankLine(line.id, candidate.id)} disabled={saving === `match-${line.id}`} className={buttonClass}>{saving === `match-${line.id}` && <Loader2 size={14} className="animate-spin" />} Conciliar</button>
                                </div>
                              ))}
                              {line.reconciliation_status !== "ignored" && <button type="button" onClick={() => void changeBankLineStatus(line.id, "ignore")} disabled={saving === `ignore-${line.id}`} className="text-xs font-bold text-stone underline decoration-stone/40 underline-offset-4 hover:text-cream">Ignorar linha com justificativa</button>}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
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

      {!loading && (data || activeModule === "registries") && (
        <>
          {activeModule === "overview" && (
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

              <FinanceModules />

              <div className="grid gap-5 xl:grid-cols-[1.15fr_1fr_1fr]">
                <DimensionList title="DRE por grupo" icon={BarChart3} featured rows={data.management.dre_lines.map((item) => ({ label: item.group, entry_type: item.entry_type, amount: item.amount, count: 1 }))} />
                <DimensionList title="Por canal" icon={Landmark} rows={data.management.by_channel} />
                <DimensionList title="Por categoria" icon={Tags} rows={data.management.by_category} />
                <DimensionList title="Por centro de custo" icon={SlidersHorizontal} rows={data.management.by_cost_center} />
              </div>
            </>
          )}

          {activeModule === "cash" && (
            <div className="space-y-5">
              <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                <Metric title="Saldo consolidado" value={currency(data.summary.balance)} subtitle="Saldo inicial mais liquidações" icon={Wallet} tone={data.summary.balance >= 0 ? "success" : "warn"} />
                <Metric title="Receitas liquidadas" value={currency(data.management.cash_realized_income)} subtitle="Entradas efetivamente recebidas" icon={ArrowUpCircle} tone="success" />
                <Metric title="Despesas liquidadas" value={currency(data.management.cash_realized_expense)} subtitle="Saídas efetivamente pagas" icon={ArrowDownCircle} tone="warn" />
                <Metric title="Resultado de caixa" value={currency(data.management.cash_realized_result)} subtitle="Receitas menos despesas" icon={TrendingUp} tone={data.management.cash_realized_result >= 0 ? "success" : "warn"} />
              </div>

              <div className="grid gap-5 xl:grid-cols-[1.1fr_1fr]">
                <div className={panelClass}>
                  <CardHeading icon={Landmark} title="Contas e saldos" description="Saldo inicial e posição calculada a partir das liquidações." />
                  <div className="mt-4 grid gap-3 sm:grid-cols-2">
                    {data.accounts.length === 0 ? (
                      <p className="rounded-xl border border-dashed border-surface-03 p-5 text-sm text-stone">Nenhuma conta cadastrada.</p>
                    ) : data.accounts.map((account) => (
                      <div key={account.id} className="rounded-xl border border-surface-03 bg-surface-01 p-4">
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <p className="font-black text-cream">{account.name}</p>
                            <p className="mt-1 text-xs uppercase tracking-wide text-stone">{account.account_type}</p>
                          </div>
                          <Wallet size={18} className="text-gold" aria-hidden="true" />
                        </div>
                        <p className={`mt-4 text-2xl font-black ${account.current_balance >= 0 ? "text-emerald-200" : "text-amber-200"}`}>{currency(account.current_balance)}</p>
                        <p className="mt-1 text-xs text-stone">Saldo inicial: {currency(account.opening_balance)}</p>
                      </div>
                    ))}
                  </div>
                </div>

                <div className={panelClass}>
                  <CardHeading icon={ReceiptText} title="Últimas movimentações" description="Lançamentos com baixa parcial ou integral." />
                  <div className="mt-4 space-y-2">
                    {data.transactions.filter((transaction) => transaction.status === "partial" || transaction.status === "paid").slice(0, 8).map((transaction) => (
                      <div key={transaction.id} className="flex items-center justify-between gap-3 rounded-xl border border-surface-03 bg-surface-01 px-3 py-3">
                        <div className="min-w-0">
                          <p className="truncate text-sm font-bold text-cream">{transaction.description}</p>
                          <p className="mt-1 truncate text-xs text-stone">{transaction.account_name || "Conta não informada"} · {transaction.paid_at || transaction.competence_date}</p>
                        </div>
                        <p className={`shrink-0 text-sm font-black ${transaction.entry_type === "income" ? "text-emerald-300" : "text-amber-300"}`}>{transaction.entry_type === "income" ? "+" : "-"}{currency(transaction.paid_amount || transaction.amount)}</p>
                      </div>
                    ))}
                    {data.transactions.filter((transaction) => transaction.status === "partial" || transaction.status === "paid").length === 0 && <p className="rounded-xl border border-dashed border-surface-03 p-5 text-sm text-stone">Nenhuma movimentação liquidada.</p>}
                  </div>
                </div>
              </div>
            </div>
          )}

          {activeModule === "cards" && (
            <div className="space-y-5">
              {paymentLoading ? (
                <div className="flex min-h-40 items-center justify-center rounded-2xl border border-surface-03 bg-surface-02 text-stone"><Loader2 size={22} className="mr-2 animate-spin text-gold" />Carregando pagamentos...</div>
              ) : paymentOverview && (
                <>
                  <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
                    <Metric title="Pagamentos" value={String(paymentOverview.total_count)} subtitle="Registros no checkout" icon={CreditCard} tone="success" />
                    <Metric title="Volume bruto" value={currency(paymentOverview.total_gross_amount)} subtitle="Valor dos pagamentos" icon={ReceiptText} tone="success" />
                    <Metric title="Tarifas vinculadas" value={currency(paymentOverview.total_linked_fee_amount)} subtitle="Tarifas registradas no financeiro" icon={SlidersHorizontal} tone="warn" />
                  </div>
                  <div className={panelClass}>
                    <CardHeading icon={CreditCard} title="Cartões e Pix" description="Volume por método, gateway, provedor e status. A conciliação de repasse depende de tarifas e liquidações vinculadas." />
                    <div className="mt-4 overflow-x-auto">
                      {paymentOverview.summaries.length === 0 ? <p className="rounded-xl border border-dashed border-surface-03 p-5 text-sm text-stone">Nenhum pagamento registrado.</p> : <table className="w-full min-w-[720px] text-left text-sm">
                        <thead className="border-b border-surface-03 text-xs uppercase tracking-wide text-stone"><tr><th className="px-3 py-3">Método</th><th className="px-3 py-3">Gateway</th><th className="px-3 py-3">Status</th><th className="px-3 py-3">Quantidade</th><th className="px-3 py-3 text-right">Bruto</th><th className="px-3 py-3 text-right">Tarifa vinculada</th></tr></thead>
                        <tbody>{paymentOverview.summaries.map((summary) => <tr key={`${summary.method}-${summary.gateway}-${summary.provider}-${summary.status}`} className="border-b border-surface-03/70"><td className="px-3 py-3 font-bold text-cream">{summary.method}</td><td className="px-3 py-3 text-stone">{summary.gateway} · {summary.provider}</td><td className="px-3 py-3 text-stone">{summary.status}</td><td className="px-3 py-3 text-stone">{summary.count}</td><td className="px-3 py-3 text-right font-bold text-cream">{currency(summary.gross_amount)}</td><td className="px-3 py-3 text-right font-bold text-amber-200">{currency(summary.linked_fee_amount)}</td></tr>)}</tbody>
                      </table>}
                    </div>
                  </div>
                </>
              )}
            </div>
          )}

          {activeModule === "cashflow" && (
            <div className="space-y-5">
              {cashFlowLoading ? (
                <div className="flex min-h-40 items-center justify-center rounded-2xl border border-surface-03 bg-surface-02 text-stone"><Loader2 size={22} className="mr-2 animate-spin text-gold" />Carregando fluxo de caixa...</div>
              ) : cashFlow && (
                <>
                  <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                    <Metric title="Saldo inicial" value={currency(cashFlow.opening_balance)} subtitle={`${cashFlow.date_from} a ${cashFlow.date_to}`} icon={Wallet} tone="success" />
                    <Metric title="Realizado" value={currency(cashFlow.realized_result)} subtitle={`Entradas ${currency(cashFlow.realized_income)} · Saídas ${currency(cashFlow.realized_expense)}`} icon={CheckCircle2} tone={cashFlow.realized_result >= 0 ? "success" : "warn"} />
                    <Metric title="Projetado" value={currency(cashFlow.projected_result)} subtitle={`Entradas ${currency(cashFlow.projected_income)} · Saídas ${currency(cashFlow.projected_expense)}`} icon={TrendingUp} tone={cashFlow.projected_result >= 0 ? "success" : "warn"} />
                    <Metric title="Saldo projetado" value={currency(cashFlow.closing_projected_balance)} subtitle={`Saldo realizado ${currency(cashFlow.closing_realized_balance)}`} icon={LineChart} tone={cashFlow.closing_projected_balance >= 0 ? "success" : "warn"} />
                  </div>
                  <div className={panelClass}>
                    <CardHeading icon={LineChart} title="Extrato do fluxo de caixa" description="Cada linha mostra o efeito projetado e o valor já realizado do lançamento, sem misturar cadastros auxiliares." />
                    <div className="mt-4 overflow-x-auto">
                      {cashFlow.lines.length === 0 ? <p className="rounded-xl border border-dashed border-surface-03 p-5 text-sm text-stone">Nenhum lançamento no período atual.</p> : <table className="w-full min-w-[820px] text-left text-sm">
                        <thead className="border-b border-surface-03 text-xs uppercase tracking-wide text-stone"><tr><th className="px-3 py-3">Data</th><th className="px-3 py-3">Lançamento</th><th className="px-3 py-3">Conta · Categoria</th><th className="px-3 py-3">Status</th><th className="px-3 py-3 text-right">Projetado</th><th className="px-3 py-3 text-right">Realizado</th></tr></thead>
                        <tbody>{cashFlow.lines.map((line) => <tr key={line.id} className="border-b border-surface-03/70"><td className="px-3 py-3 text-stone">{line.movement_date}</td><td className="px-3 py-3 font-bold text-cream">{line.description}</td><td className="px-3 py-3 text-stone">{line.account_name || "Conta não informada"} · {line.category_name || "Sem categoria"}</td><td className="px-3 py-3 text-stone">{line.status}</td><td className={`px-3 py-3 text-right font-bold ${line.projected_amount >= 0 ? "text-emerald-300" : "text-amber-300"}`}>{currency(line.projected_amount)}</td><td className={`px-3 py-3 text-right font-bold ${line.realized_amount >= 0 ? "text-emerald-300" : "text-amber-300"}`}>{currency(line.realized_amount)}</td></tr>)}</tbody>
                      </table>}
                    </div>
                  </div>
                </>
              )}
            </div>
          )}

          {(activeModule === "dre" || activeModule === "cmv") && (
            <div className="space-y-5">
              <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                <Metric title="Receita competência" value={currency(data.management.accrual_income)} subtitle="Lançamentos financeiros de receita" icon={ArrowUpCircle} tone="success" />
                <Metric title="CMV operacional" value={currency(data.management.operational_cmv.cost_total)} subtitle={`${data.management.operational_cmv.snapshot_count} snapshots · ${data.management.operational_cmv.pending_count} pendentes`} icon={Tags} tone={data.management.operational_cmv.pending_count ? "warn" : "success"} />
                <Metric title="Despesas competência" value={currency(data.management.accrual_expense)} subtitle="Lançamentos financeiros de despesa" icon={ArrowDownCircle} tone="warn" />
                <Metric title="Resultado competência" value={currency(data.management.accrual_result)} subtitle={`CMV ${data.management.operational_cmv.status === "complete" ? "disponível separadamente" : "pendente"}`} icon={BarChart3} tone={data.management.accrual_result >= 0 ? "success" : "warn"} />
              </div>
              <div className={panelClass}>
                <CardHeading icon={BarChart3} title="DRE e CMV operacional" description="A DRE mantém competência financeira separada do CMV operacional. O custo é exibido apenas quando existe snapshot histórico; nenhuma estimativa atual de ficha técnica é lançada automaticamente na DRE." />
                <div className="mt-4 grid gap-3 md:grid-cols-3">
                  <div className="rounded-xl border border-surface-03 bg-surface-01 p-4"><p className="text-xs font-black uppercase tracking-wide text-stone">Status da DRE</p><p className="mt-2 text-lg font-black text-gold">{data.management.dre_label}</p></div>
                  <div className="rounded-xl border border-surface-03 bg-surface-01 p-4"><p className="text-xs font-black uppercase tracking-wide text-stone">Receita dos snapshots</p><p className="mt-2 text-lg font-black text-cream">{currency(data.management.operational_cmv.sale_total)}</p></div>
                  <div className="rounded-xl border border-surface-03 bg-surface-01 p-4"><p className="text-xs font-black uppercase tracking-wide text-stone">Percentual CMV</p><p className="mt-2 text-lg font-black text-cream">{data.management.operational_cmv.cmv_percent == null ? "-" : `${data.management.operational_cmv.cmv_percent.toFixed(2)}%`}</p></div>
                </div>
              </div>
            </div>
          )}

          {activeModule === "budget" && (
            <div className="space-y-5">
              <div className={panelClass}>
                <CardHeading icon={Target} title="Novo orçamento" description="Defina um período e linhas planejadas. O realizado é calculado somente a partir dos lançamentos financeiros do mesmo período." />
                <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                  <input className={inputClass} placeholder="Nome do orçamento" value={budgetDraft.name} onChange={(event) => setBudgetDraft({ ...budgetDraft, name: event.target.value })} />
                  <input aria-label="Início do orçamento" className={inputClass} type="date" value={budgetDraft.period_start} onChange={(event) => setBudgetDraft({ ...budgetDraft, period_start: event.target.value })} />
                  <input aria-label="Fim do orçamento" className={inputClass} type="date" value={budgetDraft.period_end} onChange={(event) => setBudgetDraft({ ...budgetDraft, period_end: event.target.value })} />
                  <button type="button" className={buttonClass} onClick={createBudget} disabled={budgetSaving || !budgetDraft.name.trim()}>{budgetSaving ? <Loader2 size={15} className="animate-spin" /> : <Plus size={15} />} Criar orçamento</button>
                </div>
                <div className="mt-3 grid gap-3 md:grid-cols-[1fr_12rem_12rem]">
                  <select aria-label="Categoria orçamentária" className={inputClass} value={budgetDraft.lines[0]?.category_id || ""} onChange={(event) => setBudgetDraft({ ...budgetDraft, lines: [{ ...budgetDraft.lines[0], category_id: event.target.value || null }] })}>
                    <option value="">Todas as categorias</option>
                    {(data?.categories ?? []).filter((category) => category.entry_type === budgetDraft.lines[0]?.entry_type).map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}
                  </select>
                  <input aria-label="Centro de custo orçamentário" className={inputClass} placeholder="Centro de custo" value={budgetDraft.lines[0]?.cost_center || ""} onChange={(event) => setBudgetDraft({ ...budgetDraft, lines: [{ ...budgetDraft.lines[0], cost_center: event.target.value }] })} />
                  <input aria-label="Valor planejado" className={inputClass} type="number" min="0" step="0.01" placeholder="Valor planejado" value={budgetDraft.lines[0]?.planned_amount || ""} onChange={(event) => setBudgetDraft({ ...budgetDraft, lines: [{ ...budgetDraft.lines[0], planned_amount: Number(event.target.value || 0) }] })} />
                </div>
              </div>
              {budgetLoading ? <div className="flex min-h-40 items-center justify-center rounded-2xl border border-surface-03 bg-surface-02 text-stone"><Loader2 size={22} className="mr-2 animate-spin text-gold" />Carregando orçamentos...</div> : <div className="space-y-4">
                {budgets.length === 0 ? <div className={panelClass}><p className="text-sm text-stone">Nenhum orçamento cadastrado.</p></div> : budgets.map((budget) => (
                  <div key={budget.id} className={panelClass}>
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between"><div><p className="text-lg font-black text-cream">{budget.name}</p><p className="mt-1 text-sm text-stone">{budget.period_start} a {budget.period_end} · {budget.status}</p></div><p className={`text-xl font-black ${budget.variance_result <= 0 ? "text-emerald-300" : "text-amber-300"}`}>{currency(budget.variance_result)} <span className="text-xs font-bold text-stone">variação</span></p></div>
                    <div className="mt-4 grid gap-3 sm:grid-cols-4"><Metric title="Planejado receitas" value={currency(budget.planned_income)} icon={ArrowUpCircle} tone="success" /><Metric title="Realizado receitas" value={currency(budget.actual_income)} icon={CheckCircle2} tone="success" /><Metric title="Planejado despesas" value={currency(budget.planned_expense)} icon={ArrowDownCircle} tone="warn" /><Metric title="Realizado despesas" value={currency(budget.actual_expense)} icon={TrendingUp} tone="warn" /></div>
                    <div className="mt-4 overflow-x-auto"><table className="w-full min-w-[680px] text-left text-sm"><thead className="border-b border-surface-03 text-xs uppercase tracking-wide text-stone"><tr><th className="px-3 py-3">Categoria</th><th className="px-3 py-3">Centro</th><th className="px-3 py-3">Tipo</th><th className="px-3 py-3 text-right">Planejado</th><th className="px-3 py-3 text-right">Realizado</th><th className="px-3 py-3 text-right">Variação</th></tr></thead><tbody>{budget.lines.map((line) => <tr key={line.id} className="border-b border-surface-03/70"><td className="px-3 py-3 text-cream">{line.category_name || "Todas"}</td><td className="px-3 py-3 text-stone">{line.cost_center || "Todos"}</td><td className="px-3 py-3 text-stone">{line.entry_type}</td><td className="px-3 py-3 text-right text-cream">{currency(line.planned_amount)}</td><td className="px-3 py-3 text-right text-cream">{currency(line.actual_amount)}</td><td className={`px-3 py-3 text-right font-bold ${line.variance_amount <= 0 ? "text-emerald-300" : "text-amber-300"}`}>{currency(line.variance_amount)}</td></tr>)}</tbody></table></div>
                  </div>
                ))}
              </div>}
            </div>
          )}

          {(activeModule === "delivery" || activeModule === "couriers") && (
            <div className="space-y-5">
              {deliveryLoading ? (
                <div className="flex min-h-40 items-center justify-center rounded-2xl border border-surface-03 bg-surface-02 text-stone"><Loader2 size={22} className="mr-2 animate-spin text-gold" />Carregando repasses...</div>
              ) : deliveryOverview && (
                <>
                  <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                    <Metric title="Repasses" value={String(deliveryOverview.total_count)} subtitle="Ganhos registrados" icon={Route} tone="success" />
                    <Metric title="Pendentes" value={currency(deliveryOverview.pending_amount)} subtitle="Aguardando pagamento" icon={CalendarCheck2} tone="warn" />
                    <Metric title="Pagos" value={currency(deliveryOverview.paid_amount)} subtitle="Repasses confirmados" icon={CheckCircle2} tone="success" />
                    <Metric title="Cancelados" value={currency(deliveryOverview.cancelled_amount)} subtitle="Sem efeito no caixa" icon={AlertTriangle} tone="warn" />
                  </div>
                  <div className={panelClass}>
                    <CardHeading icon={Route} title="Gestão financeira de entregadores" description="Ganhos provenientes da operação logística, agrupados por entregador e status. O pagamento continua usando o fluxo oficial de repasses." />
                    <div className="mt-4 overflow-x-auto">
                      {deliveryOverview.summaries.length === 0 ? <p className="rounded-xl border border-dashed border-surface-03 p-5 text-sm text-stone">Nenhum ganho de entregador registrado.</p> : <table className="w-full min-w-[620px] text-left text-sm">
                        <thead className="border-b border-surface-03 text-xs uppercase tracking-wide text-stone"><tr><th className="px-3 py-3">Entregador</th><th className="px-3 py-3">Status</th><th className="px-3 py-3">Quantidade</th><th className="px-3 py-3 text-right">Valor</th></tr></thead>
                        <tbody>{deliveryOverview.summaries.map((summary) => <tr key={`${summary.delivery_person_id}-${summary.status}`} className="border-b border-surface-03/70"><td className="px-3 py-3 font-bold text-cream">{summary.delivery_person_name}</td><td className="px-3 py-3 text-stone">{summary.status}</td><td className="px-3 py-3 text-stone">{summary.count}</td><td className="px-3 py-3 text-right font-black text-cream">{currency(summary.amount)}</td></tr>)}</tbody>
                      </table>}
                    </div>
                  </div>
                </>
              )}
            </div>
          )}

          {activeModule === "registries" && <div className="space-y-5">
            <div className="grid gap-3 rounded-2xl border border-surface-03 bg-surface-02 p-3 sm:grid-cols-2 xl:grid-cols-4" aria-label="Ações de cadastro financeiro">
              {([
                ["account", Landmark, "Nova conta", "Banco, caixa ou carteira"],
                ["category", Tags, "Nova categoria", "Classificação da DRE"],
                ["counterparty", Users, "Novo favorecido", "Fornecedor ou parceiro"],
                ["transaction", ReceiptText, "Novo lançamento", "Receita ou despesa"],
              ] as const).map(([panel, Icon, title, description]) => (
                <button
                  key={panel}
                  type="button"
                  onClick={() => setRegistryPanel(panel)}
                  aria-pressed={registryPanel === panel}
                  className={`flex min-h-16 items-center gap-3 rounded-xl border px-3 py-3 text-left transition ${registryPanel === panel ? "border-gold/60 bg-gold/10 text-cream" : "border-surface-03 bg-surface-01 text-stone hover:border-gold/40 hover:text-cream"} ${focusClass}`}
                >
                  <span className="rounded-lg border border-current/20 p-2"><Icon size={17} aria-hidden="true" /></span>
                  <span className="min-w-0">
                    <span className="block text-sm font-black">{title}</span>
                    <span className="mt-0.5 block truncate text-xs opacity-75">{description}</span>
                  </span>
                </button>
              ))}
            </div>

            <div className={`${panelClass} flex flex-col`}>
              {registryPanel === "account" && <>
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
              </>}

              {registryPanel === "category" && <>
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
              </>}

              {registryPanel === "counterparty" && <>
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
              </>}

              {registryPanel === "transaction" && <>
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
                  {(data?.accounts ?? []).map((account) => <option key={account.id} value={account.id}>{account.name}</option>)}
                </select>
                <select aria-label="Favorecido do lancamento" className={inputClass} value={transactionDraft.counterparty_id || ""} onChange={(event) => {
                  const selected = (data?.counterparties ?? []).find((item) => item.id === event.target.value);
                  setTransactionDraft({
                    ...transactionDraft,
                    counterparty_id: event.target.value || null,
                    counterparty_type: selected?.counterparty_type ?? transactionDraft.counterparty_type,
                    counterparty_name: selected?.name ?? "",
                    counterparty_document: selected?.document ?? "",
                  });
                }}>
                  <option value="">Sem favorecido</option>
                  {(data?.counterparties ?? []).map((counterparty) => <option key={counterparty.id} value={counterparty.id}>{counterparty.name}</option>)}
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
              </>}
            </div>
          </div>}

          {isTransactionArea && <div className={panelClass}>
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
            </div>}
        </>
      )}
        </div>
      </div>
    </section>
  );
}

function FinanceModules() {
  const moduleCount = financeModuleGroups.reduce((total, group) => total + group.modules.length, 0);

  return (
    <section className={`${panelClass} overflow-hidden`} aria-labelledby="finance-modules-title">
      <div className="flex flex-col gap-3 border-b border-surface-03 pb-5 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="flex items-center gap-2 text-gold">
            <ClipboardList size={18} aria-hidden="true" />
            <p className="text-xs font-black uppercase tracking-[0.16em]">Mapa de cobertura</p>
          </div>
          <h3 id="finance-modules-title" className="mt-2 text-xl font-black tracking-tight text-cream sm:text-2xl">Módulos financeiros</h3>
          <p className="mt-1 max-w-3xl text-sm leading-relaxed text-stone">Cobertura dos submódulos nas quatro abas atuais. Os cards descrevem recursos e limitações; as operações continuam nas abas Resumo e DRE, Cadastros, Lançamentos e Configurações.</p>
        </div>
        <span className="inline-flex w-fit items-center gap-2 rounded-full border border-surface-03 bg-surface-01 px-3 py-1.5 text-[11px] font-black uppercase tracking-wide text-stone">
          <span className="h-2 w-2 rounded-full bg-gold" aria-hidden="true" /> {moduleCount} submódulos · {financeModuleGroups.length} blocos
        </span>
      </div>

      <dl className="mt-5 grid gap-3 rounded-xl border border-surface-03 bg-surface-01/50 p-4 lg:grid-cols-3" aria-label="Legenda de cobertura dos submódulos">
        {(Object.keys(financeModuleStatuses) as FinanceModuleStatus[]).map((status) => (
          <div key={status} className="min-w-0">
            <dt><span className={`inline-flex rounded-full border px-2 py-1 text-[10px] font-black uppercase tracking-wide ${financeModuleStatuses[status].className}`}>{status}</span></dt>
            <dd className="mt-2 text-xs leading-relaxed text-stone">{financeModuleStatuses[status].description}</dd>
          </div>
        ))}
      </dl>

      <div className="mt-6 space-y-6">
        {financeModuleGroups.map((group, index) => (
          <section key={group.id} aria-labelledby={`finance-group-${group.id}`} className="border-t border-surface-03 pt-5 first:border-t-0 first:pt-0">
            <div className="mb-4 flex items-start gap-3">
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-gold/20 bg-gold/10 text-xs font-black text-gold" aria-hidden="true">{String(index + 1).padStart(2, "0")}</span>
              <div className="min-w-0">
                <h4 id={`finance-group-${group.id}`} className="text-base font-black text-cream">{group.title}</h4>
                <p className="mt-1 text-xs leading-relaxed text-stone">Área agrupada por responsabilidade financeira no ERP.</p>
              </div>
            </div>
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {group.modules.map(({ title, description, status, icon: Icon }) => (
                <article key={title} className="min-w-0 rounded-2xl border border-surface-03 bg-surface-01/70 p-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-gold/20 bg-gold/10 text-gold">
                      <Icon size={18} aria-hidden="true" />
                    </div>
                    <span className={`rounded-full border px-2 py-1 text-[10px] font-black uppercase tracking-wide ${financeModuleStatuses[status].className}`}>{status}</span>
                  </div>
                  <h5 className="mt-4 break-words text-sm font-black leading-snug text-cream">{title}</h5>
                  <p className="mt-2 text-xs leading-relaxed text-stone">{description}</p>
                </article>
              ))}
            </div>
          </section>
        ))}
      </div>
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
