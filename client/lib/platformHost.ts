export const DEFAULT_PLATFORM_HOSTNAME = "erp.telz.com.br";

export function parsePlatformHostnames(
  value: unknown = import.meta.env.VITE_PLATFORM_HOSTNAMES
    ?? import.meta.env.VITE_PLATFORM_HOSTNAME
    ?? DEFAULT_PLATFORM_HOSTNAME,
): Set<string> {
  const hosts = String(value)
    .split(",")
    .map((hostname) => hostname.trim().toLowerCase().replace(/\.$/, ""))
    .filter(Boolean);
  if (import.meta.env.DEV) hosts.push("localhost", "127.0.0.1");
  return new Set(hosts);
}

export function isPlatformHostname(
  hostname: string,
  platformHostnames = parsePlatformHostnames(),
): boolean {
  return platformHostnames.has(hostname.trim().toLowerCase().replace(/\.$/, ""));
}

export function adminLandingPath(hostname: string): string {
  return isPlatformHostname(hostname) ? "/painel/empresas" : "/painel";
}
