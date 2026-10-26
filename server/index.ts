import "dotenv/config";
import express from "express";
import cors from "cors";
import { handleDemo } from "./routes/demo";

export function createServer() {
  const app = express();

  // Middleware
  app.use(cors());
  app.use(express.json());
  app.use(express.urlencoded({ extended: true }));

  // Browsers may request this independently of the document's explicit icons.
  app.get("/favicon.ico", (_req, res) => {
    res.setHeader("Cache-Control", "no-store");
    res.redirect(307, "/api/site-config/favicon?size=32");
  });

  // Preserve the manifest URL used by already installed Motoboy applications.
  app.get("/manifest.webmanifest", (_req, res) => {
    res.setHeader("Cache-Control", "no-store");
    res.redirect(307, "/api/site-config/manifest.webmanifest");
  });

  // Example API routes
  app.get("/api/ping", (_req, res) => {
    const ping = process.env.PING_MESSAGE ?? "ping";
    res.json({ message: ping });
  });

  app.get("/api/demo", handleDemo);

  return app;
}
