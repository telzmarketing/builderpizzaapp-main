import "./global.css";
// KDS/PWA surfaces can run outside AdminLayout (standalone installed apps),
// so their scoped responsive and install-control styles must load globally.
import "./admin.css";
import { createRoot } from "react-dom/client";
import App from "./App";

createRoot(document.getElementById("root")!).render(<App />);
