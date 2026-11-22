using System.Drawing;
using System.Drawing.Printing;
using System.Text;
using GranTorino.PrintService.Contracts;

namespace GranTorino.PrintService.Services;

public interface IPrinterService
{
    IReadOnlyList<string> Enumerate();
    Task PrintAsync(PrintJob job, CancellationToken cancellationToken);
}

public sealed class WindowsPrinterService : IPrinterService
{
    public IReadOnlyList<string> Enumerate() => PrinterSettings.InstalledPrinters.Cast<string>().OrderBy(x => x).ToArray();

    public async Task PrintAsync(PrintJob job, CancellationToken cancellationToken)
    {
        var printer = job.PrinterName ?? job.PrinterId ?? new PrinterSettings().PrinterName;
        if (string.IsNullOrWhiteSpace(printer)) throw new InvalidOperationException("Nenhuma impressora foi informada.");
        var type = (job.DocumentFormat ?? job.DocumentType).ToLowerInvariant();
        var file = await MaterializeAsync(job, cancellationToken);
        for (var copy = 0; copy < Math.Max(1, job.Copies); copy++)
        {
            if (type.Contains("pdf") || type.Contains("png") || type.Contains("jpeg") || type.Contains("jpg"))
            {
                using var process = new System.Diagnostics.Process
                {
                    StartInfo = new()
                    {
                        FileName = file, Verb = "printto", Arguments = $"\"{printer}\"",
                        UseShellExecute = true, CreateNoWindow = true,
                        WindowStyle = System.Diagnostics.ProcessWindowStyle.Hidden,
                    },
                };
                if (!process.Start()) throw new InvalidOperationException("Não foi possível iniciar a impressão silenciosa.");
                await process.WaitForExitAsync(cancellationToken);
                continue;
            }

            using var document = new PrintDocument { PrinterSettings = { PrinterName = printer } };
            if (!document.PrinterSettings.IsValid) throw new InvalidOperationException($"Impressora inválida: {printer}");
            var text = await File.ReadAllTextAsync(file, Encoding.UTF8, cancellationToken);
            document.PrintPage += (_, e) => e.Graphics!.DrawString(text, new Font("Consolas", 9), Brushes.Black, e.MarginBounds);
            document.Print();
        }
    }

    private static async Task<string> MaterializeAsync(PrintJob job, CancellationToken ct)
    {
        var dir = Path.Combine(Path.GetTempPath(), "GranTorinoPrintService");
        Directory.CreateDirectory(dir);
        var fileName = job.Metadata?.TryGetValue("file_name", out var name) == true ? name?.ToString() : null;
        var ext = Path.GetExtension(fileName ?? "") is { Length: > 0 } value ? value : ".bin";
        var file = Path.Combine(dir, $"{Guid.NewGuid():N}{ext}");
        if (job.Metadata?.TryGetValue("content_base64", out var raw) == true && raw is not null)
            await File.WriteAllBytesAsync(file, Convert.FromBase64String(raw.ToString()!), ct);
        else if (!string.IsNullOrWhiteSpace(job.ContentUrl) && Uri.TryCreate(job.ContentUrl, UriKind.Absolute, out var uri))
            using (var client = new HttpClient()) await File.WriteAllBytesAsync(file, await client.GetByteArrayAsync(uri, ct), ct);
        else throw new InvalidOperationException("O job não possui conteúdo acessível ao agente.");
        return file;
    }
}
