export type CatalogBootstrapPlan = {
  products?: boolean;
  promotions?: boolean;
  multiFlavorsConfig?: boolean;
  campaignBanners?: boolean;
};

export function getStoreRefreshPlan(pathname: string): CatalogBootstrapPlan {
  return {
    products: pathname === "/" || pathname === "/cardapio" || pathname === "/menu" || pathname.startsWith("/product/"),
    campaignBanners: pathname === "/",
    multiFlavorsConfig: pathname.startsWith("/product/"),
  };
}

