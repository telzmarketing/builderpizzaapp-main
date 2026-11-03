import { Camera, Check, Clock3, Loader2, ShieldAlert } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { productionVisionApi } from "@/lib/productionVision";
import { defaultProductionCaptureRule, getProductionCaptureBridge, normalizeProductionCaptureState, PRODUCTION_CAPTURE_CHECKLIST, readProductionCaptureRules, type ProductionCaptureRule, type ProductionCaptureState, type ProductionCaptureStepId } from "@/lib/productionVisionCapture";

type Props = { productionUnitId: string; stationId: string; rule?: ProductionCaptureRule; triggerStep?: ProductionCaptureStepId | null };
const stateText: Record<ProductionCaptureState, string> = { not_started: "Aguardando", countdown: "Contagem regressiva", pending: "Registrando", ok: "OK", unsupported: "Indisponível", error: "Erro" };

export default function ProductionCaptureChecklist({ productionUnitId, stationId, rule: suppliedRule, triggerStep }: Props) {
  const defaultRule = useMemo(() => readProductionCaptureRules()[stationId] ?? defaultProductionCaptureRule(stationId), [stationId]);
  const rule = suppliedRule ?? defaultRule;
  const [states, setStates] = useState<Record<string, ProductionCaptureState>>({});
  const [countdown, setCountdown] = useState<number | null>(null);
  const [scheduledStep, setScheduledStep] = useState<string | null>(null);
  const [running, setRunning] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [loadedRule, setLoadedRule] = useState<ProductionCaptureRule | null>(null);
  const nextStep = PRODUCTION_CAPTURE_CHECKLIST.find((step) => states[step.id] !== "ok");
  const activeRule = loadedRule ?? rule;

  useEffect(() => {
    let active = true;
    void productionVisionApi.getCaptureConfig(stationId).then((config) => { if (active) setLoadedRule({ stationId, enabled: config.enabled, automatic: true, delaySeconds: config.milestone_1_seconds, milestoneSeconds: [config.milestone_1_seconds, config.milestone_2_seconds, config.milestone_3_seconds] }); }).catch(() => undefined);
    void productionVisionApi.createSession({ production_unit_id: productionUnitId, stage: "production_capture", station_id: stationId, idempotency_key: `production-capture:${productionUnitId}:${stationId}`, expected_photo_count: 3 }).then((session) => { if (active) setSessionId(session.id); }).catch(() => undefined);
    return () => { active = false; };
  }, [productionUnitId, stationId]);

  const attempt = async (stepId: string, automatic = false) => {
    const step = PRODUCTION_CAPTURE_CHECKLIST.find((candidate) => candidate.id === stepId);
    if (!step || running || states[step.id] === "ok") return;
    setRunning(step.id); setCountdown(null); setMessage(null); setStates((current) => ({ ...current, [step.id]: "pending" }));
    const bridge = getProductionCaptureBridge();
    if (!bridge) { setStates((current) => ({ ...current, [step.id]: "unsupported" })); setMessage("Captura física indisponível: nenhum agente autorizado foi conectado."); setRunning(null); return; }
    try {
      const result = await bridge.capture({ productionUnitId, stationId, stepId: step.id, stage: step.stage });
      const transportState = normalizeProductionCaptureState(result.status);
      if (transportState === "unsupported") { setStates((current) => ({ ...current, [step.id]: "unsupported" })); setMessage("O transporte de captura não suporta esta operação."); return; }
      if (!result.original_storage_key) { setStates((current) => ({ ...current, [step.id]: transportState })); setMessage(automatic ? "Captura automática aceita e aguardando processamento." : "Captura aceita e aguardando processamento."); return; }
      const activeSessionId = sessionId ?? (await productionVisionApi.createSession({ production_unit_id: productionUnitId, stage: "production_capture", station_id: stationId, idempotency_key: `production-capture:${productionUnitId}:${stationId}`, expected_photo_count: 3 })).id;
      if (!sessionId) setSessionId(activeSessionId);
      const photo = await productionVisionApi.addPhoto(activeSessionId, { original_storage_key: result.original_storage_key, processing_status: "captured" });
      await productionVisionApi.captureEvent(activeSessionId, { milestone: step.id === "start" ? "milestone_1" : step.id === "pizza_ready" ? "milestone_2" : "milestone_3", idempotency_key: `${activeSessionId}:${step.id}`, mode: automatic ? "automatic" : "manual" });
      const photoPayload = photo as { status?: unknown; processing_status?: unknown };
      const finalState = normalizeProductionCaptureState(photoPayload.status ?? photoPayload.processing_status ?? "captured");
      setStates((current) => ({ ...current, [step.id]: finalState })); setMessage(finalState === "ok" ? "Foto registrada." : "Foto registrada, aguardando confirmação.");
    } catch (cause) { setStates((current) => ({ ...current, [step.id]: "error" })); setMessage(cause instanceof Error ? cause.message : "Não foi possível registrar a captura."); } finally { setRunning(null); }
  };

  useEffect(() => { if (triggerStep && states[triggerStep] !== "ok") void attempt(triggerStep); }, [triggerStep]);
  useEffect(() => {
    if (!activeRule.enabled || !activeRule.automatic || !nextStep || states[nextStep.id] === "unsupported" || scheduledStep === nextStep.id) return;
    const index = PRODUCTION_CAPTURE_CHECKLIST.findIndex((step) => step.id === nextStep.id);
    const seconds = activeRule.milestoneSeconds?.[index] ?? activeRule.delaySeconds;
    if (seconds <= 0) return;
    setScheduledStep(nextStep.id); let remaining = Math.max(1, seconds); setCountdown(remaining);
    const timer = window.setInterval(() => { remaining -= 1; setCountdown(remaining > 0 ? remaining : null); if (remaining <= 0) { window.clearInterval(timer); void attempt(nextStep.id, true); } }, 1000);
    return () => window.clearInterval(timer);
  }, [activeRule, nextStep, scheduledStep, states]);

  return <section aria-label="Checklist de captura" className="space-y-2 rounded-lg border border-surface-03 bg-surface-01 p-2">
    <div className="flex items-center justify-between gap-2"><h4 className="text-sm font-black">Fotos <span className="font-normal text-stone">(sem exibir imagem)</span></h4><span className="text-xs font-bold text-stone">{PRODUCTION_CAPTURE_CHECKLIST.filter((step) => states[step.id] === "ok").length}/3 OK</span></div>
    <div className="grid grid-cols-3 gap-1.5">{PRODUCTION_CAPTURE_CHECKLIST.map((step) => { const state = states[step.id] ?? "not_started"; const isRunning = running === step.id; const stepCountdown = nextStep?.id === step.id ? countdown : null; return <button key={step.id} type="button" disabled={state === "ok" || Boolean(running)} onClick={() => void attempt(step.id)} className={`min-h-12 rounded-md border px-1.5 py-1 text-left text-[11px] font-bold transition ${state === "ok" ? "border-emerald-500/50 bg-emerald-500/10 text-emerald-200" : state === "unsupported" ? "border-amber-500/50 bg-amber-500/10 text-amber-200" : "border-surface-03 bg-surface-02 text-cream hover:border-gold"}`}><span className="flex items-center gap-1">{state === "ok" ? <Check size={13} /> : isRunning ? <Loader2 size={13} className="animate-spin" /> : state === "unsupported" ? <ShieldAlert size={13} /> : <Camera size={13} />}<span className="truncate">{step.label}</span></span><span className="mt-0.5 block text-[10px] font-normal opacity-80">{state === "ok" ? "OK — registrada" : isRunning ? "Registrando..." : stepCountdown !== null ? `${stepCountdown}s` : stateText[state]}</span></button>; })}</div>
    {countdown !== null && nextStep && <p className="flex items-center gap-1 text-[11px] text-amber-200"><Clock3 size={13} />{nextStep.label} será tirada automaticamente em {countdown}s.</p>}
    {message && <p role="status" className="text-[11px] text-amber-100">{message}</p>}
  </section>;
}
