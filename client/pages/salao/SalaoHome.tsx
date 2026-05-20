import { useEffect } from "react";

const SALAO_SITE_URL = "/salao-site/index.html";

export default function SalaoHome() {
  useEffect(() => {
    document.title = "Moschettieri";
    document.documentElement.style.background = "#0b0b0b";
    document.body.style.margin = "0";
    document.body.style.background = "#0b0b0b";
  }, []);

  return (
    <iframe
      title="Moschettieri Salao"
      src={SALAO_SITE_URL}
      className="block h-screen min-h-screen w-full border-0 bg-black"
      loading="eager"
    />
  );
}
