using GranTorino.PrintService.Configuration;
using GranTorino.PrintService.Contracts;
using GranTorino.PrintService.Data;
using System.Text.Json;

namespace GranTorino.PrintService.Services;

public sealed class PrintWorker : BackgroundService
{
    private readonly ErpClient _erp; private readonly IPrinterService _printers; private readonly PrintDb _db; private readonly AgentOptions _options; private readonly ILogger<PrintWorker> _log; private DateTimeOffset _heartbeat = DateTimeOffset.MinValue;
    public PrintWorker(ErpClient erp, IPrinterService printers, PrintDb db, AgentOptions options, ILogger<PrintWorker> log) { _erp = erp; _printers = printers; _db = db; _options = options; _log = log; }
    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        _db.SavePrinters(_printers.Enumerate());
        while (!stoppingToken.IsCancellationRequested)
        {
            try
            {
                if (!_erp.IsPaired) await _erp.PairAsync(stoppingToken);
                if (DateTimeOffset.UtcNow - _heartbeat > TimeSpan.FromSeconds(_options.HeartbeatIntervalSeconds)) { await _erp.HeartbeatAsync(stoppingToken); _heartbeat = DateTimeOffset.UtcNow; }
                await WriteHealthAsync("healthy", null);
                var job = await _erp.NextJobAsync(stoppingToken);
                if (job is not null && _db.TryClaim(job)) await ProcessAsync(job, stoppingToken);
            }
            catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested) { break; }
            catch (Exception ex) { _log.LogError(ex, "Falha no ciclo do agente; nova tentativa será feita."); await WriteHealthAsync("degraded", ex.Message); }
            await Task.Delay(TimeSpan.FromSeconds(Math.Max(1, _options.PollIntervalSeconds)), stoppingToken);
        }
    }
    private async Task ProcessAsync(PrintJob job, CancellationToken ct)
    {
        try { await _erp.UpdateStatusAsync(job.Id, new("spooler_submitted", null, job.IdempotencyKey ?? job.Id), ct); await _printers.PrintAsync(job, ct); _db.Complete(job.Id, "printed", null); await _erp.UpdateStatusAsync(job.Id, new("printed", null, job.IdempotencyKey ?? job.Id), ct); }
        catch (Exception ex) { _db.Complete(job.Id, "error", ex.Message); try { await _erp.UpdateStatusAsync(job.Id, new("error", ex.Message, job.IdempotencyKey ?? job.Id), ct); } catch (Exception statusError) { _log.LogError(statusError, "Falha ao comunicar erro do job {JobId}", job.Id); } }
    }
    private Task WriteHealthAsync(string status, string? error)
    {
        var snapshot = new { status, paired = _erp.IsPaired, timestamp_utc = DateTimeOffset.UtcNow, printers = _printers.Enumerate(), last_error = error };
        var path = Path.Combine(_options.EffectiveDataDirectory(), "health.json");
        return File.WriteAllTextAsync(path, JsonSerializer.Serialize(snapshot, new JsonSerializerOptions { WriteIndented = true }));
    }
}
