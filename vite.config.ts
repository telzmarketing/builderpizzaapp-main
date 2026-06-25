import { defineConfig, Plugin } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";
import path from "node:path";
import { createServer } from "./server";

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => ({
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
      injectRegister: "script-defer",
      includeManifestIcons: true,
      includeAssets: [
        "favicon.ico",
        "icons/favicon-moschettieri-32.png",
        "icons/icon-192.png",
        "icons/icon-512.png",
      ],
      manifest: {
        name: "Motoboy Delivery",
        short_name: "Motoboy",
        description: "Painel do entregador",
        start_url: "/motoboy",
        scope: "/motoboy",
        display: "standalone",
        display_override: ["fullscreen", "standalone"],
        orientation: "portrait",
        theme_color: "#000000",
        background_color: "#000000",
        icons: [
          {
            src: "/api/site-config/favicon?size=192",
            sizes: "192x192",
            purpose: "any maskable",
          },
          {
            src: "/api/site-config/favicon?size=512",
            sizes: "512x512",
            purpose: "any maskable",
          },
        ],
      },
      injectManifest: {
        globPatterns: ["**/*.{js,css,html,ico,png,svg,webmanifest}"],
        globIgnores: [
          "salao-site/**",
          "salao/**",
          // O PWA offline é do Motoboy. Chunks administrativos continuam
          // carregando sob demanda pela rede, sem competir no precache inicial.
          "assets/Admin*.js",
          "assets/Aparencia-*.js",
          "assets/Bi*.js",
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
