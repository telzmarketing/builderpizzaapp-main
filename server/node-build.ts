import path from "node:path";
import { createServer } from "./index";
import * as express from "express";

const app = createServer();
const port = process.env.PORT || 3000;

// In production, serve the built SPA files
const __dirname = import.meta.dirname;
const distPath = path.join(__dirname, "../spa");

// Serve hashed assets with long cache, but keep HTML/PWA entry files fresh.
app.use(express.static(distPath, {
  maxAge: "1y",
  immutable: true,
  setHeaders(res, filePath) {
    const fileName = path.basename(filePath);
    if (
      fileName === "index.html" ||
      fileName === "registerSW.js" ||
      fileName === "sw.js" ||
      fileName === "manifest.webmanifest"
    ) {
      res.setHeader("Cache-Control", "no-cache");
    }
  },
}));

// Handle React Router - serve index.html for all non-API routes
app.get("/{*path}", (req, res) => {
  // Don't serve index.html for API routes
  if (req.path.startsWith("/api/") || req.path.startsWith("/health")) {
    return res.status(404).json({ error: "API endpoint not found" });
  }

  res.sendFile(path.join(distPath, "index.html"));
});

app.listen(port, () => {
  console.log(`🚀 Fusion Starter server running on port ${port}`);
  console.log(`📱 Frontend: http://localhost:${port}`);
  console.log(`🔧 API: http://localhost:${port}/api`);
});

// Graceful shutdown
process.on("SIGTERM", () => {
  console.log("🛑 Received SIGTERM, shutting down gracefully");
  process.exit(0);
});

process.on("SIGINT", () => {
  console.log("🛑 Received SIGINT, shutting down gracefully");
  process.exit(0);
});
