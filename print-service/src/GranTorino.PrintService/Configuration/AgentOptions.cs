namespace GranTorino.PrintService.Configuration;

public sealed class AgentOptions
{
    public string ErpBaseUrl { get; set; } = "";
    public string PairingCode { get; set; } = "";
    public string StationId { get; set; } = "";
    public int PollIntervalSeconds { get; set; } = 3;
    public int HeartbeatIntervalSeconds { get; set; } = 30;
    public int RequestTimeoutSeconds { get; set; } = 30;
    public string DataDirectory { get; set; } = "";
    public string LogLevel { get; set; } = "Information";

    public string EffectiveDataDirectory() => string.IsNullOrWhiteSpace(DataDirectory)
        ? Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData), "GranTorino", "PrintService")
        : DataDirectory;
}
