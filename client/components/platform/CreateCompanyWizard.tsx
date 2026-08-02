import { useMemo, useState } from "react";
import { ArrowLeft, ArrowRight, Building2, Check, Loader2, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ModuleToggleCard } from "@/components/platform/PlatformComponents";
import {
  platformTenantsApi,
  type ApiPlatformCompanyWizard,
  type ApiPlatformModule,
  type ApiPlatformPlan,
  type ApiPlatformProvisionResult,
} from "@/lib/api";
import { normalizePlatformHostnameInput } from "@/lib/platformMaster";

const STEPS = [
  "Dados da empresa",
  "Identificacao",
  "Usuario master",
  "Plano e licenca",
  "Modulos",
  "Dominio",
  "Revisao",
] as const;

const INITIAL: ApiPlatformCompanyWizard = {
  tenant: {
    name: "",
    slug: "",
    legal_name: "",
    timezone: "America/Sao_Paulo",
    locale: "pt-BR",
  },
  owner: {
    name: "",
    email: "",
    phone: "",
    job_title: "",
    password: "",
    force_password_change: true,
    status: "active",
  },
  profile: {},
  plan_id: null,
  module_ids: [],
  trial_days: 0,
  billing_cycle: "monthly",
  currency: "BRL",
  grace_period_days: 0,
  auto_renew: false,
  initial_status: "active",
  license_starts_at: null,
  license_expires_at: null,
  contract_value: null,
  first_due_at: null,
  domain: null,
};

function Field({
  label,
  value,
  onChange,
  required,
  type = "text",
  placeholder,
}: {
  label: string;
  value: string | number | null | undefined;
  onChange: (value: string) => void;
  required?: boolean;
  type?: string;
  placeholder?: string;
}) {
  return (
    <div className="space-y-2">
      <Label>{label}{required ? " *" : ""}</Label>
      <Input
        type={type}
        required={required}
        value={value ?? ""}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
        className="border-surface-03 bg-surface-01 text-cream"
      />
    </div>
  );
}

export default function CreateCompanyWizard({
  plans,
  modules,
  onCreated,
}: {
  plans: ApiPlatformPlan[];
  modules: ApiPlatformModule[];
  onCreated: (created: ApiPlatformProvisionResult) => void;
}) {
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState(0);
  const [form, setForm] = useState<ApiPlatformCompanyWizard>(INITIAL);
  const [domainEnabled, setDomainEnabled] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const selectedModules = useMemo(
    () => new Set(form.module_ids ?? []),
    [form.module_ids, modules],
  );

  function updateProfile(key: string, value: string) {
    setForm((current) => ({
      ...current,
      tenant: {
        ...current.tenant,
      },
      profile: { ...current.profile, [key]: value },
    }));
  }

  function canContinue() {
    if (step === 0) return !!form.tenant.name.trim();
    if (step === 1) return !!form.tenant.slug.trim();
    if (step === 2) return !!form.owner.name.trim() && /\S+@\S+\.\S+/.test(form.owner.email) && form.owner.password.length >= 8;
    if (step === 5 && domainEnabled) return !!form.domain?.hostname.trim();
    return true;
  }

  async function submit() {
    if (!canContinue()) return;
    setSaving(true);
    setError("");
    try {
      const payload: ApiPlatformCompanyWizard = {
        ...form,
        tenant: {
          ...form.tenant,
          name: form.tenant.name.trim(),
          slug: form.tenant.slug.trim().toLowerCase(),
          legal_name: form.tenant.legal_name?.trim() || null,
        },
        owner: {
          ...form.owner,
          name: form.owner.name.trim(),
          email: form.owner.email.trim().toLowerCase(),
          phone: form.owner.phone?.trim() || null,
          job_title: form.owner.job_title?.trim() || null,
          status: "active",
          force_password_change: true,
        },
        license_starts_at: form.license_starts_at
          ? new Date(`${form.license_starts_at.slice(0, 10)}T12:00:00`).toISOString()
          : null,
        license_expires_at: form.license_expires_at
          ? new Date(`${form.license_expires_at.slice(0, 10)}T12:00:00`).toISOString()
          : null,
        first_due_at: form.first_due_at
          ? new Date(`${form.first_due_at.slice(0, 10)}T12:00:00`).toISOString()
          : null,
        module_ids: [...selectedModules],
        domain: domainEnabled && form.domain
          ? {
              ...form.domain,
              hostname: normalizePlatformHostnameInput(form.domain.hostname),
            }
          : null,
      };
      const created = await platformTenantsApi.create(payload);
      onCreated(created);
      setForm(INITIAL);
      setStep(0);
      setDomainEnabled(false);
      setOpen(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nao foi possivel cadastrar a empresa.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(next) => !saving && setOpen(next)}>
      <DialogTrigger asChild>
        <Button className="gap-2 bg-gold font-black text-surface-00 hover:bg-gold/90">
          <Plus size={16} /> Nova empresa
        </Button>
      </DialogTrigger>
      <DialogContent className="max-h-[calc(100dvh-2rem)] max-w-4xl overflow-y-auto border-surface-03 bg-surface-02 text-cream">
        <DialogHeader>
          <DialogTitle>Cadastro de empresa</DialogTitle>
          <DialogDescription className="text-stone">
            Provisionamento transacional: empresa, owner, plano, modulos e dominio sao enviados em uma unica operacao.
          </DialogDescription>
        </DialogHeader>

        <div className="grid grid-cols-3 gap-2 sm:grid-cols-6">
          {STEPS.map((label, index) => (
            <div key={label} className="min-w-0 text-center">
              <div className={`mx-auto flex h-8 w-8 items-center justify-center rounded-full border text-xs font-black ${
                index < step ? "border-green-500 bg-green-500/15 text-green-300" :
                index === step ? "border-gold bg-gold text-surface-00" :
                "border-surface-03 text-stone"
              }`}>
                {index < step ? <Check size={14} /> : index + 1}
              </div>
              <p className="mt-1 hidden truncate text-[10px] text-stone sm:block">{label}</p>
            </div>
          ))}
        </div>

        {error && <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">{error}</div>}

        <div className="min-h-[20rem] rounded-2xl border border-surface-03 bg-surface-01 p-4 md:p-5">
          <div className="mb-5 flex items-center gap-2">
            <Building2 size={18} className="text-gold" />
            <h2 className="font-black text-cream">{STEPS[step]}</h2>
          </div>

          {step === 0 && (
            <div className="grid gap-4 md:grid-cols-2">
              <Field label="Nome fantasia" required value={form.tenant.name} onChange={(name) => setForm({ ...form, tenant: { ...form.tenant, name } })} />
              <Field label="Razao social" value={form.tenant.legal_name} onChange={(legal_name) => setForm({ ...form, tenant: { ...form.tenant, legal_name } })} />
              <Field label="CPF ou CNPJ" value={form.profile?.tax_id} onChange={(value) => updateProfile("tax_id", value)} />
              <Field label="Inscricao estadual" value={form.profile?.state_registration} onChange={(value) => updateProfile("state_registration", value)} />
              <Field label="Inscricao municipal" value={form.profile?.municipal_registration} onChange={(value) => updateProfile("municipal_registration", value)} />
              <Field label="Segmento" value={form.profile?.segment} onChange={(value) => updateProfile("segment", value)} />
              <Field label="Site" value={form.profile?.website} onChange={(value) => updateProfile("website", value)} />
              <Field label="E-mail institucional" type="email" value={form.profile?.email} onChange={(value) => updateProfile("email", value)} />
              <Field label="E-mail de cobranca" type="email" value={form.profile?.billing_email} onChange={(value) => updateProfile("billing_email", value)} />
              <Field label="Telefone" value={form.profile?.phone} onChange={(value) => updateProfile("phone", value)} />
              <Field label="WhatsApp" value={form.profile?.whatsapp} onChange={(value) => updateProfile("whatsapp", value)} />
              <Field label="CEP" value={form.profile?.postal_code} onChange={(value) => updateProfile("postal_code", value)} />
              <Field label="Logradouro" value={form.profile?.address_line} onChange={(value) => updateProfile("address_line", value)} />
              <Field label="Numero" value={form.profile?.address_number} onChange={(value) => updateProfile("address_number", value)} />
              <Field label="Complemento" value={form.profile?.address_extra} onChange={(value) => updateProfile("address_extra", value)} />
              <Field label="Bairro" value={form.profile?.neighborhood} onChange={(value) => updateProfile("neighborhood", value)} />
              <Field label="Cidade" value={form.profile?.city} onChange={(value) => updateProfile("city", value)} />
              <Field label="Estado" value={form.profile?.state} onChange={(value) => updateProfile("state", value.toUpperCase().slice(0, 2))} />
              <Field label="Responsavel legal" value={form.profile?.legal_representative_name} onChange={(value) => updateProfile("legal_representative_name", value)} />
              <Field label="Documento do responsavel" value={form.profile?.legal_representative_document} onChange={(value) => updateProfile("legal_representative_document", value)} />
              <Field label="E-mail do responsavel" type="email" value={form.profile?.legal_representative_email} onChange={(value) => updateProfile("legal_representative_email", value)} />
              <Field label="Telefone do responsavel" value={form.profile?.legal_representative_phone} onChange={(value) => updateProfile("legal_representative_phone", value)} />
            </div>
          )}

          {step === 1 && (
            <div className="grid gap-4 md:grid-cols-2">
              <Field
                label="Slug"
                required
                value={form.tenant.slug}
                onChange={(slug) => setForm({ ...form, tenant: { ...form.tenant, slug: slug.toLowerCase().replace(/[^a-z0-9-]/g, "") } })}
                placeholder="minha-empresa"
              />
              <Field label="Fuso horario" value={form.tenant.timezone} onChange={(timezone) => setForm({ ...form, tenant: { ...form.tenant, timezone } })} />
              <Field label="Idioma" value={form.tenant.locale} onChange={(locale) => setForm({ ...form, tenant: { ...form.tenant, locale } })} />
              <Field label="Codigo interno" value={form.profile?.internal_code} onChange={(value) => updateProfile("internal_code", value)} />
              <Field label="URL do logo" value={form.profile?.logo_url} onChange={(value) => updateProfile("logo_url", value)} />
              <div className="space-y-2">
                <Label>Status inicial</Label>
                <select value={form.initial_status} onChange={(event) => setForm({ ...form, initial_status: event.target.value as ApiPlatformCompanyWizard["initial_status"] })} className="h-10 w-full rounded-md border border-surface-03 bg-surface-02 px-3 text-sm text-cream">
                  <option value="active">Ativa</option>
                  <option value="suspended">Suspensa</option>
                  <option value="disabled">Desativada</option>
                </select>
              </div>
              <div className="rounded-xl border border-surface-03 p-4 text-sm text-stone">
                O tenant_id sera gerado pelo backend e ficara imutavel.
              </div>
            </div>
          )}

          {step === 2 && (
            <div className="grid gap-4 md:grid-cols-2">
              <Field label="Nome" required value={form.owner.name} onChange={(name) => setForm({ ...form, owner: { ...form.owner, name } })} />
              <Field label="E-mail" required type="email" value={form.owner.email} onChange={(email) => setForm({ ...form, owner: { ...form.owner, email } })} />
              <Field label="Telefone" value={form.owner.phone} onChange={(phone) => setForm({ ...form, owner: { ...form.owner, phone } })} />
              <Field label="Cargo" value={form.owner.job_title} onChange={(job_title) => setForm({ ...form, owner: { ...form.owner, job_title } })} />
              <Field label="Senha temporaria (min. 8)" required type="password" value={form.owner.password} onChange={(password) => setForm({ ...form, owner: { ...form.owner, password } })} />
              <div className="rounded-xl border border-surface-03 p-4 text-sm text-stone">
                <p className="font-bold text-cream">Acesso inicial seguro</p>
                <p className="mt-1 text-xs leading-relaxed">O proprietario sera criado ativo com a senha temporaria e devera troca-la no primeiro acesso.</p>
              </div>
              <p className="md:col-span-2 text-xs text-stone">A senha e enviada apenas nesta criacao e nunca deve retornar pela API.</p>
            </div>
          )}

          {step === 3 && (
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label>Plano</Label>
                <select
                  value={form.plan_id ?? ""}
                  onChange={(event) => setForm({ ...form, plan_id: event.target.value || null })}
                  className="h-10 w-full rounded-md border border-surface-03 bg-surface-02 px-3 text-sm text-cream"
                >
                  <option value="">Configurar depois</option>
                  {plans.filter((plan) => plan.status === "active").map((plan) => <option key={plan.id} value={plan.id}>{plan.name}</option>)}
                </select>
              </div>
              <Field label="Periodo de teste (dias)" type="number" value={form.trial_days} onChange={(value) => setForm({ ...form, trial_days: Math.max(0, Number(value) || 0) })} />
              <div className="space-y-2">
                <Label>Ciclo de cobranca</Label>
                <select value={form.billing_cycle} onChange={(event) => setForm({ ...form, billing_cycle: event.target.value as ApiPlatformCompanyWizard["billing_cycle"] })} className="h-10 w-full rounded-md border border-surface-03 bg-surface-02 px-3 text-sm text-cream">
                  <option value="monthly">Mensal</option><option value="quarterly">Trimestral</option><option value="semiannual">Semestral</option><option value="annual">Anual</option><option value="custom">Personalizado</option>
                </select>
              </div>
              <Field label="Moeda" value={form.currency} onChange={(currency) => setForm({ ...form, currency: currency.toUpperCase().slice(0, 3) })} />
              <Field label="Carencia (dias)" type="number" value={form.grace_period_days} onChange={(value) => setForm({ ...form, grace_period_days: Math.max(0, Number(value) || 0) })} />
              <Field label="Inicio da licenca" type="date" value={form.license_starts_at?.slice(0, 10)} onChange={(license_starts_at) => setForm({ ...form, license_starts_at: license_starts_at || null })} />
              <Field label="Fim da licenca" type="date" value={form.license_expires_at?.slice(0, 10)} onChange={(license_expires_at) => setForm({ ...form, license_expires_at: license_expires_at || null })} />
              <Field label="Valor do contrato" type="number" value={form.contract_value} onChange={(value) => setForm({ ...form, contract_value: value === "" ? null : Math.max(0, Number(value) || 0) })} />
              <Field label="Primeiro vencimento" type="date" value={form.first_due_at?.slice(0, 10)} onChange={(first_due_at) => setForm({ ...form, first_due_at: first_due_at || null })} />
              <label className="flex items-center gap-3 rounded-xl border border-surface-03 p-4 text-sm font-bold text-cream">
                <input type="checkbox" checked={form.auto_renew ?? false} onChange={(event) => setForm({ ...form, auto_renew: event.target.checked })} />
                Renovacao automatica
              </label>
            </div>
          )}

          {step === 4 && (
            <div className="grid gap-3 md:grid-cols-2">
              {!modules.length && <p className="md:col-span-2 text-sm text-stone">Nenhum modulo disponivel para selecao.</p>}
              {modules.map((module) => (
                <ModuleToggleCard
                  key={module.id}
                  module={module}
                  checked={selectedModules.has(module.id)}
                  onCheckedChange={(checked) => {
                    const next = new Set(selectedModules);
                    if (checked) next.add(module.id); else next.delete(module.id);
                    setForm({ ...form, module_ids: [...next] });
                  }}
                />
              ))}
            </div>
          )}

          {step === 5 && (
            <div className="space-y-4">
              <label className="flex items-center gap-3 rounded-xl border border-surface-03 p-4 text-sm font-bold text-cream">
                <input type="checkbox" checked={domainEnabled} onChange={(event) => {
                  const enabled = event.target.checked;
                  setDomainEnabled(enabled);
                  setForm({ ...form, domain: enabled ? { hostname: "", kind: "subdomain" } : null });
                }} />
                Cadastrar dominio junto com a empresa
              </label>
              {domainEnabled && form.domain && (
                <div className="grid gap-4 md:grid-cols-2">
                  <Field label="Hostname" required value={form.domain.hostname} onChange={(hostname) => setForm({ ...form, domain: { ...form.domain!, hostname } })} placeholder="loja.exemplo.com.br" />
                  <div className="space-y-2">
                    <Label>Tipo</Label>
                    <select
                      value={form.domain.kind}
                      onChange={(event) => setForm({ ...form, domain: { ...form.domain!, kind: event.target.value as "subdomain" | "custom" } })}
                      className="h-10 w-full rounded-md border border-surface-03 bg-surface-02 px-3 text-sm text-cream"
                    >
                      <option value="subdomain">Subdominio Telz</option>
                      <option value="custom">Dominio proprio</option>
                    </select>
                  </div>
                </div>
              )}
            </div>
          )}

          {step === 6 && (
            <div className="grid gap-4 md:grid-cols-2">
              <div className="rounded-xl border border-surface-03 p-4">
                <p className="text-xs font-bold uppercase tracking-wide text-gold">Empresa</p>
                <p className="mt-2 font-black text-cream">{form.tenant.name}</p>
                <p className="text-sm text-stone">{form.tenant.legal_name || "Sem razao social"} · {form.tenant.slug}</p>
              </div>
              <div className="rounded-xl border border-surface-03 p-4">
                <p className="text-xs font-bold uppercase tracking-wide text-gold">Owner</p>
                <p className="mt-2 font-black text-cream">{form.owner.name}</p>
                <p className="text-sm text-stone">{form.owner.email}</p>
              </div>
              <div className="rounded-xl border border-surface-03 p-4">
                <p className="text-xs font-bold uppercase tracking-wide text-gold">Contrato inicial</p>
                <p className="mt-2 text-sm text-cream">{plans.find((plan) => plan.id === form.plan_id)?.name || "Sem plano"}</p>
                <p className="text-sm text-stone">{form.trial_days || 0} dia(s) de teste · {selectedModules.size} modulo(s)</p>
                <p className="text-sm text-stone">{form.billing_cycle} · {form.currency} · carencia {form.grace_period_days || 0} dia(s)</p>
                <p className="text-sm text-stone">Licenca {form.license_starts_at || "inicio automatico"} ate {form.license_expires_at || "fim calculado"} · contrato {form.contract_value ?? "nao informado"}</p>
              </div>
              <div className="rounded-xl border border-surface-03 p-4">
                <p className="text-xs font-bold uppercase tracking-wide text-gold">Dominio</p>
                <p className="mt-2 text-sm text-cream">{domainEnabled ? form.domain?.hostname || "Pendente" : "Configurar depois"}</p>
                <p className="text-sm text-stone">O backend gerara o desafio DNS.</p>
              </div>
            </div>
          )}
        </div>

        <DialogFooter className="flex-row items-center justify-between sm:justify-between">
          <Button variant="outline" disabled={saving || step === 0} onClick={() => setStep((current) => current - 1)} className="gap-2">
            <ArrowLeft size={15} /> Voltar
          </Button>
          {step < STEPS.length - 1 ? (
            <Button disabled={!canContinue()} onClick={() => setStep((current) => current + 1)} className="gap-2 bg-gold text-surface-00 hover:bg-gold/90">
              Continuar <ArrowRight size={15} />
            </Button>
          ) : (
            <Button disabled={saving || !canContinue()} onClick={() => void submit()} className="gap-2 bg-gold font-black text-surface-00 hover:bg-gold/90">
              {saving ? <Loader2 size={15} className="animate-spin" /> : <Check size={15} />}
              Criar empresa
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
