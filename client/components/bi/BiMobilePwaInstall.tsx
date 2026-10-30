import PwaInstallButton from "@/components/PwaInstallButton";

/** Progressive enhancement: uses the browser's existing PWA install flow. */
export default function BiMobilePwaInstall() {
  return <PwaInstallButton only={["bi-mobile"]} />;
}
