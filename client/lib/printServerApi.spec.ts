import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { printServerApi } from "./api";

describe("printServerApi", () => {
  const storage: Storage = {
    clear: () => undefined,
    getItem: () => null,
    key: () => null,
    length: 0,
    removeItem: () => undefined,
    setItem: () => undefined,
  };

  beforeEach(() => {
    vi.stubGlobal("localStorage", storage);
    vi.stubGlobal("sessionStorage", storage);
  });

  afterEach(() => vi.restoreAllMocks());

  it("loads the tenant-scoped overview through the canonical API client", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      const data = url.includes("/overview")
        ? { stations: 1, printers: 1, pending_jobs: 0, processed_jobs: 0, failed_jobs: 0 }
        : [];
      return new Response(JSON.stringify({ data }), { status: 200, headers: { "content-type": "application/json" } });
    });

    const result = await printServerApi.overview();

    expect(result.summary.stations_online).toBe(0);
    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("/admin/print-center/overview"), expect.objectContaining({ method: "GET" }));
  });

  it("encodes resource ids for test and retry actions", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async () => new Response(JSON.stringify({ data: { accepted: true } }), { status: 200, headers: { "content-type": "application/json" } }));

    await printServerApi.testPrinter("printer/01");
    await printServerApi.retryJob("job/01");

    expect(fetchMock.mock.calls[0][0]).toContain("/admin/print-center/printers/printer%2F01/test");
    expect(fetchMock.mock.calls[1][0]).toContain("/admin/print-center/jobs/job%2F01/retry");
  });

  it("loads the Windows agent release metadata", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({
      data: { available: true, version: "1.0.0", file_name: "GranTorinoPrintService-Setup.exe", sha256: "abc123", size_bytes: 2048 },
    }), { status: 200, headers: { "content-type": "application/json" } }));

    const result = await printServerApi.agentRelease();

    expect(result.version).toBe("1.0.0");
    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("/admin/print-center/agent-release"), expect.objectContaining({ method: "GET" }));
  });

  it("downloads the installer and reads its filename from content disposition", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(new Blob(["installer"]), {
      status: 200,
      headers: { "content-type": "application/octet-stream", "content-disposition": "attachment; filename=GranTorinoPrintService-Setup.exe" },
    }));

    const result = await printServerApi.downloadAgentInstaller();

    expect(result.fileName).toBe("GranTorinoPrintService-Setup.exe");
    expect(await result.blob.text()).toBe("installer");
    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("/admin/print-center/agent-release/download"), expect.objectContaining({ method: "GET" }));
  });
});
