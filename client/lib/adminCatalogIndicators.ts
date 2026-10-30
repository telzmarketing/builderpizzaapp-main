export function displayCatalogCount(count: number, ready: boolean): string | null {
  if (!ready || count <= 0) return null;
  return count.toLocaleString("pt-BR");
}

export function catalogProductsSummary(count: number, ready: boolean): string {
  if (!ready) return "Carregando produtos...";
  if (count <= 0) return "Nenhum produto nesta visualizacao";
  return `${count} produto${count === 1 ? "" : "s"} nesta visualizacao`;
}
