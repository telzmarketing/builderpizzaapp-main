import { type Plugin } from "vite";
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";
import path from "node:path";
import { createServer } from "./server";

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => ({
  test: {
    // Agent worktrees are nested inside this checkout and must never be
    // collected as part of the canonical repository test suite.
    exclude: ["**/node_modules/**", "**/dist/**", "**/.claude/**"],
  },
  server: {
    host: "::",
    port: 8080,
    fs: {
      allow: ["./client", "./shared", "index.html"],
      deny: [".env", ".env.*", "*.{crt,pem}", "**/.git/**", "server/**"],
    },
  },
  build: {
    outDir: "dist/spa",
  },
  plugins: [
    react(),
    expressPlugin(),
    VitePWA({
      strategies: "injectManifest",
      srcDir: "client",
      filename: "sw.ts",
      registerType: "autoUpdate",
      injectRegister: false,
      includeManifestIcons: true,
      includeAssets: [
        "icons/telz.svg",
        "icons/store-default.svg",
        "icons/icon-192.png",
        "icons/icon-512.png",
      ],
      // The tenant manifest is linked only by the Motoboy route bootstrap.
      manifest: false,
      injectManifest: {
        // Manifest association is route-owned; Vite must not inject it globally.
        injectionPoint: "self.__WB_MANIFEST",
        globPatterns: ["index.html", "motoboy-pwa-head.js", "assets/index-*.js", "assets/index-*.css", "assets/Motoboy-*.js", "assets/Bi*.js", "assets/*.woff2", "icons/*.{png,svg,ico}"],
        globIgnores: [
          "favicon.ico",
          "icons/favicon-moschettieri-32.png",
          "salao-site/**",
          "salao/**",
          // O PWA offline é do Motoboy. Chunks administrativos continuam
          // carregando sob demanda pela rede, sem competir no precache inicial.
          "assets/Admin*.js",
          "assets/Aparencia-*.js",
          "assets/ClienteDetalhe-*.js",
          "assets/Conteudo-*.js",
          "assets/Cozinha-*.js",
          "assets/Crm*.js",
          "assets/Dashboard*.js",
          "assets/HomeConfig-*.js",
          "assets/leaflet-src-*.js",
          "assets/Logistica*.js",
          "assets/Marketing*.js",
          "assets/Orders-*.js",
          "assets/PaidTraffic-*.js",
          "assets/Products-*.js",
          "assets/StoreOperation-*.js",
          "assets/ChatbotAutomations-*.js",
          "assets/ChatbotConfig-*.js",
          "assets/ChatbotConversations-*.js",
          "assets/ChatbotDashboard-*.js",
          "assets/ChatbotFAQ-*.js",
          "assets/ChatbotReports-*.js",
        ],
        maximumFileSizeToCacheInBytes: 3 * 1024 * 1024,
      },
    }),
  ],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./client"),
      "@shared": path.resolve(__dirname, "./shared"),
    },
  },
}));

function expressPlugin(): Plugin {
  return {
    name: "express-plugin",
    apply: "serve", // Only apply during development (serve mode)
    configureServer(server) {
      const app = createServer();

      // Add Express app as middleware to Vite dev server
      server.middlewares.use(app);
    },
  };
}
