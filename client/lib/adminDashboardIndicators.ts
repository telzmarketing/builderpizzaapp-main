export type DashboardRevenueRow = { day: string; revenue: number };

export function hasDashboardRevenueData(rows: DashboardRevenueRow[]): boolean {
  return rows.length > 0;
}

export function dashboardRevenueData(rows: DashboardRevenueRow[]) {
  if (!hasDashboardRevenueData(rows)) return [];
  const revenueByDay = new Map(rows.map((row) => [row.day, row.revenue]));
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return Array.from({ length: 7 }, (_, index) => {
    const date = new Date(today);
    date.setDate(today.getDate() - (6 - index));
    const key = date.toISOString().slice(0, 10);
    return {
      name: date.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" }),
      receita: revenueByDay.get(key) ?? 0,
    };
  });
}
