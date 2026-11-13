import { describe, expect, it } from "vitest";
import { getAdminPageMeta } from "./adminPageMeta";

describe("AdminConfiguracoes route metadata", () => {
  it.each([
    ["/painel/comprovantes-pedidos", "Comprovantes de pedidos"],
    ["/painel/etiquetas-expedicao", "Etiquetas de expedição"],
    ["/painel/etiquetas-insumos", "Etiquetas de insumos"],
    ["/painel/dominio", "Domínio"],
    ["/painel/painel-tv-config", "Painel de TV"],
    ["/painel/som", "Som"],
    ["/painel/identificacao-parceiros", "Identificação de parceiros"],
    ["/painel/configuracoes/ia-central", "IA central"],
  ])("keeps dedicated metadata for %s", (pathname, title) => {
    expect(getAdminPageMeta(pathname)).toMatchObject({ eyebrow: "Configuracoes", title });
  });
});
