const LOCAL_DEV_ADMIN_PATHS = new Set([
  "/operacoes/print-pedido",
  "/operacoes/print-pedido/",
  "/painel/crm/agente-whatsapp",
  "/painel/crm/agente-whatsapp/",
]);

export function isLocalPrintOrderHomologationPath({
  dev,
  hostname,
  pathname,
}: {
  dev: boolean;
  hostname: string;
  pathname: string;
}): boolean {
  const normalizedHostname = hostname.trim().toLowerCase().replace(/\.+$/, "");

  return dev
    && (normalizedHostname === "localhost" || normalizedHostname === "127.0.0.1")
    && LOCAL_DEV_ADMIN_PATHS.has(pathname);
}
