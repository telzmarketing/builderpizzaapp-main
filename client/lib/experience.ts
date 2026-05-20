export type PublicExperience = "delivery" | "salao";

const SALAO_HOSTS = new Set(["moschettieri.com.br", "www.moschettieri.com.br"]);

export function getPublicExperience(hostname?: string): PublicExperience {
  const currentHost = (hostname ?? (typeof window !== "undefined" ? window.location.hostname : "")).toLowerCase();

  if (SALAO_HOSTS.has(currentHost)) return "salao";

  const isLocalHost = currentHost === "localhost" || currentHost === "127.0.0.1";
  const forcedExperience = import.meta.env.VITE_PUBLIC_EXPERIENCE;
  if (isLocalHost && forcedExperience === "salao") return "salao";

  return "delivery";
}

export function isSalaoExperience(hostname?: string) {
  return getPublicExperience(hostname) === "salao";
}
