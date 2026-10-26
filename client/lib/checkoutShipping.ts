/** A cancelled address quote can never restore data for the previous address. */
export function scheduleShippingQuote<T>(calculate: () => Promise<T>, callbacks: { result: (value: T | null) => void; loading: (value: boolean) => void; error: (value: string) => void }, delay = 600): () => void {
  let active = true;
  callbacks.result(null);
  callbacks.error("");
  callbacks.loading(true);
  const timer = setTimeout(async () => {
    try {
      const result = await calculate();
      if (active) callbacks.result(result);
    } catch (error) {
      if (active) callbacks.error(error instanceof Error ? error.message : "Não foi possível calcular o frete. Confira o endereço e tente novamente.");
    } finally { if (active) callbacks.loading(false); }
  }, delay);
  return () => { active = false; clearTimeout(timer); };
}
