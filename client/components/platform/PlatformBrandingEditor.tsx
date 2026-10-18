import { useCallback, useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useApp } from "@/context/AppContext";
import { platformBrandingApi, resolveAssetUrl, type ApiPlatformBranding } from "@/lib/api";
import { hasPlatformCapability, readPlatformPermissions } from "@/lib/platformCapabilities";

function BrandingPreview({ url, label }: { url: string; label: string }) {
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [url]);
  return <div className="flex h-20 w-28 items-center justify-center overflow-hidden rounded-lg border border-surface-03 bg-surface-01 text-xs text-stone">
    {url && !failed ? <img src={resolveAssetUrl(url)} alt={label} className="h-full w-full object-contain" onError={() => setFailed(true)} /> : failed ? "Imagem indisponivel" : "Padrao Telz"}
  </div>;
}

export default function PlatformBrandingEditor() {
  const { refreshSiteContent } = useApp();
  const canManage = hasPlatformCapability(readPlatformPermissions(), "platform_settings.manage");
  const [draft, setDraft] = useState<ApiPlatformBranding>({ logo_url: "", favicon_url: "" });
  const [saved, setSaved] = useState<ApiPlatformBranding | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState<keyof ApiPlatformBranding | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const load = useCallback(async () => {
    setLoading(true); setError("");
    try { const value = await platformBrandingApi.get(); setDraft(value); setSaved(value); }
    catch (err) { setError(err instanceof Error ? err.message : "Falha ao carregar a marca do gestor."); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { void load(); }, [load]);
  const dirty = saved !== null && (saved.logo_url !== draft.logo_url || saved.favicon_url !== draft.favicon_url);

  async function upload(field: keyof ApiPlatformBranding, input: HTMLInputElement) {
    const file = input.files?.[0];
    if (!file || !canManage) return;
    setError(""); setMessage(""); setUploading(field);
    try {
      if (!["image/png", "image/jpeg", "image/webp"].includes(file.type)) throw new Error("Use uma imagem PNG, JPEG ou WebP.");
      if (file.size > 5 * 1024 * 1024) throw new Error("O arquivo deve ter no maximo 5 MB.");
      const url = await platformBrandingApi.upload(file);
      setDraft((current) => ({ ...current, [field]: url }));
    } catch (err) { setError(err instanceof Error ? err.message : "Falha ao enviar imagem."); }
    finally { setUploading(null); input.value = ""; }
  }

  async function save() {
    if (!canManage || saving || uploading || !dirty) return;
    setSaving(true); setError(""); setMessage("");
    try {
      const value = await platformBrandingApi.save(draft);
      setSaved(value); setDraft(value);
      try { await refreshSiteContent(); setMessage("Marca do gestor salva com sucesso."); }
      catch { setMessage("Marca salva. Recarregue a pagina para atualizar a exibicao."); }
    } catch (err) { setError(err instanceof Error ? err.message : "Falha ao salvar a marca do gestor."); }
    finally { setSaving(false); }
  }

  return <section className="space-y-4 rounded-2xl border border-surface-03 bg-surface-02 p-5" aria-labelledby="platform-branding-heading">
    <div><h2 id="platform-branding-heading" className="font-black text-cream">Marca do gestor</h2>
      <p className="mt-1 text-sm text-stone">Logo e favicon do gestor de empresas. As marcas das empresas continuam independentes.</p></div>
    {loading ? <p role="status" className="flex items-center gap-2 text-stone"><Loader2 size={16} className="animate-spin" /> Carregando marca...</p>
      : saved !== null ? <>
        <fieldset disabled={!canManage || saving || uploading !== null} className="grid gap-6 disabled:opacity-70 md:grid-cols-2">
          {([{ field: "logo_url", label: "Logo do gestor" }, { field: "favicon_url", label: "Favicon do gestor" }] as const).map(({ field, label }) => <div key={field} className="space-y-3">
            <label htmlFor={`platform-${field}`} className="block text-sm font-bold text-cream">{label}</label>
            <BrandingPreview url={draft[field]} label={label} />
            {canManage && <>
              <input id={`platform-${field}`} type="file" accept="image/png,image/jpeg,image/webp" className="block w-full text-sm text-stone file:mr-3 file:rounded-lg file:border-0 file:bg-surface-03 file:p-2 file:text-cream" onChange={(event) => void upload(field, event.currentTarget)} />
              {uploading === field && <p role="status" className="text-sm text-stone">Enviando imagem...</p>}
              {draft[field] && <Button type="button" variant="outline" size="sm" onClick={() => { setDraft((current) => ({ ...current, [field]: "" })); setMessage(""); }}>Remover imagem</Button>}
            </>}
          </div>)}
        </fieldset>
        <p className="text-xs text-stone">PNG, JPEG ou WebP, ate 5 MB. Favicon: prefira uma imagem quadrada. Sem imagem, sera usada a marca padrao Telz.</p>
        {canManage ? <div className="flex flex-wrap items-center gap-3"><Button type="button" onClick={() => void save()} disabled={!dirty || saving || uploading !== null}>{saving ? "Salvando..." : "Salvar marca do gestor"}</Button>{dirty && <p className="text-xs text-gold">Alteracoes ainda nao salvas.</p>}</div> : <p className="text-sm text-stone">Seu acesso permite apenas visualizar a marca do gestor.</p>}
      </> : null}
    {error && <div role="alert" className="space-y-2 text-sm text-red-300"><p>{error}</p>{!saved && !loading && <Button type="button" variant="outline" onClick={() => void load()}>Tentar novamente</Button>}</div>}
    {message && <p role="status" className="text-sm text-green-300">{message}</p>}
  </section>;
}
