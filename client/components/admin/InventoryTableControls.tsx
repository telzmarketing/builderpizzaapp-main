import type { ReactNode } from "react";

export function filterAndSort<T, K extends string>(rows: T[], search: string, sort: K, fields: Record<K, (row: T) => string | number>) {
  const needle = search.trim().toLocaleLowerCase("pt-BR");
  return rows
    .filter((row) => !needle || Object.values(fields).some((read) => String(read(row)).toLocaleLowerCase("pt-BR").includes(needle)))
    .slice()
    .sort((left, right) => {
      const a = fields[sort](left);
      const b = fields[sort](right);
      if (typeof a === "number" && typeof b === "number") return a - b;
      return String(a).localeCompare(String(b), "pt-BR", { numeric: true, sensitivity: "base" });
    });
}

export function InventoryTableControls({ search, onSearch, sort, onSort, options, children }: { search: string; onSearch: (value: string) => void; sort: string; onSort: (value: string) => void; options: Array<{ value: string; label: string }>; children?: ReactNode }) {
  return (
    <div className="flex flex-col gap-2 border-b border-surface-03 bg-surface-01 p-3 sm:flex-row sm:items-center sm:justify-between">
      <label className="flex min-w-0 flex-1 items-center gap-2 text-xs font-bold text-stone">
        <span className="sr-only">Buscar na tabela</span>
        <input className="w-full rounded-lg border border-surface-03 bg-surface-01 px-3 py-2 text-sm text-cream outline-none transition placeholder:text-stone/70 focus:border-gold" value={search} onChange={(event) => onSearch(event.target.value)} placeholder="Buscar insumo, item ou fornecedor..." aria-label="Buscar na tabela" />
      </label>
      <div className="flex items-center gap-2">
        {children}
        <label className="flex items-center gap-2 text-xs font-bold text-stone">
          <span>Ordenar por</span>
          <select className="w-auto min-w-40 rounded-lg border border-surface-03 bg-surface-01 px-3 py-2 text-sm text-cream outline-none focus:border-gold" value={sort} onChange={(event) => onSort(event.target.value)} aria-label="Ordenar tabela">
            {options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
          </select>
        </label>
      </div>
    </div>
  );
}
