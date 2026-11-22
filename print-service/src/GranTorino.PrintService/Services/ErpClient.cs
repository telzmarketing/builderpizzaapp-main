using System.Net.Http.Json;
using System.Net.Http.Headers;
using GranTorino.PrintService.Configuration;
using GranTorino.PrintService.Contracts;
using GranTorino.PrintService.Data;

namespace GranTorino.PrintService.Services;

public sealed class ErpClient
{
    private readonly HttpClient _http; private readonly AgentOptions _options; private readonly PrintDb _db; private readonly IPrinterService _printers; private AgentState State => new() { AccessToken = _db.GetState("access_token"), DeviceId = _db.GetState("device_id") ?? Environment.MachineName, StationId = _db.GetState("station_id") ?? _options.StationId };
    public ErpClient(HttpClient http, AgentOptions options, PrintDb db, IPrinterService printers) { _http = http; _options = options; _db = db; _printers = printers; }
    public bool IsPaired => !string.IsNullOrWhiteSpace(_db.GetState("access_token"));
    private void Auth() { _http.DefaultRequestHeaders.Authorization = string.IsNullOrWhiteSpace(State.AccessToken) ? null : new AuthenticationHeaderValue("Bearer", State.AccessToken); }
    public async Task PairAsync(CancellationToken ct)
    {
        if (string.IsNullOrWhiteSpace(_options.PairingCode)) return;
        var request = new PairRequest(_options.PairingCode, Environment.MachineName, "1.0.0");
        using var response = await _http.PostAsJsonAsync("/api/print-agent/v1/pair", request, ct); response.EnsureSuccessStatusCode();
        var envelope = await response.Content.ReadFromJsonAsync<ApiEnvelope<PairData>>(cancellationToken: ct) ?? throw new InvalidOperationException("Resposta de pareamento inválida.");
        var result = envelope.Data ?? throw new InvalidOperationException("Pareamento sem credencial.");
        _db.SetState("access_token", result.AccessToken); if (!string.IsNullOrWhiteSpace(result.StationId)) _db.SetState("station_id", result.StationId!); _db.SetState("device_id", State.DeviceId);
    }
    public async Task<PrintJob?> NextJobAsync(CancellationToken ct) { Auth(); using var response = await _http.GetAsync("/api/print-agent/v1/jobs/next", ct); response.EnsureSuccessStatusCode(); var envelope = await response.Content.ReadFromJsonAsync<ApiEnvelope<JobEnvelope>>(cancellationToken: ct); return envelope?.Data?.Job; }
    public async Task UpdateStatusAsync(string id, JobStatusRequest status, CancellationToken ct) { Auth(); using var request = new HttpRequestMessage(HttpMethod.Post, $"/api/print-agent/v1/jobs/{Uri.EscapeDataString(id)}/status") { Content = JsonContent.Create(status) }; using var response = await _http.SendAsync(request, ct); response.EnsureSuccessStatusCode(); }
    public async Task HeartbeatAsync(CancellationToken ct) { Auth(); var request = new HeartbeatRequest(Environment.MachineName, "1.0.0", _printers.Enumerate().Select(name => new HeartbeatPrinter(name, "ready")).ToArray()); using var response = await _http.PostAsJsonAsync("/api/print-agent/v1/heartbeat", request, ct); response.EnsureSuccessStatusCode(); }
}
