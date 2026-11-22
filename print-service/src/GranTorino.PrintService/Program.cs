using GranTorino.PrintService.Configuration;
using GranTorino.PrintService.Data;
using GranTorino.PrintService.Services;

var builder = Host.CreateApplicationBuilder(args);
builder.Services.AddWindowsService(options => options.ServiceName = "Gran Torino Print Service");
// O prefixo padrão do host preserva PrintService__ErpBaseUrl como a seção PrintService.
builder.Configuration.AddEnvironmentVariables();
var options = new AgentOptions(); builder.Configuration.GetSection("PrintService").Bind(options); builder.Services.AddSingleton(options);
builder.Logging.AddSimpleConsole(o => o.SingleLine = true);
builder.Services.AddSingleton(new PrintDb(options.EffectiveDataDirectory()));
builder.Services.AddSingleton<IPrinterService, WindowsPrinterService>();
builder.Services.AddHttpClient<ErpClient>((sp, http) => { var cfg = sp.GetRequiredService<AgentOptions>(); http.BaseAddress = new Uri(cfg.ErpBaseUrl.TrimEnd('/')); http.Timeout = TimeSpan.FromSeconds(cfg.RequestTimeoutSeconds); });
builder.Services.AddHostedService<PrintWorker>();
await builder.Build().RunAsync();
