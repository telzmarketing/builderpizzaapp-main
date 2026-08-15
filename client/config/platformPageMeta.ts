export type PlatformPageMeta = {
  eyebrow: string;
  title: string;
  subtitle: string;
};

const platformPageMeta: Array<{
  match: (pathname: string) => boolean;
  meta: PlatformPageMeta;
}> = [
  {
    match: (pathname) => pathname === "/painel/plataforma",
    meta: {
      eyebrow: "Plataforma",
      title: "Visao geral",
      subtitle: "Indicadores e alertas reais da operacao SaaS.",
    },
  },
  {
    match: (pathname) => /^\/painel\/empresas\/[^/]+$/.test(pathname),
    meta: {
      eyebrow: "Plataforma / Empresas",
      title: "Detalhes da empresa",
      subtitle: "Cadastro, acesso, licenca, modulos, dominios e historico.",
    },
  },
  {
    match: (pathname) => pathname === "/painel/empresas",
    meta: {
      eyebrow: "Plataforma",
      title: "Empresas",
      subtitle: "Gestao centralizada das empresas da plataforma.",
    },
  },
  {
    match: (pathname) => pathname === "/painel/planos",
    meta: {
      eyebrow: "Plataforma",
      title: "Planos",
      subtitle: "Catalogo comercial e limites disponiveis para contratacao.",
    },
  },
  {
    match: (pathname) => pathname === "/painel/modulos",
    meta: {
      eyebrow: "Plataforma",
      title: "Modulos",
      subtitle: "Recursos que podem ser contratados e habilitados por empresa.",
    },
  },
  {
    match: (pathname) => pathname === "/painel/cobrancas",
    meta: {
      eyebrow: "Plataforma",
      title: "Cobrancas",
      subtitle: "Empresas por situacao financeira e acesso ao historico de faturas.",
    },
  },
  {
    match: (pathname) => pathname === "/painel/dominios",
    meta: {
      eyebrow: "Plataforma",
      title: "Dominios",
      subtitle: "Verificacao e ativacao dos enderecos das empresas.",
    },
  },
  {
    match: (pathname) => pathname === "/painel/usuarios-plataforma",
    meta: {
      eyebrow: "Plataforma",
      title: "Usuarios da plataforma",
      subtitle: "Consulta dos operadores com acesso administrativo a Central Master.",
    },
  },
  {
    match: (pathname) => pathname === "/painel/configuracoes-plataforma",
    meta: {
      eyebrow: "Plataforma",
      title: "Configuracoes",
      subtitle: "Postura operacional, seguranca e rollout do ambiente da plataforma.",
    },
  },
  {
    match: (pathname) => pathname === "/painel/suporte",
    meta: {
      eyebrow: "Plataforma",
      title: "Suporte",
      subtitle: "Acesso temporario, escopado e auditado ao painel de uma empresa.",
    },
  },
  {
    match: (pathname) => pathname === "/painel/auditoria",
    meta: {
      eyebrow: "Plataforma",
      title: "Auditoria",
      subtitle: "Registro imutavel das acoes administrativas da plataforma.",
    },
  },
  {
    match: (pathname) => pathname === "/painel/saude-servicos",
    meta: {
      eyebrow: "Monitoramento",
      title: "Saude dos servicos",
      subtitle: "Disponibilidade, latencia e alertas dos componentes centrais.",
    },
  },
  {
    match: (pathname) => pathname === "/painel/integracoes-plataforma",
    meta: {
      eyebrow: "Monitoramento",
      title: "Integracoes",
      subtitle: "Conectividade redigida dos provedores usados pelas empresas.",
    },
  },
  {
    match: (pathname) => pathname === "/painel/filas-jobs",
    meta: {
      eyebrow: "Monitoramento",
      title: "Filas e jobs",
      subtitle: "Execucao assincrona, filas pendentes e saude dos workers.",
    },
  },
  {
    match: (pathname) => pathname === "/painel/whatsapp-gateway-plataforma",
    meta: {
      eyebrow: "Monitoramento",
      title: "WhatsApp Gateway",
      subtitle: "Runtime e instancias do gateway sem expor credenciais ou numeros completos.",
    },
  },
  {
    match: (pathname) => pathname === "/painel/erros-plataforma",
    meta: {
      eyebrow: "Monitoramento",
      title: "Erros",
      subtitle: "Ocorrencias operacionais redigidas, agrupadas e rastreaveis.",
    },
  },
  {
    match: (pathname) => pathname === "/painel/armazenamento-plataforma",
    meta: {
      eyebrow: "Monitoramento",
      title: "Armazenamento",
      subtitle: "Uso de disco e consumo atribuido por empresa.",
    },
  },
  {
    match: (pathname) => pathname === "/painel/backups-plataforma",
    meta: {
      eyebrow: "Monitoramento",
      title: "Backups",
      subtitle: "Execucoes, validacao dos componentes e prontidao de restauracao.",
    },
  },
];

export function getPlatformPageMeta(pathname: string): PlatformPageMeta {
  return platformPageMeta.find((entry) => entry.match(pathname))?.meta ?? {
    eyebrow: "Plataforma",
    title: "Administracao Master",
    subtitle: "Central de operacao SaaS.",
  };
}
