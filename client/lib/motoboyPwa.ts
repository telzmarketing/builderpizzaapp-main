export const MOTOBOY_SCOPE = "/motoboy/";
export const BI_MOBILE_SCOPE = "/painel/bi-mobile/";

export function isMotoboyPath(pathname: string) {
  return pathname === "/motoboy" || pathname.startsWith(MOTOBOY_SCOPE);
}

export function isBiMobilePath(pathname: string) {
  return pathname === "/painel/bi-mobile" || pathname.startsWith(BI_MOBILE_SCOPE);
}

export function isLegacyMotoboyWorker(registration: ServiceWorkerRegistration, origin: string) {
  const worker = registration.active || registration.waiting || registration.installing;
  return registration.scope === `${origin}/` && worker?.scriptURL === `${origin}/sw.js`;
}

async function retireLegacyWorker(registration: ServiceWorkerRegistration) {
  // Existing push subscriptions belong to their registration, not to the PWA id.
  const subscription = await registration.pushManager?.getSubscription();
  if (subscription) {
    // No subscription backend exists in this checkout. Preserve the old endpoint
    // instead of silently rebinding it to a new endpoint unknown to the sender.
    return;
  }
  await registration.unregister();
}

export async function configureMotoboyWorker(pathname: string, container: ServiceWorkerContainer, origin: string) {
  const registrations = await container.getRegistrations();
  const legacy = registrations.filter((registration) => isLegacyMotoboyWorker(registration, origin));
  if (!isMotoboyPath(pathname)) {
    await Promise.all(legacy.map(async (registration) => {
      await registration.update();
      await retireLegacyWorker(registration);
    }));
    return;
  }
  await container.register("/sw.js", { scope: MOTOBOY_SCOPE, updateViaCache: "none" });
  await Promise.all(legacy.map(async (registration) => {
    await registration.update();
    await retireLegacyWorker(registration);
  }));
}

export async function configureBiMobileWorker(pathname: string, container: ServiceWorkerContainer) {
  if (!isBiMobilePath(pathname)) return;
  await container.register("/sw.js", { scope: BI_MOBILE_SCOPE, updateViaCache: "none" });
}

export function syncMotoboyPwaHead(pathname: string) {
  (window as Window & { updateMotoboyPwaHead?: (path: string) => void }).updateMotoboyPwaHead?.(pathname);
}
