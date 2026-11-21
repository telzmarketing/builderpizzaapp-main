import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { checkSilentPrintAgent, detectSilentPrintTransport, enqueueSilentPrint, getSilentPrintHistory, loadSilentPrintAgentConfig, saveSilentPrintAgentConfig, SilentPrintError } from "./silentPrinting";

function storage() {
  const values = new Map<string, string>();
  return { getItem: (key: string) => values.get(key) ?? null, setItem: (key: string, value: string) => values.set(key, value), removeItem: (key: string) => values.delete(key) };
}

const job = (key = "job-1") => ({ documentId: "order-1", documentType: "receipt" as const, content: { kind: "html" as const, data: "<main>pedido</main>" }, printerId: "receipt-printer", idempotencyKey: key });

describe("silent printing client bridge", () => {
  beforeEach(() => {
    vi.stubGlobal("localStorage", storage());
    vi.stubGlobal("window", { qz: undefined });
    saveSilentPrintAgentConfig({ transport: "local_agent", baseUrl: "http://127.0.0.1:18181", requestTimeoutMs: 500 });
  });
  afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

  it("normalizes the configured agent and detects local transport", () => {
    saveSilentPrintAgentConfig({ baseUrl: "http://127.0.0.1:18181/", requestTimeoutMs: 1 });
    expect(loadSilentPrintAgentConfig()).toMatchObject({ baseUrl: "http://127.0.0.1:18181", requestTimeoutMs: 500 });
    expect(detectSilentPrintTransport()).toBe("local_agent");
  });

  it("sends HTML directly to the local agent and records confirmation", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ job_id: "agent-1", status: "confirmed", agent_version: "1.0" }), { status: 200, headers: { "Content-Type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);
    await expect(enqueueSilentPrint(job())).resolves.toMatchObject({ jobId: "agent-1", status: "confirmed", transport: "local_agent" });
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://127.0.0.1:18181/v1/print");
    expect(new Headers(init.headers).get("Idempotency-Key")).toBe("job-1");
    expect(JSON.parse(String(init.body))).toMatchObject({ content: { kind: "html", data: "<main>pedido</main>" }, printer_id: "receipt-printer" });
    expect(getSilentPrintHistory()[0]).toMatchObject({ jobId: "agent-1", status: "confirmed" });
  });

  it("coalesces repeated clicks while a job is in flight", async () => {
    let resolve: (value: Response) => void = () => undefined;
    const pending = new Promise<Response>((done) => { resolve = done; });
    const fetchMock = vi.fn().mockReturnValue(pending);
    vi.stubGlobal("fetch", fetchMock);
    const first = enqueueSilentPrint(job("same")); const second = enqueueSilentPrint(job("same"));
    expect(first).toBe(second); resolve(new Response(JSON.stringify({ job_id: "same", status: "sent" }), { status: 200 }));
    await expect(first).resolves.toMatchObject({ status: "sent" });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("returns an explicit unavailable error without browser-print APIs", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("connection refused")));
    await expect(enqueueSilentPrint(job("offline"))).rejects.toMatchObject({ code: "AGENT_UNAVAILABLE" });
    expect((window as Window & { print?: unknown }).print).toBeUndefined();
  });

  it("maps health detection without sending a print job", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response("{}", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    await expect(checkSilentPrintAgent()).resolves.toMatchObject({ available: true, transport: "local_agent" });
    expect(fetchMock).toHaveBeenCalledWith("http://127.0.0.1:18181/v1/health", expect.anything());
  });

  it("supports QZ Tray detection as an authorized installed transport", () => {
    vi.stubGlobal("window", { qz: { websocket: { connect: vi.fn() }, configs: { create: vi.fn() }, print: vi.fn() } });
    expect(detectSilentPrintTransport({ ...loadSilentPrintAgentConfig(), transport: "auto" })).toBe("qz");
    expect(detectSilentPrintTransport({ ...loadSilentPrintAgentConfig(), transport: "qz" })).toBe("qz");
  });

  it("preserves the QZ connection failure and points to browser local access permission", async () => {
    const connect = vi.fn().mockRejectedValue(new Error("Unable to establish connection with QZ Tray"));
    vi.stubGlobal("window", { qz: { websocket: { isActive: () => false, connect } } });
    saveSilentPrintAgentConfig({ transport: "qz" });
    const result = enqueueSilentPrint(job("qz-lna"));
    await expect(result).rejects.toMatchObject({
      code: "AGENT_UNAVAILABLE",
      message: expect.stringContaining("Unable to establish connection with QZ Tray"),
    });
    await expect(result).rejects.toThrow("Apps on this device");
    expect(connect).toHaveBeenCalledOnce();
  });

  it("keeps the QZ diagnostic when both automatic transports fail", async () => {
    vi.stubGlobal("window", { qz: { websocket: { isActive: () => false, connect: vi.fn().mockRejectedValue(new Error("Unable to establish connection with QZ Tray")) } } });
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("connection refused")));
    saveSilentPrintAgentConfig({ transport: "auto" });
    const result = enqueueSilentPrint(job("both-offline"));
    await expect(result).rejects.toMatchObject({ code: "AGENT_UNAVAILABLE" });
    await expect(result).rejects.toThrow("Local print agent unavailable");
    await expect(result).rejects.toThrow("Apps on this device");
    expect(getSilentPrintHistory()[0].message).toContain("Apps on this device");
  });

  it("uses the local agent when automatic QZ connection fails", async () => {
    vi.stubGlobal("window", { qz: { websocket: { isActive: () => false, connect: vi.fn().mockRejectedValue(new Error("Unable to establish connection with QZ Tray")) } } });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ job_id: "fallback-1", status: "confirmed" }), { status: 200 })));
    saveSilentPrintAgentConfig({ transport: "auto" });
    await expect(enqueueSilentPrint(job("fallback-1"))).resolves.toMatchObject({ jobId: "fallback-1", status: "confirmed", transport: "local_agent" });
  });

  it("rejects an invalid job before contacting the agent", async () => {
    await expect(enqueueSilentPrint({ ...job(), content: { kind: "raw", data: "" } })).rejects.toBeInstanceOf(SilentPrintError);
  });
});
