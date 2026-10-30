(function () {
  var apps = [
    ["/app/kds/principal", "kds-principal", "KDS Principal"],
    ["/app/kds/pizzaiolo", "kds-pizzaiolo", "KDS Pizzaiolo"],
    ["/app/kds/preparo", "kds-preparo", "KDS Cozinha Preparo"],
    ["/app/kds/expedicao", "kds-expedicao", "KDS Expedição"],
    ["/app/kds/motoboys", "kds-motoboys", "KDS Motoboys"],
    ["/app/kds/pdv", "kds-pdv", "KDS PDV"],
    ["/app/kds/analitico", "kds-analitico", "KDS Analítico"],
  ];
  function appFor(path) {
    if (path === "/motoboy" || path.indexOf("/motoboy/") === 0) return ["motoboy", "Motoboy"];
    if (path === "/painel/bi-mobile" || path.indexOf("/painel/bi-mobile/") === 0) return ["bi-mobile", "BI Mobile"];
    for (var i = 0; i < apps.length; i += 1) {
      if (path === apps[i][0] || path.indexOf(apps[i][0] + "/") === 0) return [apps[i][1], apps[i][2]];
    }
    return null;
  }
  window.updateMotoboyPwaHead = function (pathname) {
    document.querySelectorAll("[data-telz-pwa]").forEach(function (node) { node.remove(); });
    var app = appFor(pathname);
    if (!app) return;
    function add(tag, attributes) {
      var node = document.createElement(tag);
      node.setAttribute("data-telz-pwa", "true");
      Object.keys(attributes).forEach(function (key) { node.setAttribute(key, attributes[key]); });
      document.head.appendChild(node);
    }
    add("link", { rel: "manifest", href: "/api/site-config/manifest.webmanifest?app=" + encodeURIComponent(app[0]) });
    add("link", { rel: "apple-touch-icon", sizes: "192x192", href: "/api/site-config/favicon?size=192" });
    add("meta", { name: "mobile-web-app-capable", content: "yes" });
    add("meta", { name: "apple-mobile-web-app-capable", content: "yes" });
    add("meta", { name: "apple-mobile-web-app-title", content: app[1] });
    add("meta", { name: "apple-mobile-web-app-status-bar-style", content: "black-translucent" });
  };
  if (window.location.pathname === "/motoboy") {
    window.location.replace("/motoboy/" + window.location.search + window.location.hash);
    return;
  }
  window.updateMotoboyPwaHead(window.location.pathname);
})();
