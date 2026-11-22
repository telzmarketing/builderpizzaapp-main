using System.Text.Json.Serialization;

namespace GranTorino.PrintService.Contracts;

public sealed record ApiEnvelope<T>([property: JsonPropertyName("success")] bool Success, [property: JsonPropertyName("data")] T? Data);
public sealed record PairRequest(
    [property: JsonPropertyName("code")] string Code,
    [property: JsonPropertyName("hostname")] string Hostname,
    [property: JsonPropertyName("agent_version")] string AgentVersion);
public sealed record PairResponse(
    [property: JsonPropertyName("access_token")] string AccessToken,
    [property: JsonPropertyName("station_id")] string? StationId);
public sealed record PairData([property: JsonPropertyName("access_token")] string AccessToken, [property: JsonPropertyName("station_id")] string? StationId);
public sealed record JobEnvelope([property: JsonPropertyName("job")] PrintJob? Job);
public sealed record PrintJob(
    [property: JsonPropertyName("id")] string Id,
    [property: JsonPropertyName("printer_id")] string? PrinterId,
    [property: JsonPropertyName("printer_name")] string? PrinterName,
    [property: JsonPropertyName("document_type")] string DocumentType,
    [property: JsonPropertyName("document_format")] string? DocumentFormat,
    [property: JsonPropertyName("payload_ref")] string? ContentUrl,
    [property: JsonPropertyName("payload_metadata")] Dictionary<string, object>? Metadata,
    [property: JsonPropertyName("copies")] int Copies,
    [property: JsonPropertyName("idempotency_key")] string? IdempotencyKey);
public sealed record JobStatusRequest(
    [property: JsonPropertyName("status")] string Status,
    [property: JsonPropertyName("message")] string? Message,
    [property: JsonPropertyName("attempt_id")] string? AttemptId);
public sealed record HeartbeatPrinter(
    [property: JsonPropertyName("code")] string Code,
    [property: JsonPropertyName("status")] string Status);
public sealed record HeartbeatRequest(
    [property: JsonPropertyName("hostname")] string Hostname,
    [property: JsonPropertyName("agent_version")] string AgentVersion,
    [property: JsonPropertyName("printers")] HeartbeatPrinter[] Printers);

public sealed class AgentState
{
    [JsonPropertyName("access_token")] public string? AccessToken { get; set; }
    [JsonPropertyName("device_id")] public string DeviceId { get; set; } = Environment.MachineName;
    [JsonPropertyName("station_id")] public string? StationId { get; set; }
}
