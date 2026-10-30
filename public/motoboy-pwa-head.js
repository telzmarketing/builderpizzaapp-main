(function () {
  function isMotoboy(path) {
    return path === "/motoboy" || path.indexOf("/motoboy/") === 0;
  }
  function isBiMobile(path) {
    return path === "/painel/bi-mobile" || path.indexOf("/painel/bi-mobile/") === 0;
  }
  window.updateMotoboyPwaHead = function (pathname) {
    document.querySelectorAll("[data-motoboy-pwa]").forEach(function (node) { node.remove(); });
    if (!isMotoboy(pathname) && !isBiMobile(pathname)) return;
    function add(tag, attributes) {
      var node = document.createElement(tag);
      node.setAttribute("data-motoboy-pwa", "true");
      Object.keys(attributes).forEach(function (key) { node.setAttribute(key, attributes[key]); });
      document.head.appendChild(node);
    }
    add("link", { rel: "manifest", href: isBiMobile(pathname) ? "/api/site-config/manifest.webmanifest?app=bi-mobile" : "/api/site-config/manifest.webmanifest" });
    add("link", { rel: "apple-touch-icon", sizes: "192x192", href: "/api/site-config/favicon?size=192" });
    add("meta", { name: "mobile-web-app-capable", content: "yes" });
    add("meta", { name: "apple-mobile-web-app-capable", content: "yes" });
    add("meta", { name: "apple-mobile-web-app-title", content: isBiMobile(pathname) ? "BI Mobile" : "Motoboy" });
    add("meta", { name: "apple-mobile-web-app-status-bar-style", content: "black-translucent" });
  };
  // Preserve old installed entry URLs and query/hash before the SPA starts.
  if (window.location.pathname === "/motoboy") {
    window.location.replace("/motoboy/" + window.location.search + window.location.hash);
    return;
  }
  window.updateMotoboyPwaHead(window.location.pathname);
})();
