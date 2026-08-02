import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ArrowLeft,
  CalendarClock,
  Check,
  Copy,
  CreditCard,
  Globe2,
  Headphones,
  Loader2,
  Plus,
  RefreshCw,
  Save,
  Shield,
  Trash2,
  UserRound,
} from "lucide-react";
import { Link, useParams } from "react-router-dom";
import {
  AuditLogTimeline,
  CompanySummaryCard,
  ConfirmationDialog,
  DomainStatusBadge,
  LicenseStatusBadge,
  UsageProgress,
} from "@/components/platform/PlatformComponents";
import PlatformSupportAccessDialog from "@/components/platform/PlatformSupportAccessDialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/hooks/use-toast";
import {
  platformAuditApi,
  platformBillingApi,
  platformDomainsApi,
  platformPlansApi,
  platformTenantsApi,
  type ApiPlatformAuditLog,
  type ApiPlatformBillingHistory,
  type ApiPlatformInvoice,
  type ApiPlatformInvitation,
  type ApiPlatformLicense,
  type ApiPlatformModule,
  type ApiPlatformPlan,
  type ApiPlatformTenantDetail,
  type ApiPlatformTenantDomain,
  type ApiPlatformTenantProfile,
  type ApiPlatformTenantNote,
  type ApiPlatformTenantMembershipRole,
  type ApiPlatformTenantMembershipStatus,
  type ApiPlatformTenantSecurity,
  type ApiPlatformTenantUser,
  type ApiPlatformUsageMetric,
} from "@/lib/api";
import { isPlatformInvoicePaymentAvailable } from "@/lib/platformMaster";
import {
  PLATFORM_LICENSE_ACTION_META,
  platformLicenseActionNeedsDays,
  platformLicenseActionsForStatus,
  type PlatformLicenseAction,
} from "@/lib/platformLicense";
import {
  buildPlatformTenantModulePayload,
  platformTenantModuleDraft,
  type PlatformTenantModuleDraft,
  type PlatformTenantModuleOrigin,
} from "@/lib/platformTenantModules";

const TABS = [
  "Visao geral",
  "Cadastro",
  "Licenca",
  "Modulos",
  "Integracoes",
  "Usuarios",
  "Dominios",
  "Cobrancas",
  "Consumo",
  "Seguranca",
  "Auditoria",
  "Notas",
] as const;
type Tab = typeof TABS[number];

function formatDateTime(value?: string | null) {
  return value ? new Date(value).toLocaleString("pt-BR") : "Nao definido";
}

export default function PlatformTenantDetail() {
  const { tenantId = "" } = useParams();
  const { toast } = useToast();
  const [tab, setTab] = useState<Tab>(() => {
    const requestedTab = new URLSearchParams(window.location.search).get("tab");
    return TABS.find((item) => item === requestedTab) ?? "Visao geral";
  });
  const [tenant, setTenant] = useState<ApiPlatformTenantDetail | null>(null);
  const [license, setLicense] = useState<ApiPlatformLicense | null>(null);
  const [plans, setPlans] = useState<ApiPlatformPlan[]>([]);
  const [users, setUsers] = useState<ApiPlatformTenantUser[]>([]);
  const [invitations, setInvitations] = useState<ApiPlatformInvitation[]>([]);
  const [invoices, setInvoices] = useState<ApiPlatformInvoice[]>([]);
  const [audit, setAudit] = useState<ApiPlatformAuditLog[]>([]);
  const [usage, setUsage] = useState<ApiPlatformUsageMetric[]>([]);
  const [security, setSecurity] = useState<ApiPlatformTenantSecurity | null>(null);
  const [notes, setNotes] = useState<ApiPlatformTenantNote[]>([]);
  const [loading, setLoading] = useState(true);
  const [tabLoading, setTabLoading] = useState(false);
  const [error, setError] = useState("");
  const [reason, setReason] = useState("");
  const [confirmAction, setConfirmAction] = useState<"suspend" | "reactivate" | "archive" | null>(null);
  const [supportOpen, setSupportOpen] = useState(false);

  const load = useCallback(async () => {
    if (!tenantId) return;
    setLoading(true);
    setError("");
    try {
      setTenant(await platformTenantsApi.get(tenantId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nao foi possivel carregar a empresa.");
    } finally {
      setLoading(false);
    }
  }, [tenantId]);

  useEffect(() => { void load(); }, [load]);

  useEffect(() => {
    if (!tenantId || !tenant) return;
    let cancelled = false;
    const fetchTab = async () => {
      setTabLoading(true);
      try {
        if (tab === "Licenca") {
          const [licenseData, planData] = await Promise.all([
            platformTenantsApi.license(tenantId),
            platformPlansApi.list(),
          ]);
          if (!cancelled) {
            setLicense(licenseData);
            setPlans(planData);
          }
        } else if (tab === "Usuarios") {
          const [userData, invitationData] = await Promise.all([
            platformTenantsApi.users(tenantId),
            platformTenantsApi.invitations(tenantId),
          ]);
          if (!cancelled) {
            setUsers(userData);
            setInvitations(invitationData);
          }
        } else if (tab === "Cobrancas") {
          const data = await platformTenantsApi.invoices(tenantId);
          if (!cancelled) setInvoices(data);
        } else if (tab === "Auditoria") {
          const data = await platformAuditApi.list({ tenant_id: tenantId, page_size: 50 });
          if (!cancelled) setAudit(data.items);
        } else if (tab === "Consumo") {
          const data = await platformTenantsApi.usage(tenantId);
          if (!cancelled) setUsage(data);
        } else if (tab === "Seguranca") {
          const data = await platformTenantsApi.security(tenantId);
          if (!cancelled) setSecurity(data);
        } else if (tab === "Notas") {
          const data = await platformTenantsApi.notes(tenantId);
          if (!cancelled) setNotes(data);
        }
      } catch (err) {
        if (!cancelled) {
          toast({ variant: "destructive", title: "Nao foi possivel carregar a secao", description: err instanceof Error ? err.message : "Tente novamente." });
        }
      } finally {
        if (!cancelled) setTabLoading(false);
      }
    };
    void fetchTab();
    return () => { cancelled = true; };
  }, [tab, tenant, tenantId, toast]);

  async function tenantAction() {
    if (!confirmAction || !tenant) return;
    try {
      await platformTenantsApi.action(tenant.id, confirmAction, reason.trim());
      toast({ title: "Empresa atualizada", description: "A acao foi registrada na auditoria." });
      setConfirmAction(null);
      setReason("");
      await load();
    } catch (err) {
      toast({ variant: "destructive", title: "Acao nao concluida", description: err instanceof Error ? err.message : "Tente novamente." });
    }
  }

  if (loading) return <div className="flex min-h-72 items-center justify-center gap-2 text-stone"><Loader2 className="animate-spin text-gold" /> Carregando empresa...</div>;
  if (error || !tenant) return <div className="rounded-2xl border border-red-500/30 bg-red-500/10 p-6 text-red-200">{error || "Empresa nao encontrada."}<Button variant="outline" className="ml-3 gap-2" onClick={() => void load()}><RefreshCw size={14} /> Repetir</Button></div>;

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex min-w-0 items-center gap-3">
          <Button variant="outline" size="icon" asChild><Link to="/painel/empresas" aria-label="Voltar para empresas"><ArrowLeft size={16} /></Link></Button>
          <div className="min-w-0"><h2 className="truncate text-xl font-black text-cream">{tenant.name}</h2><p className="truncate text-xs text-stone">{tenant.id}</p></div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => setSupportOpen(true)} className="gap-2"><Headphones size={15} /> Acessar como suporte</Button>
          {tenant.status === "suspended" ? (
            <Button onClick={() => setConfirmAction("reactivate")} className="bg-green-600 text-white hover:bg-green-500">Reativar</Button>
          ) : (
            <Button variant="outline" onClick={() => setConfirmAction("suspend")}>Suspender</Button>
          )}
          {!tenant.is_legacy && <Button variant="destructive" onClick={() => setConfirmAction("archive")}>Arquivar</Button>}
        </div>
      </div>

      <div className="overflow-x-auto rounded-xl border border-surface-03 bg-surface-02 p-1">
        <div className="flex min-w-max gap-1">
          {TABS.map((item) => (
            <button key={item} type="button" onClick={() => setTab(item)} className={`rounded-lg px-3 py-2 text-xs font-bold transition ${tab === item ? "bg-gold text-surface-00" : "text-stone hover:bg-surface-03 hover:text-cream"}`}>{item}</button>
          ))}
        </div>
      </div>

      {tabLoading && <div className="flex items-center justify-center gap-2 py-12 text-sm text-stone"><Loader2 size={16} className="animate-spin text-gold" /> Atualizando secao...</div>}
      {!tabLoading && tab === "Visao geral" && <Overview tenant={tenant} />}
      {!tabLoading && tab === "Cadastro" && <Registration tenant={tenant} onUpdated={setTenant} />}
      {!tabLoading && tab === "Licenca" && <License tenant={tenant} plans={plans} license={license ?? tenant.license ?? null} onChanged={setLicense} onTenantChanged={setTenant} />}
      {!tabLoading && tab === "Modulos" && <Modules tenantId={tenant.id} modules={tenant.modules ?? []} onChanged={(modules) => setTenant({ ...tenant, modules })} />}
      {!tabLoading && tab === "Integracoes" && <Integrations modules={tenant.modules ?? []} />}
      {!tabLoading && tab === "Usuarios" && (
        <Users
          tenantId={tenant.id}
          items={users}
          invitations={invitations}
          onReload={async () => {
            const [userData, invitationData] = await Promise.all([
              platformTenantsApi.users(tenant.id),
              platformTenantsApi.invitations(tenant.id),
            ]);
            setUsers(userData);
            setInvitations(invitationData);
          }}
        />
      )}
      {!tabLoading && tab === "Dominios" && <Domains tenantId={tenant.id} items={tenant.domains ?? []} onChanged={(domains) => setTenant({ ...tenant, domains })} />}
      {!tabLoading && tab === "Cobrancas" && <Billing tenantId={tenant.id} planId={tenant.plan?.id ?? null} items={invoices} onChanged={setInvoices} />}
      {!tabLoading && tab === "Consumo" && <Usage items={usage} tenant={tenant} />}
      {!tabLoading && tab === "Seguranca" && <Security data={security} />}
      {!tabLoading && tab === "Auditoria" && <AuditLogTimeline items={audit} />}
      {!tabLoading && tab === "Notas" && <Notes tenantId={tenant.id} items={notes} onChanged={setNotes} />}

      {confirmAction && (
        <ConfirmationDialog
          open
          onOpenChange={(open) => {
            if (!open) { setConfirmAction(null); setReason(""); }
          }}
          title={confirmAction === "suspend" ? "Suspender empresa" : confirmAction === "reactivate" ? "Reativar empresa" : "Arquivar empresa"}
          description="A acao altera o acesso da empresa e gera um evento de auditoria."
          confirmLabel="Confirmar"
          destructive={confirmAction !== "reactivate"}
          reason={reason}
          reasonRequired
          onReasonChange={setReason}
          onConfirm={() => void tenantAction()}
        />
      )}
      <PlatformSupportAccessDialog
        open={supportOpen}
        onOpenChange={setSupportOpen}
        tenant={tenant}
        users={users}
      />
    </div>
  );
}

function Overview({ tenant }: { tenant: ApiPlatformTenantDetail }) {
  return (
    <div className="grid gap-5 xl:grid-cols-[22rem_1fr]">
      <CompanySummaryCard tenant={tenant} />
      <div className="grid gap-4 sm:grid-cols-2">
        <InfoCard title="Licenca" icon={<CalendarClock size={18} />}>
          {tenant.license ? <><LicenseStatusBadge status={tenant.license.status} /><p className="mt-3 text-sm text-stone">Expira em {tenant.license.expires_at ? new Date(tenant.license.expires_at).toLocaleDateString("pt-BR") : "data nao definida"}</p></> : <p className="text-sm text-stone">Nao configurada.</p>}
        </InfoCard>
        <InfoCard title="Dominio" icon={<Globe2 size={18} />}>
          {tenant.primary_domain ? <><DomainStatusBadge status={tenant.primary_domain.status} /><p className="mt-3 truncate text-sm text-cream">{tenant.primary_domain.hostname}</p></> : <p className="text-sm text-stone">Nenhum dominio principal ativo.</p>}
        </InfoCard>
        <InfoCard title="Modulos" icon={<Check size={18} />}><p className="text-2xl font-black text-cream">{tenant.modules?.filter((item) => item.entitlement?.enabled).length ?? 0}</p><p className="text-xs text-stone">habilitados</p></InfoCard>
        <InfoCard title="Usuarios" icon={<UserRound size={18} />}><p className="text-2xl font-black text-cream">{tenant.user_count ?? 0}</p><p className="text-xs text-stone">memberships ativas ou convidadas</p></InfoCard>
      </div>
    </div>
  );
}

function InfoCard({ title, icon, children }: { title: string; icon: React.ReactNode; children: React.ReactNode }) {
  return <div className="rounded-2xl border border-surface-03 bg-surface-02 p-5"><div className="mb-4 flex items-center gap-2 text-gold">{icon}<h3 className="font-black text-cream">{title}</h3></div>{children}</div>;
}

function Registration({ tenant, onUpdated }: { tenant: ApiPlatformTenantDetail; onUpdated: (tenant: ApiPlatformTenantDetail) => void }) {
  const { toast } = useToast();
  const [name, setName] = useState(tenant.name);
  const [legalName, setLegalName] = useState(tenant.legal_name ?? "");
  const [timezone, setTimezone] = useState(tenant.timezone);
  const [locale, setLocale] = useState(tenant.locale);
  const [profile, setProfile] = useState<ApiPlatformTenantProfile>(tenant.profile ?? {});
  const [saving, setSaving] = useState(false);

  async function save() {
    setSaving(true);
    try {
      const updated = await platformTenantsApi.update(tenant.id, {
        name: name.trim(),
        legal_name: legalName.trim() || null,
        timezone,
        locale,
        profile,
      });
      onUpdated(updated);
      toast({ title: "Cadastro atualizado" });
    } catch (err) {
      toast({ variant: "destructive", title: "Nao foi possivel salvar", description: err instanceof Error ? err.message : "Tente novamente." });
    } finally { setSaving(false); }
  }

  const fields: Array<[keyof ApiPlatformTenantProfile, string]> = [
    ["trade_name", "Nome fantasia"], ["tax_id", "CPF ou CNPJ"], ["email", "E-mail"],
    ["state_registration", "Inscricao estadual"], ["municipal_registration", "Inscricao municipal"],
    ["segment", "Segmento"], ["website", "Site"], ["whatsapp", "WhatsApp"],
    ["billing_email", "E-mail de cobranca"], ["internal_code", "Codigo interno"], ["logo_url", "URL do logo"],
    ["legal_representative_name", "Responsavel legal"], ["legal_representative_document", "Documento do responsavel"],
    ["legal_representative_email", "E-mail do responsavel"], ["legal_representative_phone", "Telefone do responsavel"],
    ["phone", "Telefone"], ["postal_code", "CEP"], ["address_line", "Logradouro"],
    ["address_number", "Numero"], ["address_extra", "Complemento"], ["neighborhood", "Bairro"],
    ["city", "Cidade"], ["state", "Estado"],
  ];
  return (
    <section className="space-y-5 rounded-2xl border border-surface-03 bg-surface-02 p-5">
      <div className="grid gap-4 md:grid-cols-2">
        <FormField label="Nome interno" value={name} onChange={setName} />
        <FormField label="Razao social" value={legalName} onChange={setLegalName} />
        <FormField label="Fuso horario" value={timezone} onChange={setTimezone} />
        <FormField label="Idioma" value={locale} onChange={setLocale} />
        {fields.map(([key, label]) => <FormField key={key} label={label} value={String(profile[key] ?? "")} onChange={(value) => setProfile((current) => ({ ...current, [key]: value || null }))} />)}
        <div><p className="mb-2 text-xs font-bold text-stone">Tenant ID imutavel</p><Input readOnly value={tenant.id} className="border-surface-03 bg-surface-01 text-stone" /></div>
        <div><p className="mb-2 text-xs font-bold text-stone">Slug</p><Input readOnly value={tenant.slug} className="border-surface-03 bg-surface-01 text-stone" /></div>
      </div>
      <Button disabled={saving || !name.trim()} onClick={() => void save()} className="gap-2 bg-gold text-surface-00 hover:bg-gold/90">{saving ? <Loader2 size={15} className="animate-spin" /> : <Save size={15} />} Salvar cadastro</Button>
    </section>
  );
}

function FormField({ label, value, onChange, type = "text" }: { label: string; value: string; onChange: (value: string) => void; type?: string }) {
  return <label><span className="mb-2 block text-xs font-bold text-stone">{label}</span><Input type={type} value={value} onChange={(event) => onChange(event.target.value)} className="border-surface-03 bg-surface-01 text-cream" /></label>;
}

function License({
  tenant,
  plans,
  license,
  onChanged,
  onTenantChanged,
}: {
  tenant: ApiPlatformTenantDetail;
  plans: ApiPlatformPlan[];
  license: ApiPlatformLicense | null;
  onChanged: (license: ApiPlatformLicense) => void;
  onTenantChanged: (tenant: ApiPlatformTenantDetail) => void;
}) {
  const { toast } = useToast();
  const [action, setAction] = useState<PlatformLicenseAction | null>(null);
  const [reason, setReason] = useState("");
  const [days, setDays] = useState("30");
  const [saving, setSaving] = useState(false);
  const [planOpen, setPlanOpen] = useState(false);
  const [planId, setPlanId] = useState(tenant.plan?.id ?? "");
  const [planReason, setPlanReason] = useState("");

  const needsDays = action && license
    ? platformLicenseActionNeedsDays(action, license)
    : false;

  function openAction(nextAction: PlatformLicenseAction) {
    setAction(nextAction);
    setReason("");
    setDays(nextAction === "convert" ? "" : "30");
  }

  async function execute() {
    if (!action || !license || reason.trim().length < 3 || saving) return;
    const parsedDays = days.trim() ? Number(days) : undefined;
    if (needsDays && (!parsedDays || parsedDays < 1)) return;
    if (parsedDays !== undefined && (!Number.isFinite(parsedDays) || parsedDays < 1)) return;
    setSaving(true);
    try {
      const updated = await platformTenantsApi.licenseAction(tenant.id, action, {
        ...(parsedDays !== undefined ? { days: parsedDays } : {}),
        reason: reason.trim(),
      });
      onChanged(updated);
      setAction(null);
      setReason("");
      toast({ title: "Licenca atualizada", description: "A transicao foi registrada na auditoria." });
    } catch (err) {
      toast({ variant: "destructive", title: "Acao nao concluida", description: err instanceof Error ? err.message : "Tente novamente." });
    } finally {
      setSaving(false);
    }
  }
  async function changePlan() {
    if (!planId || !planReason.trim()) return;
    try {
      const updated = await platformTenantsApi.changePlan(tenant.id, planId, planReason.trim());
      onTenantChanged(updated);
      setPlanOpen(false);
      setPlanReason("");
      toast({ title: "Plano alterado" });
    } catch (err) {
      toast({ variant: "destructive", title: "Nao foi possivel alterar o plano", description: err instanceof Error ? err.message : "Tente novamente." });
    }
  }
  if (!license) return <UnavailableSection title="Licenca nao configurada" description="O backend nao retornou uma licenca para esta empresa." />;
  const availableActions = platformLicenseActionsForStatus(license.status);
  return (
    <div className="space-y-5 rounded-2xl border border-surface-03 bg-surface-02 p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <LicenseStatusBadge status={license.status} />
          <p className="mt-3 text-sm text-stone">
            Inicio: {license.starts_at ? new Date(license.starts_at).toLocaleDateString("pt-BR") : "-"}
            {" · "}Termino: {(license.ends_at || license.expires_at) ? new Date(license.ends_at || license.expires_at || "").toLocaleDateString("pt-BR") : "-"}
          </p>
          {license.grace_period_ends_at && <p className="mt-1 text-xs text-yellow-200">Carencia ate {new Date(license.grace_period_ends_at).toLocaleDateString("pt-BR")}</p>}
          {license.cancellation_reason && <p className="mt-1 text-xs text-red-200">Cancelamento: {license.cancellation_reason}</p>}
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => setPlanOpen(true)}>Alterar plano</Button>
          {availableActions.map((licenseAction) => {
            const meta = PLATFORM_LICENSE_ACTION_META[licenseAction];
            return (
              <Button
                key={licenseAction}
                variant={meta.destructive ? "destructive" : licenseAction === "renew" ? "default" : "outline"}
                onClick={() => openAction(licenseAction)}
                className={licenseAction === "renew" ? "bg-gold text-surface-00 hover:bg-gold/90" : undefined}
              >
                {meta.label}
              </Button>
            );
          })}
        </div>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <UsageProgress label="Dias utilizados" used={license.days_used ?? 0} limit={license.days_remaining != null ? (license.days_used ?? 0) + license.days_remaining : null} />
        <div className="rounded-xl border border-surface-03 bg-surface-01 p-4 text-sm text-stone">Renovacao automatica: <strong className="text-cream">{license.auto_renew ? "Ativa" : "Desativada"}</strong></div>
        <div className="rounded-xl border border-surface-03 bg-surface-01 p-4 text-sm text-stone">Dias restantes: <strong className="text-cream">{license.days_remaining ?? "Sem limite"}</strong></div>
        <div className="rounded-xl border border-surface-03 bg-surface-01 p-4 text-sm text-stone">Proximo vencimento: <strong className="text-cream">{license.next_due_at ? new Date(license.next_due_at).toLocaleDateString("pt-BR") : "Nao definido"}</strong></div>
      </div>
      {action && (
        <ConfirmationDialog
          open
          onOpenChange={(open) => { if (!open) setAction(null); }}
          title={`${PLATFORM_LICENSE_ACTION_META[action].label} licenca`}
          description="A alteracao passa a valer imediatamente e sera auditada pelo backend."
          confirmLabel={saving ? "Salvando..." : "Confirmar"}
          confirmDisabled={saving || reason.trim().length < 3 || !!needsDays && (!Number(days) || Number(days) < 1)}
          preventCloseOnConfirm
          destructive={PLATFORM_LICENSE_ACTION_META[action].destructive}
          reason={reason}
          reasonRequired
          onReasonChange={setReason}
          onConfirm={() => void execute()}
        >
          {(needsDays || action === "convert") && (
            <label className="space-y-2 text-sm">
              <span className="font-bold text-cream">Dias{action === "convert" ? " adicionais (opcional)" : " *"}</span>
              <Input type="number" min={1} max={3650} value={days} onChange={(event) => setDays(event.target.value)} className="border-surface-03 bg-surface-01 text-cream" />
            </label>
          )}
        </ConfirmationDialog>
      )}
      {planOpen && <ConfirmationDialog open onOpenChange={setPlanOpen} title="Alterar plano da empresa" description="Os modulos do plano serao reconciliados pelo backend sem apagar historico." confirmLabel="Alterar plano" reason={planReason} reasonRequired onReasonChange={setPlanReason} onConfirm={() => void changePlan()}>
        <label className="space-y-2 text-sm"><span className="font-bold text-cream">Novo plano</span><select value={planId} onChange={(event) => setPlanId(event.target.value)} className="h-10 w-full rounded-md border border-surface-03 bg-surface-01 px-3 text-cream"><option value="">Selecione</option>{plans.filter((plan) => plan.status === "active").map((plan) => <option key={plan.id} value={plan.id}>{plan.name}</option>)}</select></label>
      </ConfirmationDialog>}
    </div>
  );
}

function moduleDrafts(modules: ApiPlatformModule[]): Record<string, PlatformTenantModuleDraft> {
  return Object.fromEntries(modules.map((module) => [module.id, platformTenantModuleDraft(module)]));
}

function Modules({ tenantId, modules, onChanged }: { tenantId: string; modules: ApiPlatformModule[]; onChanged: (modules: ApiPlatformModule[]) => void }) {
  const { toast } = useToast();
  const [drafts, setDrafts] = useState<Record<string, PlatformTenantModuleDraft>>(() => moduleDrafts(modules));
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setDrafts(moduleDrafts(modules));
  }, [modules]);

  function updateDraft(moduleId: string, patch: Partial<PlatformTenantModuleDraft>) {
    setDrafts((current) => ({
      ...current,
      [moduleId]: { ...current[moduleId], ...patch },
    }));
  }

  async function save() {
    if (reason.trim().length < 3 || saving) return;
    setSaving(true);
    try {
      const payload = buildPlatformTenantModulePayload(modules, drafts, reason.trim());
      const updated = await platformTenantsApi.updateModules(tenantId, payload, reason.trim());
      onChanged(updated);
      setReason("");
      toast({ title: "Modulos atualizados", description: "Metadados e configuracoes existentes foram preservados." });
    } catch (err) {
      toast({ variant: "destructive", title: "Nao foi possivel salvar", description: err instanceof Error ? err.message : "Tente novamente." });
    } finally {
      setSaving(false);
    }
  }

  if (!modules.length) return <UnavailableSection title="Nenhum modulo cadastrado" description="Cadastre modulos no catalogo da plataforma." />;

  return (
    <div className="space-y-4">
      <div className="grid gap-4 xl:grid-cols-2">
        {modules.map((module) => {
          const draft = drafts[module.id];
          if (!draft) return null;
          const integration = module.module_group === "integrations";
          return (
            <article key={module.id} className="space-y-4 rounded-2xl border border-surface-03 bg-surface-02 p-4">
              <div className="flex items-start gap-3">
                <input
                  type="checkbox"
                  checked={draft.enabled}
                  onChange={(event) => updateDraft(module.id, { enabled: event.target.checked })}
                  className="mt-1"
                />
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="font-black text-cream">{module.name}</h3>
                    <span className="rounded-full border border-surface-03 px-2 py-1 text-[10px] text-stone">{module.module_group}</span>
                  </div>
                  <p className="mt-1 text-xs text-stone">{module.description || module.key}</p>
                  {module.entitlement?.block_reason && <p className="mt-2 text-xs text-red-200">{module.entitlement.block_reason}</p>}
                </div>
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                <label className="space-y-2 text-xs font-bold text-stone">
                  <span>Origem</span>
                  <select value={draft.origin} onChange={(event) => updateDraft(module.id, { origin: event.target.value as PlatformTenantModuleOrigin })} className="h-10 w-full rounded-md border border-surface-03 bg-surface-01 px-3 text-sm text-cream">
                    <option value="plan">Plano</option>
                    <option value="addon">Adicional</option>
                    <option value="courtesy">Cortesia</option>
                    <option value="trial">Trial</option>
                  </select>
                </label>
                <ModuleInput label="Limite" type="number" min="0" value={draft.limit_value} onChange={(value) => updateDraft(module.id, { limit_value: value })} placeholder="Sem limite" />
                <ModuleInput label="Inicio" type="datetime-local" value={draft.starts_at} onChange={(value) => updateDraft(module.id, { starts_at: value })} />
                <ModuleInput label="Termino" type="datetime-local" value={draft.ends_at} onChange={(value) => updateDraft(module.id, { ends_at: value })} />
                <ModuleInput label="Valor adicional" type="number" min="0" step="0.01" value={draft.additional_price} onChange={(value) => updateDraft(module.id, { additional_price: value })} />
              </div>

              {integration ? (
                <p className="rounded-xl border border-blue-500/20 bg-blue-500/10 p-3 text-xs text-blue-100">
                  A configuracao interna desta integracao e preservada, mas permanece oculta para evitar exposicao de credenciais.
                </p>
              ) : (
                <label className="block space-y-2 text-xs font-bold text-stone">
                  <span>Configuracao do tenant (JSON)</span>
                  <Textarea value={draft.config_text} onChange={(event) => updateDraft(module.id, { config_text: event.target.value })} spellCheck={false} className="min-h-28 border-surface-03 bg-surface-01 font-mono text-xs text-cream" />
                </label>
              )}
            </article>
          );
        })}
      </div>
      <div className="flex flex-col gap-3 rounded-xl border border-surface-03 bg-surface-02 p-4 sm:flex-row">
        <Input value={reason} onChange={(event) => setReason(event.target.value)} placeholder="Motivo da alteracao (obrigatorio)" className="border-surface-03 bg-surface-01 text-cream" />
        <Button disabled={saving || reason.trim().length < 3} onClick={() => void save()} className="gap-2 bg-gold text-surface-00 hover:bg-gold/90">
          {saving ? <Loader2 size={15} className="animate-spin" /> : <Save size={15} />} Salvar modulos
        </Button>
      </div>
    </div>
  );
}

function ModuleInput({ label, value, onChange, ...inputProps }: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: string;
  min?: string;
  step?: string;
  placeholder?: string;
}) {
  return (
    <label className="space-y-2 text-xs font-bold text-stone">
      <span>{label}</span>
      <Input {...inputProps} value={value} onChange={(event) => onChange(event.target.value)} className="border-surface-03 bg-surface-01 text-cream" />
    </label>
  );
}

function Integrations({ modules }: { modules: ApiPlatformModule[] }) {
  const integrations = modules.filter((module) => module.module_group === "integrations");

  if (!integrations.length) {
    return <UnavailableSection title="Nenhuma integracao cadastrada" description="Cadastre integracoes no catalogo de modulos da plataforma." />;
  }

  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-blue-500/20 bg-blue-500/10 p-4 text-sm text-blue-100">
        Credenciais e configuracoes internas permanecem ocultas. Habilitacao, vigencia e limites podem ser administrados na aba Modulos.
      </div>
      <div className="grid gap-4 xl:grid-cols-2">
        {integrations.map((module) => {
          const entitlement = module.entitlement;
          return (
            <article key={module.id} className="rounded-2xl border border-surface-03 bg-surface-02 p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <h3 className="font-black text-cream">{module.name}</h3>
                  <p className="mt-1 text-xs text-stone">{module.description || module.key}</p>
                </div>
                <span className={`rounded-full border px-2 py-1 text-xs font-bold ${
                  entitlement?.enabled
                    ? "border-green-500/30 bg-green-500/10 text-green-200"
                    : "border-surface-03 text-stone"
                }`}>
                  {entitlement?.enabled ? "Habilitada" : "Desabilitada"}
                </span>
              </div>
              <dl className="mt-4 grid gap-3 text-xs sm:grid-cols-2">
                <IntegrationMeta label="Chave" value={module.key} />
                <IntegrationMeta label="Origem" value={entitlement?.origin || "Nao contratada"} />
                <IntegrationMeta label="Inicio" value={formatDateTime(entitlement?.starts_at)} />
                <IntegrationMeta label="Termino" value={formatDateTime(entitlement?.ends_at)} />
                <IntegrationMeta label="Limite" value={entitlement?.limit_value == null ? "Sem limite" : String(entitlement.limit_value)} />
                <IntegrationMeta
                  label="Valor adicional"
                  value={Number(entitlement?.additional_price || 0).toLocaleString("pt-BR", { style: "currency", currency: "BRL" })}
                />
              </dl>
              {entitlement?.block_reason && <p className="mt-4 rounded-lg bg-red-500/10 p-3 text-xs text-red-200">{entitlement.block_reason}</p>}
            </article>
          );
        })}
      </div>
    </div>
  );
}

function IntegrationMeta({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="font-bold text-stone">{label}</dt>
      <dd className="mt-1 break-words text-cream">{value}</dd>
    </div>
  );
}

type UserAction = "role" | "status" | "block" | "reactivate" | "reset-password" | "revoke-sessions" | "transfer-owner";

const MEMBERSHIP_ROLES: Array<Exclude<ApiPlatformTenantMembershipRole, "owner">> = [
  "admin",
  "manager",
  "operator",
  "viewer",
];

const MEMBERSHIP_STATUSES: ApiPlatformTenantMembershipStatus[] = [
  "active",
  "invited",
  "suspended",
  "revoked",
];

function Users({
  tenantId,
  items,
  invitations,
  onReload,
}: {
  tenantId: string;
  items: ApiPlatformTenantUser[];
  invitations: ApiPlatformInvitation[];
  onReload: () => Promise<void>;
}) {
  const { toast } = useToast();
  const [createOpen, setCreateOpen] = useState(false);
  const [inviteOpen, setInviteOpen] = useState(false);
  const [createReason, setCreateReason] = useState("");
  const [createData, setCreateData] = useState({
    name: "",
    email: "",
    phone: "",
    password: "",
    force_password_change: true,
    membership_role: "viewer" as Exclude<ApiPlatformTenantMembershipRole, "owner">,
  });
  const [inviteReason, setInviteReason] = useState("");
  const [inviteData, setInviteData] = useState({
    name: "",
    email: "",
    phone: "",
    job_title: "",
    membership_role: "viewer" as Exclude<ApiPlatformTenantMembershipRole, "owner">,
    expires_in_hours: 72,
  });
  const [issuedToken, setIssuedToken] = useState("");
  const [resendTarget, setResendTarget] = useState<ApiPlatformInvitation | null>(null);
  const [resendReason, setResendReason] = useState("");
  const [resendHours, setResendHours] = useState(72);
  const [target, setTarget] = useState<ApiPlatformTenantUser | null>(null);
  const [action, setAction] = useState<UserAction | null>(null);
  const [reason, setReason] = useState("");
  const [role, setRole] = useState<Exclude<ApiPlatformTenantMembershipRole, "owner">>("viewer");
  const [status, setStatus] = useState<ApiPlatformTenantMembershipStatus>("active");
  const [password, setPassword] = useState("");
  const [forcePasswordChange, setForcePasswordChange] = useState(true);
  const [saving, setSaving] = useState(false);

  function closeAction() {
    setTarget(null);
    setAction(null);
    setReason("");
    setPassword("");
    setForcePasswordChange(true);
  }

  function openAction(user: ApiPlatformTenantUser, nextAction: UserAction) {
    setTarget(user);
    setAction(nextAction);
    setReason("");
    setRole(user.membership.role === "owner" ? "admin" : user.membership.role);
    setStatus(user.membership.status);
    setPassword("");
    setForcePasswordChange(true);
  }

  async function createUser() {
    if (
      createData.name.trim().length < 2
      || !createData.email.trim()
      || createData.password.length < 8
      || createReason.trim().length < 3
    ) return;
    setSaving(true);
    try {
      await platformTenantsApi.createUser(tenantId, {
        ...createData,
        name: createData.name.trim(),
        email: createData.email.trim(),
        phone: createData.phone.trim() || null,
        reason: createReason.trim(),
      });
      await onReload();
      setCreateOpen(false);
      setCreateReason("");
      setCreateData({
        name: "",
        email: "",
        phone: "",
        password: "",
        force_password_change: true,
        membership_role: "viewer",
      });
      toast({ title: "Usuario criado", description: "O acesso foi vinculado a esta empresa." });
    } catch (err) {
      toast({ variant: "destructive", title: "Nao foi possivel criar o usuario", description: err instanceof Error ? err.message : "Tente novamente." });
    } finally {
      setSaving(false);
    }
  }

  async function inviteUser() {
    if (
      inviteData.name.trim().length < 2
      || !inviteData.email.trim()
      || inviteReason.trim().length < 3
    ) return;
    setSaving(true);
    try {
      const result = await platformTenantsApi.inviteUser(tenantId, {
        ...inviteData,
        name: inviteData.name.trim(),
        email: inviteData.email.trim(),
        phone: inviteData.phone.trim() || null,
        job_title: inviteData.job_title.trim() || null,
        reason: inviteReason.trim(),
      });
      setIssuedToken(result.invitation_token);
      await onReload();
      setInviteOpen(false);
      setInviteReason("");
      setInviteData({
        name: "",
        email: "",
        phone: "",
        job_title: "",
        membership_role: "viewer",
        expires_in_hours: 72,
      });
      toast({ title: "Convite emitido", description: "Copie o link agora: o token bruto nao sera exibido novamente." });
    } catch (err) {
      toast({ variant: "destructive", title: "Nao foi possivel convidar", description: err instanceof Error ? err.message : "Tente novamente." });
    } finally {
      setSaving(false);
    }
  }

  async function resendInvitation() {
    if (!resendTarget || resendReason.trim().length < 3) return;
    setSaving(true);
    try {
      const result = await platformTenantsApi.resendInvitation(tenantId, resendTarget.id, {
        expires_in_hours: resendHours,
        reason: resendReason.trim(),
      });
      setIssuedToken(result.invitation_token);
      setResendTarget(null);
      setResendReason("");
      await onReload();
      toast({ title: "Convite reenviado", description: "O token anterior foi invalidado. Copie o novo link agora." });
    } catch (err) {
      toast({ variant: "destructive", title: "Nao foi possivel reenviar", description: err instanceof Error ? err.message : "Tente novamente." });
    } finally {
      setSaving(false);
    }
  }

  const invitationLink = issuedToken
    ? `${window.location.origin}/painel/convite/${encodeURIComponent(issuedToken)}`
    : "";

  async function copyInvitationLink() {
    try {
      await navigator.clipboard.writeText(invitationLink);
      toast({ title: "Link copiado" });
    } catch {
      toast({ variant: "destructive", title: "Nao foi possivel copiar", description: "Selecione o link e copie manualmente." });
    }
  }

  async function executeAction() {
    if (!target || !action || reason.trim().length < 3) return;
    setSaving(true);
    try {
      if (action === "role") {
        await platformTenantsApi.updateUserRole(tenantId, target.id, {
          membership_role: role,
          reason: reason.trim(),
        });
      } else if (action === "status") {
        await platformTenantsApi.updateUserStatus(tenantId, target.id, {
          status,
          reason: reason.trim(),
        });
      } else if (action === "block" || action === "reactivate") {
        await platformTenantsApi.userAccessAction(tenantId, target.id, action, reason.trim());
      } else if (action === "reset-password") {
        if (password.length < 8) return;
        await platformTenantsApi.resetUserPassword(tenantId, target.id, {
          password,
          force_password_change: forcePasswordChange,
          reason: reason.trim(),
        });
      } else if (action === "revoke-sessions") {
        await platformTenantsApi.revokeUserSessions(tenantId, target.id, reason.trim());
      } else {
        await platformTenantsApi.transferOwnership(tenantId, target.id, reason.trim());
      }
      await onReload();
      closeAction();
      toast({ title: "Usuario atualizado", description: "A alteracao foi registrada na auditoria." });
    } catch (err) {
      toast({ variant: "destructive", title: "Nao foi possivel concluir", description: err instanceof Error ? err.message : "Tente novamente." });
    } finally {
      setSaving(false);
    }
  }

  const actionTitle = action === "role" ? "Alterar funcao"
    : action === "status" ? "Alterar status"
    : action === "block" ? "Bloquear usuario"
    : action === "reactivate" ? "Reativar usuario"
    : action === "reset-password" ? "Redefinir senha"
    : action === "revoke-sessions" ? "Revogar sessoes"
    : "Transferir propriedade";

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button variant="outline" onClick={() => setInviteOpen(true)} className="mr-2 gap-2">
          <Plus size={15} /> Convidar
        </Button>
        <Button onClick={() => setCreateOpen(true)} className="gap-2 bg-gold text-surface-00 hover:bg-gold/90">
          <Plus size={15} /> Novo usuario
        </Button>
      </div>

      {invitationLink && (
        <div className="rounded-xl border border-yellow-500/30 bg-yellow-500/10 p-4">
          <p className="font-bold text-yellow-100">Link temporario do convite</p>
          <p className="mt-1 text-xs text-yellow-100/70">Este token bruto e exibido somente nesta emissao. Compartilhe por um canal seguro.</p>
          <div className="mt-3 flex flex-col gap-2 sm:flex-row">
            <Input readOnly value={invitationLink} className="border-yellow-500/30 bg-surface-01 text-cream" />
            <Button variant="outline" onClick={() => void copyInvitationLink()}>Copiar link</Button>
            <Button variant="ghost" onClick={() => setIssuedToken("")} className="text-stone">Ocultar</Button>
          </div>
        </div>
      )}

      {!items.length ? (
        <UnavailableSection title="Nenhum usuario vinculado" description="Crie o primeiro acesso empresarial pelo botao acima." />
      ) : (
        <div className="grid gap-3 xl:grid-cols-2">
          {items.map((user) => (
            <div key={user.membership.id} className="rounded-xl border border-surface-03 bg-surface-02 p-4">
              <div className="flex items-start gap-3">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-gold/10 text-gold"><UserRound size={18} /></span>
                <div className="min-w-0 flex-1">
                  <p className="truncate font-bold text-cream">{user.name}</p>
                  <p className="truncate text-xs text-stone">{user.email}</p>
                  <div className="mt-3 flex flex-wrap gap-2 text-xs">
                    <span className="rounded-full border border-surface-03 px-2 py-1 text-stone">{user.membership.role}</span>
                    <span className="rounded-full border border-surface-03 px-2 py-1 text-stone">{user.membership.status}</span>
                    {user.force_password_change && <span className="rounded-full border border-yellow-500/30 px-2 py-1 text-yellow-200">troca de senha pendente</span>}
                  </div>
                </div>
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                {user.membership.role !== "owner" && (
                  <Button variant="outline" size="sm" onClick={() => openAction(user, "role")}>Funcao</Button>
                )}
                {user.membership.role !== "owner" && (
                  <Button variant="outline" size="sm" onClick={() => openAction(user, "status")}>Status</Button>
                )}
                {user.membership.role !== "owner" && (
                  user.membership.status === "suspended"
                    ? <Button variant="outline" size="sm" onClick={() => openAction(user, "reactivate")}>Reativar</Button>
                    : <Button variant="destructive" size="sm" onClick={() => openAction(user, "block")}>Bloquear</Button>
                )}
                <Button variant="outline" size="sm" onClick={() => openAction(user, "reset-password")}>Redefinir senha</Button>
                <Button variant="outline" size="sm" onClick={() => openAction(user, "revoke-sessions")}>Revogar sessoes</Button>
                {user.membership.role !== "owner" && user.membership.status === "active" && (
                  <Button variant="outline" size="sm" onClick={() => openAction(user, "transfer-owner")}>Tornar owner</Button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {!!invitations.length && (
        <section className="rounded-2xl border border-surface-03 bg-surface-02 p-4">
          <h3 className="font-black text-cream">Convites</h3>
          <div className="mt-3 space-y-2">
            {invitations.map((invitation) => (
              <div key={invitation.id} className="flex flex-col gap-3 rounded-xl border border-surface-03 bg-surface-01 p-3 sm:flex-row sm:items-center">
                <div className="min-w-0 flex-1">
                  <p className="truncate font-bold text-cream">{invitation.name} · {invitation.email}</p>
                  <p className="mt-1 text-xs text-stone">{invitation.membership_role} · {invitation.status} · expira {new Date(invitation.expires_at).toLocaleString("pt-BR")}</p>
                </div>
                {invitation.status === "pending" && (
                  <Button variant="outline" size="sm" onClick={() => { setResendTarget(invitation); setResendReason(""); }}>Reenviar</Button>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {createOpen && (
        <ConfirmationDialog
          open
          onOpenChange={(open) => {
            setCreateOpen(open);
            if (!open) setCreateReason("");
          }}
          title="Criar usuario empresarial"
          description="O usuario recebera acesso somente a esta empresa. Revise os dados antes de confirmar."
          confirmLabel={saving ? "Criando..." : "Criar usuario"}
          confirmDisabled={saving || createData.name.trim().length < 2 || !createData.email.trim() || createData.password.length < 8}
          preventCloseOnConfirm
          reason={createReason}
          reasonRequired
          onReasonChange={setCreateReason}
          onConfirm={() => void createUser()}
        >
          <div className="grid gap-3 sm:grid-cols-2">
            <FormField label="Nome" value={createData.name} onChange={(name) => setCreateData((current) => ({ ...current, name }))} />
            <FormField label="E-mail" value={createData.email} onChange={(email) => setCreateData((current) => ({ ...current, email }))} />
            <FormField label="Telefone" value={createData.phone} onChange={(phone) => setCreateData((current) => ({ ...current, phone }))} />
            <label>
              <span className="mb-2 block text-xs font-bold text-stone">Funcao</span>
              <select value={createData.membership_role} onChange={(event) => setCreateData((current) => ({ ...current, membership_role: event.target.value as typeof current.membership_role }))} className="h-10 w-full rounded-md border border-surface-03 bg-surface-01 px-3 text-cream">
                {MEMBERSHIP_ROLES.map((item) => <option key={item} value={item}>{item}</option>)}
              </select>
            </label>
            <label className="sm:col-span-2">
              <span className="mb-2 block text-xs font-bold text-stone">Senha temporaria</span>
              <Input type="password" value={createData.password} onChange={(event) => setCreateData((current) => ({ ...current, password: event.target.value }))} minLength={8} maxLength={72} className="border-surface-03 bg-surface-01 text-cream" />
            </label>
            <label className="flex items-center gap-2 text-sm text-cream sm:col-span-2">
              <input type="checkbox" checked={createData.force_password_change} onChange={(event) => setCreateData((current) => ({ ...current, force_password_change: event.target.checked }))} />
              Exigir troca da senha no primeiro acesso
            </label>
          </div>
        </ConfirmationDialog>
      )}

      {inviteOpen && (
        <ConfirmationDialog
          open
          onOpenChange={setInviteOpen}
          title="Convidar usuario"
          description="O token temporario sera mostrado uma unica vez. O convite nao cria acesso ate ser aceito."
          confirmLabel={saving ? "Emitindo..." : "Emitir convite"}
          confirmDisabled={saving || inviteData.name.trim().length < 2 || !inviteData.email.trim()}
          preventCloseOnConfirm
          reason={inviteReason}
          reasonRequired
          onReasonChange={setInviteReason}
          onConfirm={() => void inviteUser()}
        >
          <div className="grid gap-3 sm:grid-cols-2">
            <FormField label="Nome" value={inviteData.name} onChange={(name) => setInviteData((current) => ({ ...current, name }))} />
            <FormField label="E-mail" value={inviteData.email} onChange={(email) => setInviteData((current) => ({ ...current, email }))} />
            <FormField label="Telefone" value={inviteData.phone} onChange={(phone) => setInviteData((current) => ({ ...current, phone }))} />
            <FormField label="Cargo" value={inviteData.job_title} onChange={(job_title) => setInviteData((current) => ({ ...current, job_title }))} />
            <label>
              <span className="mb-2 block text-xs font-bold text-stone">Funcao</span>
              <select value={inviteData.membership_role} onChange={(event) => setInviteData((current) => ({ ...current, membership_role: event.target.value as typeof current.membership_role }))} className="h-10 w-full rounded-md border border-surface-03 bg-surface-01 px-3 text-cream">
                {MEMBERSHIP_ROLES.map((item) => <option key={item} value={item}>{item}</option>)}
              </select>
            </label>
            <label>
              <span className="mb-2 block text-xs font-bold text-stone">Validade em horas</span>
              <Input type="number" min={1} max={720} value={inviteData.expires_in_hours} onChange={(event) => setInviteData((current) => ({ ...current, expires_in_hours: Math.max(1, Number(event.target.value) || 1) }))} className="border-surface-03 bg-surface-01 text-cream" />
            </label>
          </div>
        </ConfirmationDialog>
      )}

      {resendTarget && (
        <ConfirmationDialog
          open
          onOpenChange={(open) => { if (!open) setResendTarget(null); }}
          title="Reenviar convite"
          description={`O token anterior de ${resendTarget.email} sera invalidado e substituido por outro.`}
          confirmLabel={saving ? "Reemitindo..." : "Reemitir convite"}
          confirmDisabled={saving}
          preventCloseOnConfirm
          reason={resendReason}
          reasonRequired
          onReasonChange={setResendReason}
          onConfirm={() => void resendInvitation()}
        >
          <label className="space-y-2 text-sm">
            <span className="font-bold text-cream">Nova validade em horas</span>
            <Input type="number" min={1} max={720} value={resendHours} onChange={(event) => setResendHours(Math.max(1, Number(event.target.value) || 1))} className="border-surface-03 bg-surface-01 text-cream" />
          </label>
        </ConfirmationDialog>
      )}

      {target && action && (
        <ConfirmationDialog
          open
          onOpenChange={(open) => { if (!open) closeAction(); }}
          title={actionTitle}
          description={`A alteracao de ${target.name} entra em vigor imediatamente e sera auditada.`}
          confirmLabel={saving ? "Salvando..." : "Confirmar alteracao"}
          confirmDisabled={saving || action === "reset-password" && password.length < 8}
          preventCloseOnConfirm
          destructive={action === "block" || action === "revoke-sessions" || action === "status" && status !== "active"}
          reason={reason}
          reasonRequired
          onReasonChange={setReason}
          onConfirm={() => void executeAction()}
        >
          {action === "role" && (
            <label className="space-y-2 text-sm">
              <span className="font-bold text-cream">Nova funcao</span>
              <select value={role} onChange={(event) => setRole(event.target.value as typeof role)} className="h-10 w-full rounded-md border border-surface-03 bg-surface-01 px-3 text-cream">
                {MEMBERSHIP_ROLES.map((item) => <option key={item} value={item}>{item}</option>)}
              </select>
            </label>
          )}
          {action === "status" && (
            <label className="space-y-2 text-sm">
              <span className="font-bold text-cream">Novo status</span>
              <select value={status} onChange={(event) => setStatus(event.target.value as ApiPlatformTenantMembershipStatus)} className="h-10 w-full rounded-md border border-surface-03 bg-surface-01 px-3 text-cream">
                {MEMBERSHIP_STATUSES.map((item) => <option key={item} value={item}>{item}</option>)}
              </select>
            </label>
          )}
          {action === "reset-password" && (
            <div className="space-y-3">
              <label className="space-y-2 text-sm">
                <span className="font-bold text-cream">Nova senha temporaria</span>
                <Input type="password" minLength={8} maxLength={72} value={password} onChange={(event) => setPassword(event.target.value)} className="border-surface-03 bg-surface-01 text-cream" />
              </label>
              <label className="flex items-center gap-2 text-sm text-cream">
                <input type="checkbox" checked={forcePasswordChange} onChange={(event) => setForcePasswordChange(event.target.checked)} />
                Exigir troca no proximo acesso
              </label>
            </div>
          )}
          {action === "revoke-sessions" && (
            <p className="rounded-xl border border-yellow-500/30 bg-yellow-500/10 p-3 text-sm text-yellow-100">
              Todos os tokens emitidos anteriormente para este usuario serao invalidados. Um novo login sera necessario em cada dispositivo.
            </p>
          )}
          {action === "transfer-owner" && (
            <p className="rounded-xl border border-yellow-500/30 bg-yellow-500/10 p-3 text-sm text-yellow-100">
              O owner atual passara a administrador. O usuario selecionado assumira a propriedade da empresa.
            </p>
          )}
        </ConfirmationDialog>
      )}
    </div>
  );
}

function Domains({ tenantId, items, onChanged }: { tenantId: string; items: ApiPlatformTenantDomain[]; onChanged: (items: ApiPlatformTenantDomain[]) => void }) {
  const { toast } = useToast();
  const [hostname, setHostname] = useState("");
  const [kind, setKind] = useState<"subdomain" | "custom">("subdomain");
  const [saving, setSaving] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [verification, setVerification] = useState<{ record_type: string; record_name: string; record_value: string } | null>(null);
  const [actionTarget, setActionTarget] = useState<ApiPlatformTenantDomain | null>(null);
  const [destructiveAction, setDestructiveAction] = useState<"suspend" | "remove" | null>(null);
  const [actionReason, setActionReason] = useState("");

  async function add() {
    if (!hostname.trim()) return;
    setSaving(true);
    try {
      const created = await platformTenantsApi.createDomain(tenantId, { hostname: hostname.trim(), kind });
      onChanged([created.domain, ...items]);
      setHostname("");
      setVerification(created.verification);
      toast({ title: "Dominio cadastrado", description: "Copie a prova DNS exibida antes de sair desta tela." });
    } catch (err) { toast({ variant: "destructive", title: "Nao foi possivel cadastrar", description: err instanceof Error ? err.message : "Tente novamente." }); }
    finally { setSaving(false); }
  }

  async function copyDns(value: string, label: string) {
    try {
      if (!navigator.clipboard) throw new Error("Area de transferencia indisponivel.");
      await navigator.clipboard.writeText(value);
      toast({ title: `${label} copiado` });
    } catch (err) {
      toast({ variant: "destructive", title: "Nao foi possivel copiar", description: err instanceof Error ? err.message : "Copie manualmente." });
    }
  }

  async function act(domain: ApiPlatformTenantDomain, action: "verify" | "activate" | "primary") {
    setBusyId(domain.id);
    try {
      const updated = await platformDomainsApi.action(domain.id, action);
      onChanged(items.map((item) => item.id === updated.id ? updated : action === "primary" ? { ...item, is_primary: false } : item));
      toast({ title: action === "verify" ? "Teste DNS concluido" : "Dominio atualizado" });
    } catch (err) { toast({ variant: "destructive", title: "Acao nao concluida", description: err instanceof Error ? err.message : "Tente novamente." }); }
    finally { setBusyId(null); }
  }

  function requestDestructive(domain: ApiPlatformTenantDomain, action: "suspend" | "remove") {
    setActionTarget(domain);
    setDestructiveAction(action);
    setActionReason("");
  }

  async function executeDestructive() {
    if (!actionTarget || !destructiveAction || actionReason.trim().length < 3 || busyId) return;
    setBusyId(actionTarget.id);
    try {
      if (destructiveAction === "remove") {
        await platformDomainsApi.remove(actionTarget.id, actionReason.trim());
        onChanged(items.filter((item) => item.id !== actionTarget.id));
      } else {
        const updated = await platformDomainsApi.action(actionTarget.id, "suspend", actionReason.trim());
        onChanged(items.map((item) => item.id === updated.id ? updated : item));
      }
      toast({
        title: destructiveAction === "remove" ? "Dominio removido" : "Dominio suspenso",
        description: "O motivo foi registrado na auditoria.",
      });
      setActionTarget(null);
      setDestructiveAction(null);
      setActionReason("");
    } catch (err) {
      toast({ variant: "destructive", title: "Acao nao concluida", description: err instanceof Error ? err.message : "Tente novamente." });
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="space-y-4">
      <div className="grid gap-3 rounded-xl border border-surface-03 bg-surface-02 p-4 sm:grid-cols-[1fr_auto_auto]">
        <Input value={hostname} onChange={(event) => setHostname(event.target.value)} placeholder="loja.exemplo.com.br" className="border-surface-03 bg-surface-01 text-cream" />
        <select value={kind} onChange={(event) => setKind(event.target.value as typeof kind)} className="rounded-md border border-surface-03 bg-surface-01 px-3 text-sm text-cream">
          <option value="subdomain">Subdominio</option>
          <option value="custom">Dominio proprio</option>
        </select>
        <Button disabled={saving || !hostname.trim()} onClick={() => void add()} className="gap-2 bg-gold text-surface-00 hover:bg-gold/90">
          {saving ? <Loader2 size={15} className="animate-spin" /> : <Plus size={15} />} Adicionar
        </Button>
      </div>

      {verification && (
        <section className="rounded-xl border border-yellow-500/30 bg-yellow-500/10 p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h3 className="font-black text-yellow-100">Prova DNS - copie agora</h3>
              <p className="mt-1 text-xs text-yellow-100/80">O valor de verificacao e exibido somente nesta sessao.</p>
            </div>
            <Button variant="ghost" size="sm" onClick={() => setVerification(null)}>Ocultar</Button>
          </div>
          <div className="mt-4 space-y-2">
            {[
              ["Tipo", verification.record_type],
              ["Nome", verification.record_name],
              ["Valor", verification.record_value],
            ].map(([label, value]) => (
              <div key={label} className="flex items-center gap-2 rounded-lg bg-surface-01 p-3">
                <div className="min-w-0 flex-1"><p className="text-[10px] font-bold uppercase text-stone">{label}</p><p className="mt-1 break-all font-mono text-xs text-cream">{value}</p></div>
                <Button variant="outline" size="icon" aria-label={`Copiar ${label}`} onClick={() => void copyDns(value, label)}><Copy size={14} /></Button>
              </div>
            ))}
          </div>
        </section>
      )}

      {!items.length ? (
        <UnavailableSection title="Nenhum dominio cadastrado" description="Adicione um subdominio Telz ou dominio proprio." />
      ) : (
        <div className="space-y-3">
          {items.map((domain) => {
            const canTestDns = ["pending", "awaiting_dns", "verifying", "dns_error"].includes(domain.status);
            const dnsRecord = domain.expected_txt_record || domain.expected_cname;
            return (
              <article key={domain.id} className="flex flex-col gap-3 rounded-xl border border-surface-03 bg-surface-02 p-4 lg:flex-row lg:items-center lg:justify-between">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="truncate font-bold text-cream">{domain.hostname}</p>
                    <DomainStatusBadge status={domain.status} />
                    {domain.is_primary && <span className="rounded-full border border-gold/30 px-2 py-1 text-xs text-gold">Principal</span>}
                  </div>
                  {dnsRecord ? (
                    <button type="button" onClick={() => void copyDns(dnsRecord, "Registro DNS")} className="mt-2 inline-flex max-w-full items-center gap-2 text-left text-xs text-stone hover:text-cream">
                      <span className="truncate">{dnsRecord}</span><Copy size={12} className="shrink-0" />
                    </button>
                  ) : <p className="mt-2 text-xs text-stone">Sem instrucao DNS pendente.</p>}
                  {domain.error_message && <p className="mt-2 text-xs text-red-300">{domain.error_message}</p>}
                </div>
                <div className="flex flex-wrap gap-2">
                  {canTestDns && <Button variant="outline" size="sm" disabled={busyId === domain.id} onClick={() => void act(domain, "verify")}>Testar DNS</Button>}
                  {domain.status === "verified" && <Button size="sm" disabled={busyId === domain.id} onClick={() => void act(domain, "activate")} className="bg-green-600 text-white">Ativar</Button>}
                  {domain.status === "active" && !domain.is_primary && <Button variant="outline" size="sm" disabled={busyId === domain.id} onClick={() => void act(domain, "primary")}>Definir principal</Button>}
                  {domain.status === "active" && <Button asChild variant="outline" size="sm"><a href={`https://${domain.hostname}`} target="_blank" rel="noreferrer">Testar acesso</a></Button>}
                  {domain.status === "active" && <Button variant="destructive" size="sm" disabled={busyId === domain.id} onClick={() => requestDestructive(domain, "suspend")}>Suspender</Button>}
                  <Button variant="outline" size="sm" disabled={busyId === domain.id} onClick={() => requestDestructive(domain, "remove")} className="gap-1 text-red-300"><Trash2 size={13} /> Remover</Button>
                </div>
              </article>
            );
          })}
        </div>
      )}

      {actionTarget && destructiveAction && (
        <ConfirmationDialog
          open
          onOpenChange={(open) => {
            if (!open && !busyId) {
              setActionTarget(null);
              setDestructiveAction(null);
              setActionReason("");
            }
          }}
          title={destructiveAction === "remove" ? "Remover dominio" : "Suspender dominio"}
          description={`${actionTarget.hostname}: a acao sera registrada na auditoria com o motivo informado.`}
          confirmLabel={busyId ? "Processando..." : destructiveAction === "remove" ? "Remover" : "Suspender"}
          destructive
          reason={actionReason}
          reasonRequired
          confirmDisabled={!!busyId || actionReason.trim().length < 3}
          preventCloseOnConfirm
          onReasonChange={setActionReason}
          onConfirm={() => void executeDestructive()}
        />
      )}
    </div>
  );
}

function Billing({
  tenantId,
  planId,
  items,
  onChanged,
}: {
  tenantId: string;
  planId: string | null;
  items: ApiPlatformInvoice[];
  onChanged: (items: ApiPlatformInvoice[]) => void;
}) {
  const { toast } = useToast();
  const [invoice, setInvoice] = useState<ApiPlatformInvoice | null>(null);
  const [amount, setAmount] = useState("");
  const [method, setMethod] = useState("pix");
  const [reference, setReference] = useState("");
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [actionInvoice, setActionInvoice] = useState<ApiPlatformInvoice | null>(null);
  const [billingAction, setBillingAction] = useState<"discount" | "courtesy" | "extend" | "cancel" | null>(null);
  const [actionReason, setActionReason] = useState("");
  const [discountAmount, setDiscountAmount] = useState("");
  const [newDueAt, setNewDueAt] = useState("");
  const [historyInvoice, setHistoryInvoice] = useState<ApiPlatformInvoice | null>(null);
  const [history, setHistory] = useState<ApiPlatformBillingHistory[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [invoiceDraft, setInvoiceDraft] = useState({
    period_start: "",
    period_end: "",
    due_at: "",
    additions_amount: "0",
    discount_amount: "0",
    status: "pending" as "draft" | "pending" | "courtesy",
    notes: "",
  });
  async function register() {
    if (!invoice || Number(amount) <= 0 || !isPlatformInvoicePaymentAvailable(invoice.status)) return;
    setSaving(true);
    try {
      const result = await platformBillingApi.recordPayment(invoice.id, {
        amount: Number(amount),
        paid_at: new Date().toISOString(),
        payment_method: method,
        reference: reference.trim() || undefined,
        notes: notes.trim() || undefined,
      });
      onChanged(items.map((item) => item.id === result.invoice.id ? result.invoice : item));
      setInvoice(null);
      setAmount("");
      setReference("");
      setNotes("");
      toast({
        title: result.idempotent_replay ? "Pagamento ja registrado" : "Pagamento registrado",
        description: result.idempotent_replay
          ? "A referencia encontrou o mesmo pagamento e nenhuma duplicidade foi criada."
          : "O saldo da fatura foi atualizado.",
      });
    } catch (err) { toast({ variant: "destructive", title: "Nao foi possivel registrar", description: err instanceof Error ? err.message : "Tente novamente." }); }
    finally { setSaving(false); }
  }

  function openBillingAction(item: ApiPlatformInvoice, action: NonNullable<typeof billingAction>) {
    setActionInvoice(item);
    setBillingAction(action);
    setActionReason("");
    setDiscountAmount("");
    setNewDueAt(item.due_at ? item.due_at.slice(0, 10) : "");
  }

  async function executeBillingAction() {
    if (!actionInvoice || !billingAction || actionReason.trim().length < 3) return;
    if (billingAction === "discount" && Number(discountAmount) <= 0) return;
    if (billingAction === "extend" && !newDueAt) return;
    setSaving(true);
    try {
      const updated = billingAction === "discount"
        ? await platformBillingApi.applyDiscount(actionInvoice.id, Number(discountAmount), actionReason.trim())
        : billingAction === "courtesy"
          ? await platformBillingApi.grantCourtesy(actionInvoice.id, actionReason.trim())
          : billingAction === "extend"
            ? await platformBillingApi.extendDueDate(actionInvoice.id, new Date(`${newDueAt}T12:00:00`).toISOString(), actionReason.trim())
            : await platformBillingApi.cancelInvoice(actionInvoice.id, actionReason.trim());
      onChanged(items.map((item) => item.id === updated.id ? updated : item));
      setActionInvoice(null);
      setBillingAction(null);
      setActionReason("");
      toast({ title: "Fatura atualizada", description: "A acao foi registrada no historico financeiro." });
    } catch (err) {
      toast({ variant: "destructive", title: "Nao foi possivel atualizar a fatura", description: err instanceof Error ? err.message : "Tente novamente." });
    } finally {
      setSaving(false);
    }
  }

  async function loadHistory(item: ApiPlatformInvoice) {
    setHistoryInvoice(item);
    setHistoryLoading(true);
    try {
      setHistory(await platformBillingApi.history(item.id));
    } catch (err) {
      toast({ variant: "destructive", title: "Nao foi possivel carregar o historico", description: err instanceof Error ? err.message : "Tente novamente." });
      setHistory([]);
    } finally {
      setHistoryLoading(false);
    }
  }

  async function createInvoice() {
    if (!invoiceDraft.period_start || !invoiceDraft.period_end || !invoiceDraft.due_at) return;
    setSaving(true);
    try {
      const created = await platformTenantsApi.createInvoice(tenantId, {
        plan_id: planId,
        period_start: new Date(`${invoiceDraft.period_start}T12:00:00`).toISOString(),
        period_end: new Date(`${invoiceDraft.period_end}T12:00:00`).toISOString(),
        due_at: new Date(`${invoiceDraft.due_at}T12:00:00`).toISOString(),
        additions_amount: Number(invoiceDraft.additions_amount) || 0,
        discount_amount: Number(invoiceDraft.discount_amount) || 0,
        status: invoiceDraft.status,
        notes: invoiceDraft.notes.trim() || undefined,
      });
      onChanged([created, ...items]);
      setCreateOpen(false);
      setInvoiceDraft({ period_start: "", period_end: "", due_at: "", additions_amount: "0", discount_amount: "0", status: "pending", notes: "" });
      toast({ title: "Fatura gerada" });
    } catch (err) {
      toast({ variant: "destructive", title: "Nao foi possivel gerar a fatura", description: err instanceof Error ? err.message : "Tente novamente." });
    } finally {
      setSaving(false);
    }
  }
  return (
    <div className="space-y-3">
      <div className="flex justify-end"><Button onClick={() => setCreateOpen(true)} className="gap-2 bg-gold text-surface-00 hover:bg-gold/90"><Plus size={15} /> Gerar fatura</Button></div>
      {!items.length && <UnavailableSection title="Nenhuma cobranca cadastrada" description="Gere a primeira fatura SaaS pelo botao acima." />}
      {items.map((item) => (
        <div key={item.id} className="flex flex-col gap-3 rounded-xl border border-surface-03 bg-surface-02 p-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="font-bold text-cream">{Number(item.total_amount).toLocaleString("pt-BR", { style: "currency", currency: "BRL" })}</p>
            <p className="mt-1 text-xs text-stone">Vencimento {item.due_at ? new Date(item.due_at).toLocaleDateString("pt-BR") : "-"} · {item.status}</p>
          </div>
          {isPlatformInvoicePaymentAvailable(item.status) && (
            <div className="flex flex-wrap gap-2">
              <Button size="sm" onClick={() => { setInvoice(item); setAmount(String(item.total_amount)); setReference(""); setNotes(""); }} className="gap-2 bg-gold text-surface-00">
                <CreditCard size={14} /> Pagamento
              </Button>
              <Button variant="outline" size="sm" onClick={() => openBillingAction(item, "discount")}>Desconto</Button>
              <Button variant="outline" size="sm" onClick={() => openBillingAction(item, "extend")}>Prorrogar</Button>
              <Button variant="outline" size="sm" onClick={() => openBillingAction(item, "courtesy")}>Cortesia</Button>
              <Button variant="destructive" size="sm" onClick={() => openBillingAction(item, "cancel")}>Cancelar</Button>
              <Button variant="ghost" size="sm" onClick={() => void loadHistory(item)}>Historico</Button>
            </div>
          )}
          {!isPlatformInvoicePaymentAvailable(item.status) && <Button variant="ghost" size="sm" onClick={() => void loadHistory(item)}>Historico</Button>}
        </div>
      ))}
      {invoice && (
        <ConfirmationDialog
          open
          onOpenChange={(open) => { if (!open) setInvoice(null); }}
          title="Registrar pagamento manual"
          description="Faturas em estado final nao aceitam pagamentos. A referencia, quando informada, evita duplicidade dentro da empresa."
          confirmLabel={saving ? "Registrando..." : "Registrar"}
          confirmDisabled={saving || Number(amount) <= 0}
          preventCloseOnConfirm
          onConfirm={() => void register()}
        >
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="space-y-2 text-sm">
              <span className="font-bold text-cream">Valor pago</span>
              <Input type="number" min="0.01" step="0.01" value={amount} onChange={(event) => setAmount(event.target.value)} className="border-surface-03 bg-surface-01 text-cream" />
            </label>
            <label className="space-y-2 text-sm">
              <span className="font-bold text-cream">Metodo</span>
              <select value={method} onChange={(event) => setMethod(event.target.value)} className="h-10 w-full rounded-md border border-surface-03 bg-surface-01 px-3 text-cream">
                <option value="pix">Pix</option>
                <option value="bank_transfer">Transferencia</option>
                <option value="cash">Dinheiro</option>
                <option value="other">Outro</option>
              </select>
            </label>
            <label className="space-y-2 text-sm sm:col-span-2">
              <span className="font-bold text-cream">Referencia idempotente (opcional)</span>
              <Input value={reference} maxLength={160} onChange={(event) => setReference(event.target.value)} placeholder="Ex.: comprovante-12345" className="border-surface-03 bg-surface-01 text-cream" />
              <span className="block text-xs text-stone">Repetir a mesma referencia com a mesma fatura e valor nao cria outro pagamento.</span>
            </label>
            <label className="space-y-2 text-sm sm:col-span-2">
              <span className="font-bold text-cream">Observacoes (opcional)</span>
              <textarea value={notes} onChange={(event) => setNotes(event.target.value)} className="min-h-20 w-full rounded-xl border border-surface-03 bg-surface-01 px-3 py-2 text-cream outline-none focus:border-gold" />
            </label>
          </div>
        </ConfirmationDialog>
      )}
      {actionInvoice && billingAction && (
        <ConfirmationDialog
          open
          onOpenChange={(open) => { if (!open) { setActionInvoice(null); setBillingAction(null); } }}
          title={billingAction === "discount" ? "Aplicar desconto"
            : billingAction === "courtesy" ? "Conceder cortesia"
            : billingAction === "extend" ? "Prorrogar vencimento"
            : "Cancelar fatura"}
          description="Esta alteracao financeira e auditada e nao pode ser ocultada do historico."
          confirmLabel={saving ? "Salvando..." : "Confirmar"}
          confirmDisabled={saving || billingAction === "discount" && Number(discountAmount) <= 0 || billingAction === "extend" && !newDueAt}
          preventCloseOnConfirm
          destructive={billingAction === "cancel"}
          reason={actionReason}
          reasonRequired
          onReasonChange={setActionReason}
          onConfirm={() => void executeBillingAction()}
        >
          {billingAction === "discount" && (
            <label className="space-y-2 text-sm">
              <span className="font-bold text-cream">Valor do desconto</span>
              <Input type="number" min="0.01" step="0.01" value={discountAmount} onChange={(event) => setDiscountAmount(event.target.value)} className="border-surface-03 bg-surface-01 text-cream" />
            </label>
          )}
          {billingAction === "extend" && (
            <label className="space-y-2 text-sm">
              <span className="font-bold text-cream">Novo vencimento</span>
              <Input type="date" value={newDueAt} onChange={(event) => setNewDueAt(event.target.value)} className="border-surface-03 bg-surface-01 text-cream" />
            </label>
          )}
        </ConfirmationDialog>
      )}
      {historyInvoice && (
        <section className="rounded-2xl border border-surface-03 bg-surface-02 p-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h3 className="font-black text-cream">Historico da fatura</h3>
              <p className="mt-1 text-xs text-stone">{historyInvoice.id}</p>
            </div>
            <Button variant="ghost" size="sm" onClick={() => { setHistoryInvoice(null); setHistory([]); }}>Fechar</Button>
          </div>
          {historyLoading ? <div className="flex justify-center py-8"><Loader2 className="animate-spin text-gold" /></div>
            : !history.length ? <p className="mt-4 text-sm text-stone">Nenhum evento financeiro registrado.</p>
              : <div className="mt-4 space-y-2">{history.map((event) => (
                <div key={event.id} className="rounded-xl border border-surface-03 bg-surface-01 p-3 text-sm">
                  <div className="flex flex-wrap items-center justify-between gap-2"><strong className="text-cream">{event.action}</strong><time className="text-xs text-stone">{new Date(event.created_at).toLocaleString("pt-BR")}</time></div>
                  {event.reason && <p className="mt-2 text-stone">{event.reason}</p>}
                </div>
              ))}</div>}
        </section>
      )}
      {createOpen && (
        <ConfirmationDialog
          open
          onOpenChange={setCreateOpen}
          title="Gerar fatura manual"
          description="A cobranca SaaS e separada dos pagamentos de pedidos da loja."
          confirmLabel={saving ? "Gerando..." : "Gerar fatura"}
          confirmDisabled={saving || !invoiceDraft.period_start || !invoiceDraft.period_end || !invoiceDraft.due_at}
          preventCloseOnConfirm
          onConfirm={() => void createInvoice()}
        >
          <div className="grid gap-3 sm:grid-cols-2">
            <FormField type="date" label="Inicio do periodo" value={invoiceDraft.period_start} onChange={(period_start) => setInvoiceDraft((current) => ({ ...current, period_start }))} />
            <FormField type="date" label="Fim do periodo" value={invoiceDraft.period_end} onChange={(period_end) => setInvoiceDraft((current) => ({ ...current, period_end }))} />
            <FormField type="date" label="Vencimento" value={invoiceDraft.due_at} onChange={(due_at) => setInvoiceDraft((current) => ({ ...current, due_at }))} />
            <label className="space-y-2 text-sm"><span className="font-bold text-cream">Status inicial</span><select value={invoiceDraft.status} onChange={(event) => setInvoiceDraft((current) => ({ ...current, status: event.target.value as typeof current.status }))} className="h-10 w-full rounded-md border border-surface-03 bg-surface-01 px-3 text-cream"><option value="draft">Rascunho</option><option value="pending">Pendente</option><option value="courtesy">Cortesia</option></select></label>
            <FormField type="number" label="Adicionais" value={invoiceDraft.additions_amount} onChange={(additions_amount) => setInvoiceDraft((current) => ({ ...current, additions_amount }))} />
            <FormField type="number" label="Desconto inicial" value={invoiceDraft.discount_amount} onChange={(discount_amount) => setInvoiceDraft((current) => ({ ...current, discount_amount }))} />
            <label className="space-y-2 text-sm sm:col-span-2"><span className="font-bold text-cream">Observacoes</span><textarea value={invoiceDraft.notes} onChange={(event) => setInvoiceDraft((current) => ({ ...current, notes: event.target.value }))} className="min-h-20 w-full rounded-xl border border-surface-03 bg-surface-01 p-3 text-cream" /></label>
          </div>
        </ConfirmationDialog>
      )}
    </div>
  );
}

function Usage({ items, tenant }: { items: ApiPlatformUsageMetric[]; tenant: ApiPlatformTenantDetail }) {
  if (!items.length) return <UnavailableSection title="Sem metricas de consumo" description="Nenhuma medicao foi registrada para esta empresa." />;
  const limits: Record<string, number | null | undefined> = {
    users: tenant.plan?.max_users,
    orders: tenant.plan?.max_orders,
    storage_mb: tenant.plan?.max_storage_mb,
    whatsapp_instances: tenant.plan?.max_whatsapp_instances,
  };
  const latest = new Map<string, ApiPlatformUsageMetric>();
  items.forEach((item) => {
    if (!latest.has(item.metric_key)) latest.set(item.metric_key, item);
  });
  return <div className="grid gap-4 rounded-2xl border border-surface-03 bg-surface-02 p-5 md:grid-cols-2">{[...latest.values()].map((item) => <div key={item.id} className="rounded-xl border border-surface-03 bg-surface-01 p-4"><UsageProgress label={item.metric_key} used={item.value} limit={limits[item.metric_key] ?? null} /><p className="mt-2 text-xs text-stone">Periodo {item.period_key} · atualizado {new Date(item.updated_at).toLocaleString("pt-BR")}</p></div>)}</div>;
}

function Security({ data }: { data: ApiPlatformTenantSecurity | null }) {
  if (!data) return <UnavailableSection title="Seguranca indisponivel" description="O backend nao retornou o resumo de seguranca." />;
  return <div className="space-y-5"><div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{[
    ["Usuarios ativos", data.active_users],
    ["Convites pendentes", data.invited_users],
    ["Usuarios bloqueados", data.blocked_users],
    ["Suportes ativos", data.active_support_sessions],
  ].map(([label, value]) => <div key={String(label)} className="rounded-xl border border-surface-03 bg-surface-02 p-4"><p className="text-xs text-stone">{label}</p><p className="mt-2 text-2xl font-black text-cream">{value}</p></div>)}</div><section className="rounded-2xl border border-surface-03 bg-surface-02 p-5"><h3 className="font-black text-cream">Sessoes de suporte</h3>{!data.support_sessions.length ? <p className="mt-4 text-sm text-stone">Nenhuma sessao registrada.</p> : <div className="mt-4 space-y-3">{data.support_sessions.map((session) => <div key={session.id} className="rounded-xl border border-surface-03 bg-surface-01 p-4 text-sm"><div className="flex items-center justify-between gap-3"><span className="font-bold text-cream">{session.status}</span><span className="text-xs text-stone">{new Date(session.starts_at).toLocaleString("pt-BR")}</span></div><p className="mt-2 text-stone">{session.reason}</p></div>)}</div>}<p className="mt-4 text-xs text-stone">Revogacao manual: {data.session_revocation_available ? "disponivel" : "indisponivel"} · 2FA: {data.two_factor_available ? "disponivel" : "indisponivel"}</p></section></div>;
}

function Notes({ tenantId, items, onChanged }: { tenantId: string; items: ApiPlatformTenantNote[]; onChanged: (items: ApiPlatformTenantNote[]) => void }) {
  const { toast } = useToast();
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  async function add() {
    if (note.trim().length < 2) return;
    setSaving(true);
    try {
      const created = await platformTenantsApi.addNote(tenantId, note.trim());
      onChanged([created, ...items]); setNote(""); toast({ title: "Nota adicionada" });
    } catch (err) { toast({ variant: "destructive", title: "Nao foi possivel adicionar", description: err instanceof Error ? err.message : "Tente novamente." }); }
    finally { setSaving(false); }
  }
  return <div className="space-y-4"><div className="rounded-2xl border border-surface-03 bg-surface-02 p-4"><textarea value={note} onChange={(event) => setNote(event.target.value)} placeholder="Registre uma nota interna para a equipe da plataforma" className="min-h-28 w-full rounded-xl border border-surface-03 bg-surface-01 p-3 text-sm text-cream outline-none focus:border-gold" /><Button disabled={saving || note.trim().length < 2} onClick={() => void add()} className="mt-3 gap-2 bg-gold text-surface-00 hover:bg-gold/90">{saving ? <Loader2 size={15} className="animate-spin" /> : <Plus size={15} />} Adicionar nota</Button></div>{!items.length ? <UnavailableSection title="Nenhuma nota interna" description="Use o campo acima para registrar a primeira nota." /> : <div className="space-y-3">{items.map((item) => <article key={item.id} className="rounded-xl border border-surface-03 bg-surface-02 p-4"><p className="whitespace-pre-wrap text-sm text-cream">{item.note}</p><p className="mt-3 text-xs text-stone">{item.author?.name || "Sistema"} · {new Date(item.created_at).toLocaleString("pt-BR")}</p></article>)}</div>}</div>;
}

function UnavailableSection({ title, description }: { title: string; description: string }) {
  return <div className="rounded-2xl border border-dashed border-surface-03 bg-surface-02/50 p-10 text-center"><Shield className="mx-auto text-stone" /><h3 className="mt-3 font-black text-cream">{title}</h3><p className="mx-auto mt-2 max-w-xl text-sm text-stone">{description}</p></div>;
}
