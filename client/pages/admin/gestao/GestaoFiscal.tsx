import { useEffect, useState } from "react";
import { AlertTriangle, Building2, FileCheck2, FileText, KeyRound, LayoutDashboard, Loader2, Plus, RefreshCw, Send, Settings, ShieldCheck, Tags } from "lucide-react";
import { AdminPageTabs, type AdminPageTab } from "@/components/admin/AdminPageChrome";
import AdminGestao from "./AdminGestao";
import {
  fiscalApi,
  type FiscalCertificateInput,
  type FiscalCompanyInput,
  type FiscalDocument,
  type FiscalEnvironment,
  type FiscalOverview,
  type FiscalProductProfileInput,
  type FiscalSeriesInput,
} from "@/lib/api";

type FiscalSection = "settings" | "overview" | "company" | "certificate" | "profiles" | "documents";

const sections: AdminPageTab<FiscalSection>[] = [
  { id: "settings", label: "Configuracoes", icon: Settings },
  { id: "overview", label: "Resumo", icon: LayoutDashboard },
  { id: "company", label: "Empresa", icon: Building2 },
  { id: "certificate", label: "Certificado e serie", icon: KeyRound },
  { id: "profiles", label: "Perfis tributarios", icon: Tags },
  { id: "documents", label: "Documentos", icon: FileText },
];

const panelClass = "rounded-lg border border-surface-03 bg-surface-02 p-5";
const inputClass = "w-full rounded-lg border border-surface-03 bg-surface-01 px-3 py-2 text-sm text-cream outline-none transition focus:border-gold";
const buttonClass = "inline-flex items-center justify-center gap-2 rounded-lg bg-gold px-3 py-2 text-sm font-black text-black transition hover:bg-gold/90 disabled:cursor-not-allowed disabled:opacity-60";

function today() {
  return new Date().toISOString().slice(0, 10);
}

function currency(value: number) {
  return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(value || 0);
}

const emptyCompany: FiscalCompanyInput = {
  legal_name: "",
  trade_name: "",
  document: "",
  state_registration: "",
  municipal_registration: "",
  tax_regime: "simples_nacional",
  cnae: "",
  address_street: "",
  address_number: "",
  address_complement: "",
  neighborhood: "",
  city: "",
  city_ibge_code: "",
  state: "SP",
  zip_code: "",
  phone: "",
  email: "",
  active: true,
};

const emptyCertificate: FiscalCertificateInput = {
  certificate_type: "a1",
  subject_name: "",
  serial_number: "",
  valid_from: today(),
  valid_until: today(),
  storage_reference: "",
  password_configured: false,
  active: true,
};

const emptySeries: FiscalSeriesInput = {
  document_model: "NFCe",
  series: "1",
  environment: "homologation",
  next_number: 1,
  active: true,
  notes: "",
};

const emptyProfile: FiscalProductProfileInput = {
  product_id: "",
  ncm: "",
  cest: "",
  cfop: "5102",
  origin: "0",
  cst: "",
  csosn: "102",
  icms_rate: 0,
  pis_cst: "49",
  pis_rate: 0,
  cofins_cst: "49",
  cofins_rate: 0,
  fiscal_description: "",
  active: true,
};

export default function GestaoFiscal() {
  const [section, setSection] = useState<FiscalSection>("settings");

  return (
    <AdminGestao
      moduleKey="fiscal"
      showSettings={section === "settings"}
      moduleTabs={<AdminPageTabs<FiscalSection> tabs={sections} active={section} onChange={setSection} />}
    >
      {section !== "settings" && <FiscalPanel section={section} />}
    </AdminGestao>
  );
}

function FiscalPanel({ section }: { section: Exclude<FiscalSection, "settings"> }) {
  const [data, setData] = useState<FiscalOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [companyDraft, setCompanyDraft] = useState<FiscalCompanyInput>(emptyCompany);
  const [certificateDraft, setCertificateDraft] = useState<FiscalCertificateInput>(emptyCertificate);
  const [seriesDraft, setSeriesDraft] = useState<FiscalSeriesInput>(emptySeries);
  const [profileDraft, setProfileDraft] = useState<FiscalProductProfileInput>(emptyProfile);
  const [orderId, setOrderId] = useState("");
  const [documentEnvironment, setDocumentEnvironment] = useState<FiscalEnvironment>("homologation");

  const load = () => {
    setLoading(true);
    setError("");
    fiscalApi.overview()
      .then((payload) => {
        setData(payload);
        if (payload.company) setCompanyDraft(payload.company);
        if (payload.certificate) setCertificateDraft(payload.certificate);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Nao foi possivel carregar Fiscal."))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, []);

  const run = async (key: string, action: () => Promise<unknown>, success: string) => {
    setSaving(key);
    setError("");
    setMessage("");
    try {
      await action();
      setMessage(success);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Operacao fiscal nao concluida.");
    } finally {
      setSaving("");
    }
  };

  return (
    <section className="space-y-5">
      <div className={panelClass}>
        <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
          <div>
            <h3 className="text-lg font-black text-cream">Fiscal SEFAZ nativo</h3>
            <p className="text-sm text-stone">Cadastro fiscal, series, perfis tributarios, XML interno e historico de operacoes SEFAZ.</p>
          </div>
          <button type="button" onClick={load} disabled={loading} className="inline-flex items-center justify-center gap-2 rounded-lg border border-surface-03 px-3 py-2 text-sm font-bold text-stone transition hover:bg-surface-03 hover:text-cream disabled:opacity-60">
            {loading ? <Loader2 size={15} className="animate-spin" /> : <RefreshCw size={15} />}
            Atualizar
          </button>
        </div>
      </div>

      {loading && (
        <div className="flex min-h-48 items-center justify-center rounded-lg border border-surface-03 bg-surface-02 text-stone">
          <Loader2 size={18} className="mr-2 animate-spin" /> Carregando fiscal...
        </div>
      )}

      {!loading && (error || message) && (
        <div className={`rounded-lg border p-4 text-sm ${error ? "border-red-500/30 bg-red-500/10 text-red-200" : "border-emerald-500/30 bg-emerald-500/10 text-emerald-200"}`}>
          {error || message}
        </div>
      )}

      {!loading && data && (
        <>
          {section === "overview" && (
            <>
              <div className="grid gap-4 md:grid-cols-4">
                <Metric title="Setup" value={data.ready_for_homologation ? "Homologacao pronta" : "Pendente"} tone={data.ready_for_homologation ? "success" : "warn"} />
                <Metric title="Empresa" value={data.company?.document || "Nao cadastrada"} />
                <Metric title="Certificado" value={data.certificate?.valid ? "Valido" : "Pendente"} tone={data.certificate?.valid ? "success" : "warn"} />
                <Metric title="Documentos" value={String(data.documents.length)} />
              </div>

              {data.missing_setup.length > 0 && (
                <div className="rounded-lg border border-amber-500/25 bg-amber-500/10 p-4 text-sm text-amber-200">
                  <div className="flex items-center gap-2 font-black"><AlertTriangle size={16} /> Pendencias fiscais</div>
                  <p className="mt-1">{data.missing_setup.join(", ")}</p>
                </div>
              )}
            </>
          )}

          <div className="grid gap-5 xl:grid-cols-3">
            {section === "company" && <div className={panelClass}>
              <h4 className="mb-4 text-sm font-black uppercase tracking-wide text-parchment">Empresa fiscal</h4>
              <div className="space-y-3">
                <input className={inputClass} placeholder="Razao social" value={companyDraft.legal_name} onChange={(e) => setCompanyDraft({ ...companyDraft, legal_name: e.target.value })} />
                <input className={inputClass} placeholder="Nome fantasia" value={companyDraft.trade_name || ""} onChange={(e) => setCompanyDraft({ ...companyDraft, trade_name: e.target.value })} />
                <div className="grid grid-cols-2 gap-3">
                  <input className={inputClass} placeholder="CNPJ" value={companyDraft.document} onChange={(e) => setCompanyDraft({ ...companyDraft, document: e.target.value })} />
                  <input className={inputClass} placeholder="IE" value={companyDraft.state_registration || ""} onChange={(e) => setCompanyDraft({ ...companyDraft, state_registration: e.target.value })} />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <input className={inputClass} placeholder="CRT/regime" value={companyDraft.tax_regime} onChange={(e) => setCompanyDraft({ ...companyDraft, tax_regime: e.target.value })} />
                  <input className={inputClass} placeholder="CNAE" value={companyDraft.cnae || ""} onChange={(e) => setCompanyDraft({ ...companyDraft, cnae: e.target.value })} />
                </div>
                <input className={inputClass} placeholder="Endereco" value={companyDraft.address_street || ""} onChange={(e) => setCompanyDraft({ ...companyDraft, address_street: e.target.value })} />
                <div className="grid grid-cols-3 gap-3">
                  <input className={inputClass} placeholder="Numero" value={companyDraft.address_number || ""} onChange={(e) => setCompanyDraft({ ...companyDraft, address_number: e.target.value })} />
                  <input className={inputClass} placeholder="Cidade" value={companyDraft.city || ""} onChange={(e) => setCompanyDraft({ ...companyDraft, city: e.target.value })} />
                  <input className={inputClass} placeholder="UF" value={companyDraft.state || ""} onChange={(e) => setCompanyDraft({ ...companyDraft, state: e.target.value.toUpperCase().slice(0, 2) })} />
                </div>
                <input className={inputClass} placeholder="Codigo IBGE municipio" value={companyDraft.city_ibge_code || ""} onChange={(e) => setCompanyDraft({ ...companyDraft, city_ibge_code: e.target.value })} />
                <button type="button" className={buttonClass} disabled={saving === "company"} onClick={() => run("company", () => fiscalApi.updateCompany(companyDraft), "Empresa fiscal salva.")}>
                  {saving === "company" ? <Loader2 size={15} className="animate-spin" /> : <ShieldCheck size={15} />}
                  Salvar empresa
                </button>
              </div>
            </div>}

            {section === "certificate" && <div className={panelClass}>
              <h4 className="mb-4 text-sm font-black uppercase tracking-wide text-parchment">Certificado e serie</h4>
              <div className="space-y-3">
                <select className={inputClass} value={certificateDraft.certificate_type} onChange={(e) => setCertificateDraft({ ...certificateDraft, certificate_type: e.target.value as "a1" | "a3" })}>
                  <option value="a1">A1</option>
                  <option value="a3">A3</option>
                </select>
                <input className={inputClass} placeholder="Titular do certificado" value={certificateDraft.subject_name || ""} onChange={(e) => setCertificateDraft({ ...certificateDraft, subject_name: e.target.value })} />
                <input className={inputClass} placeholder="Numero de serie" value={certificateDraft.serial_number || ""} onChange={(e) => setCertificateDraft({ ...certificateDraft, serial_number: e.target.value })} />
                <div className="grid grid-cols-2 gap-3">
                  <input className={inputClass} type="date" value={certificateDraft.valid_from || ""} onChange={(e) => setCertificateDraft({ ...certificateDraft, valid_from: e.target.value })} />
                  <input className={inputClass} type="date" value={certificateDraft.valid_until || ""} onChange={(e) => setCertificateDraft({ ...certificateDraft, valid_until: e.target.value })} />
                </div>
                <input className={inputClass} placeholder="Referencia segura do arquivo" value={certificateDraft.storage_reference || ""} onChange={(e) => setCertificateDraft({ ...certificateDraft, storage_reference: e.target.value })} />
                <label className="flex items-center gap-2 text-sm text-stone">
                  <input type="checkbox" checked={certificateDraft.password_configured} onChange={(e) => setCertificateDraft({ ...certificateDraft, password_configured: e.target.checked })} />
                  Senha configurada fora da resposta da API
                </label>
                <button type="button" className={buttonClass} disabled={saving === "certificate"} onClick={() => run("certificate", () => fiscalApi.updateCertificate(certificateDraft), "Metadados do certificado salvos.")}>
                  <FileCheck2 size={15} /> Salvar certificado
                </button>
                <div className="border-t border-surface-03 pt-3" />
                <div className="grid grid-cols-3 gap-3">
                  <select className={inputClass} value={seriesDraft.document_model} onChange={(e) => setSeriesDraft({ ...seriesDraft, document_model: e.target.value as "NFCe" | "NFe" })}>
                    <option value="NFCe">NFC-e</option>
                    <option value="NFe">NF-e</option>
                  </select>
                  <input className={inputClass} placeholder="Serie" value={seriesDraft.series} onChange={(e) => setSeriesDraft({ ...seriesDraft, series: e.target.value })} />
                  <input className={inputClass} type="number" min="1" value={seriesDraft.next_number} onChange={(e) => setSeriesDraft({ ...seriesDraft, next_number: Number(e.target.value || 1) })} />
                </div>
                <select className={inputClass} value={seriesDraft.environment} onChange={(e) => setSeriesDraft({ ...seriesDraft, environment: e.target.value as FiscalEnvironment })}>
                  <option value="homologation">Homologacao</option>
                  <option value="production">Producao</option>
                </select>
                <button type="button" className={buttonClass} disabled={saving === "series"} onClick={() => run("series", () => fiscalApi.createSeries(seriesDraft), "Serie fiscal criada.")}>
                  <Plus size={15} /> Criar serie
                </button>
              </div>
            </div>}

            {section === "profiles" && <div className={panelClass}>
              <h4 className="mb-4 text-sm font-black uppercase tracking-wide text-parchment">Perfil tributario</h4>
              <div className="space-y-3">
                <input className={inputClass} placeholder="ID do produto" value={profileDraft.product_id} onChange={(e) => setProfileDraft({ ...profileDraft, product_id: e.target.value })} />
                <input className={inputClass} placeholder="Descricao fiscal" value={profileDraft.fiscal_description || ""} onChange={(e) => setProfileDraft({ ...profileDraft, fiscal_description: e.target.value })} />
                <div className="grid grid-cols-3 gap-3">
                  <input className={inputClass} placeholder="NCM" value={profileDraft.ncm} onChange={(e) => setProfileDraft({ ...profileDraft, ncm: e.target.value })} />
                  <input className={inputClass} placeholder="CEST" value={profileDraft.cest || ""} onChange={(e) => setProfileDraft({ ...profileDraft, cest: e.target.value })} />
                  <input className={inputClass} placeholder="CFOP" value={profileDraft.cfop} onChange={(e) => setProfileDraft({ ...profileDraft, cfop: e.target.value })} />
                </div>
                <div className="grid grid-cols-3 gap-3">
                  <input className={inputClass} placeholder="Origem" value={profileDraft.origin} onChange={(e) => setProfileDraft({ ...profileDraft, origin: e.target.value })} />
                  <input className={inputClass} placeholder="CST" value={profileDraft.cst || ""} onChange={(e) => setProfileDraft({ ...profileDraft, cst: e.target.value })} />
                  <input className={inputClass} placeholder="CSOSN" value={profileDraft.csosn || ""} onChange={(e) => setProfileDraft({ ...profileDraft, csosn: e.target.value })} />
                </div>
                <div className="grid grid-cols-3 gap-3">
                  <input className={inputClass} type="number" step="0.01" placeholder="ICMS %" value={profileDraft.icms_rate} onChange={(e) => setProfileDraft({ ...profileDraft, icms_rate: Number(e.target.value || 0) })} />
                  <input className={inputClass} type="number" step="0.01" placeholder="PIS %" value={profileDraft.pis_rate} onChange={(e) => setProfileDraft({ ...profileDraft, pis_rate: Number(e.target.value || 0) })} />
                  <input className={inputClass} type="number" step="0.01" placeholder="COFINS %" value={profileDraft.cofins_rate} onChange={(e) => setProfileDraft({ ...profileDraft, cofins_rate: Number(e.target.value || 0) })} />
                </div>
                <button type="button" className={buttonClass} disabled={saving === "profile" || !profileDraft.product_id} onClick={() => run("profile", () => fiscalApi.updateProductProfile(profileDraft.product_id, profileDraft), "Perfil tributario salvo.")}>
                  <Plus size={15} /> Salvar perfil
                </button>
              </div>
            </div>
            }
          </div>

          {section === "documents" && <div className="grid gap-5 xl:grid-cols-[24rem_minmax(0,1fr)]">
            <div className={panelClass}>
              <h4 className="mb-4 text-sm font-black uppercase tracking-wide text-parchment">Documento por pedido</h4>
              <div className="space-y-3">
                <input className={inputClass} placeholder="ID do pedido" value={orderId} onChange={(e) => setOrderId(e.target.value)} />
                <select className={inputClass} value={documentEnvironment} onChange={(e) => setDocumentEnvironment(e.target.value as FiscalEnvironment)}>
                  <option value="homologation">Homologacao</option>
                  <option value="production">Producao</option>
                </select>
                <button type="button" className={buttonClass} disabled={saving === "document" || !orderId} onClick={() => run("document", () => fiscalApi.createDocumentFromOrder(orderId, { document_model: "NFCe", environment: documentEnvironment }), "Documento fiscal preparado.")}>
                  <FileCheck2 size={15} /> Preparar NFC-e
                </button>
              </div>
              <div className="mt-5 space-y-2">
                {data.series.map((item) => (
                  <div key={item.id} className="rounded-lg border border-surface-03 bg-surface-01 px-3 py-2 text-sm text-stone">
                    <b className="text-cream">{item.document_model} serie {item.series}</b>
                    <span className="block text-xs">{item.environment} - proximo {item.next_number}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className={panelClass}>
              <h4 className="mb-4 text-sm font-black uppercase tracking-wide text-parchment">Documentos fiscais</h4>
              <div className="space-y-2">
                {data.documents.map((doc) => (
                  <DocumentRow key={doc.id} doc={doc} saving={saving} run={run} />
                ))}
                {data.documents.length === 0 && <EmptyText text="Nenhum documento fiscal preparado." />}
              </div>
            </div>
          </div>}
        </>
      )}
    </section>
  );
}

function DocumentRow({
  doc,
  saving,
  run,
}: {
  doc: FiscalDocument;
  saving: string;
  run: (key: string, action: () => Promise<unknown>, success: string) => Promise<void>;
}) {
  return (
    <div className="grid gap-3 rounded-lg border border-surface-03 bg-surface-01 px-4 py-3 md:grid-cols-[1fr_auto_auto] md:items-center">
      <div className="min-w-0">
        <p className="font-bold text-cream">{doc.document_model} {doc.series || "-"} / {doc.number || "-"}</p>
        <p className="truncate text-xs text-stone">Pedido {doc.order_id || "-"} - {doc.access_key || "sem chave"}</p>
        <p className="text-xs text-stone">{doc.environment} - {doc.status} - {currency(doc.total_document)}</p>
      </div>
      <div className="flex flex-wrap gap-2">
        {doc.status === "validated" && (
          <button type="button" disabled={!!saving} onClick={() => run(doc.id, () => fiscalApi.signDocument(doc.id), "Documento assinado.")} className="rounded-lg border border-sky-500/30 p-2 text-sky-300 transition hover:bg-sky-500/10" title="Assinar">
            <ShieldCheck size={16} />
          </button>
        )}
        {doc.status === "signed" && (
          <button type="button" disabled={!!saving} onClick={() => run(doc.id, () => fiscalApi.transmitDocument(doc.id), "Documento enviado para fila SEFAZ.")} className="rounded-lg border border-emerald-500/30 p-2 text-emerald-300 transition hover:bg-emerald-500/10" title="Transmitir">
            <Send size={16} />
          </button>
        )}
        <button type="button" disabled={!!saving} onClick={() => run(doc.id, () => fiscalApi.consultDocument(doc.id), "Consulta registrada.")} className="rounded-lg border border-surface-03 p-2 text-stone transition hover:bg-surface-03 hover:text-cream" title="Consultar">
          <RefreshCw size={16} />
        </button>
      </div>
      <div className="text-right text-xs text-stone">
        {doc.events?.[0]?.message || "Sem eventos"}
      </div>
    </div>
  );
}

function Metric({ title, value, tone = "default" }: { title: string; value: string; tone?: "default" | "success" | "warn" }) {
  const toneClass = tone === "success" ? "text-emerald-300" : tone === "warn" ? "text-amber-300" : "text-gold";
  return (
    <div className={panelClass}>
      <div className="mb-2 text-xs font-black uppercase tracking-wide text-stone">{title}</div>
      <p className={`text-lg font-black ${toneClass}`}>{value}</p>
    </div>
  );
}

function EmptyText({ text }: { text: string }) {
  return <div className="rounded-lg border border-surface-03 bg-surface-01 p-5 text-center text-sm text-stone">{text}</div>;
}
