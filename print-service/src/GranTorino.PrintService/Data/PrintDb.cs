using Microsoft.Data.Sqlite;
using GranTorino.PrintService.Contracts;

namespace GranTorino.PrintService.Data;

public sealed class PrintDb
{
    private readonly string _connectionString;
    public PrintDb(string dataDirectory)
    {
        Directory.CreateDirectory(dataDirectory);
        _connectionString = new SqliteConnectionStringBuilder { DataSource = Path.Combine(dataDirectory, "print-service.db"), ForeignKeys = true }.ToString();
        using var db = Open();
        using var command = db.CreateCommand();
        command.CommandText = """
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS printers (name TEXT PRIMARY KEY, last_seen_utc TEXT NOT NULL, status TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, printer_name TEXT NULL, status TEXT NOT NULL, idempotency_key TEXT NULL UNIQUE, last_error TEXT NULL, updated_utc TEXT NOT NULL);
            """;
        command.ExecuteNonQuery();
    }
    private SqliteConnection Open() { var c = new SqliteConnection(_connectionString); c.Open(); return c; }
    public string? GetState(string key) { using var db = Open(); using var c = db.CreateCommand(); c.CommandText = "SELECT value FROM state WHERE key=$key"; c.Parameters.AddWithValue("$key", key); return c.ExecuteScalar() as string; }
    public void SetState(string key, string value) { using var db = Open(); using var c = db.CreateCommand(); c.CommandText = "INSERT INTO state(key,value) VALUES($key,$value) ON CONFLICT(key) DO UPDATE SET value=excluded.value"; c.Parameters.AddWithValue("$key", key); c.Parameters.AddWithValue("$value", value); c.ExecuteNonQuery(); }
    public void SavePrinters(IEnumerable<string> printers) { using var db = Open(); using var tx = db.BeginTransaction(); foreach (var printer in printers) { using var c = db.CreateCommand(); c.Transaction = tx; c.CommandText = "INSERT INTO printers(name,last_seen_utc,status) VALUES($name,$now,'available') ON CONFLICT(name) DO UPDATE SET last_seen_utc=$now,status='available'"; c.Parameters.AddWithValue("$name", printer); c.Parameters.AddWithValue("$now", DateTimeOffset.UtcNow.ToString("O")); c.ExecuteNonQuery(); } tx.Commit(); }
    public bool TryClaim(PrintJob job) { using var db = Open(); using var c = db.CreateCommand(); c.CommandText = "INSERT INTO jobs(id,printer_name,status,idempotency_key,updated_utc) VALUES($id,$printer,'processing',$key,$now) ON CONFLICT(id) DO NOTHING"; c.Parameters.AddWithValue("$id", job.Id); c.Parameters.AddWithValue("$printer", (object?)job.PrinterName ?? DBNull.Value); c.Parameters.AddWithValue("$key", (object?)job.IdempotencyKey ?? DBNull.Value); c.Parameters.AddWithValue("$now", DateTimeOffset.UtcNow.ToString("O")); return c.ExecuteNonQuery() == 1; }
    public void Complete(string id, string status, string? error) { using var db = Open(); using var c = db.CreateCommand(); c.CommandText = "UPDATE jobs SET status=$status,last_error=$error,updated_utc=$now WHERE id=$id"; c.Parameters.AddWithValue("$id", id); c.Parameters.AddWithValue("$status", status); c.Parameters.AddWithValue("$error", (object?)error ?? DBNull.Value); c.Parameters.AddWithValue("$now", DateTimeOffset.UtcNow.ToString("O")); c.ExecuteNonQuery(); }
}
