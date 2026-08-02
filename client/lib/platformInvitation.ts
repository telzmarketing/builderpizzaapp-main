export function resolvePlatformInvitationToken(
  pathToken: string | undefined,
  searchToken: string | null,
): string {
  return (pathToken || searchToken || "").trim();
}

export function platformInvitationPasswordError(
  password: string,
  confirmation: string,
): string | null {
  if (!password && !confirmation) return null;
  if (password.length < 8) return "A senha precisa ter pelo menos 8 caracteres.";
  if (password.length > 72) return "A senha pode ter no maximo 72 caracteres.";
  if (password !== confirmation) return "A confirmacao nao corresponde a senha.";
  return null;
}
