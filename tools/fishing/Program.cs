using System.Collections.Concurrent;
using System.Diagnostics;
using System.Text;
using System.Text.Json;
using BD2Fishing;

// JSON-lines control adapter. No connection/injection occurs until `connect`.
internal static class Program
{
    private sealed record Request(int Id, string Op, JsonElement Data, long StopVersion);
    private static readonly object OutputLock = new();
    private static void Emit(object value)
    {
        lock (OutputLock) { Console.WriteLine(JsonSerializer.Serialize(value)); Console.Out.Flush(); }
    }

    public static int Main(string[] args)
    {
        Console.InputEncoding = new UTF8Encoding(false);
        Console.OutputEncoding = new UTF8Encoding(false);
        if (args.SequenceEqual(new[] { "--identity" }))
        {
            Emit(new { protocol = 1, upstream = "0.4.5", injection = false });
            return 0;
        }
        if (args.Length != 2 || args[0] != "--parent" || !int.TryParse(args[1], out int parentPid))
            return 2;
        using var parent = Process.GetProcessById(parentPid);
        using var lifetime = new CancellationTokenSource();
        using var queue = new BlockingCollection<Request>(32);
        using var link = new FishingControlLink(FishingIdentity.DataRoot);
        long heartbeat = Stopwatch.GetTimestamp();
        int connectedPid = 0;
        bool configured = false;
        var input = Task.Run(() =>
        {
            try
            {
                string? line;
                while ((line = Console.ReadLine()) != null)
                {
                    if (line.Length > 65536) throw new InvalidDataException("Command too large");
                    using var doc = JsonDocument.Parse(line);
                    var data = doc.RootElement.Clone();
                    var op = data.GetProperty("op").GetString()!;
                    if (op == "heartbeat")
                    { Interlocked.Exchange(ref heartbeat, Stopwatch.GetTimestamp()); continue; }
                    if (op is "stop" or "shutdown") link.RequestStop();
                    if (op == "shutdown") lifetime.Cancel();
                    queue.Add(new Request(data.GetProperty("id").GetInt32(), op, data, link.StopVersion));
                }
            }
            catch (Exception ex) { Emit(new { type = "transport_error", error = ex.Message }); }
            finally { link.RequestStop(); lifetime.Cancel(); queue.CompleteAdding(); }
        });
        using var watchdog = new Timer(_ =>
        {
            if (parent.HasExited || Stopwatch.GetElapsedTime(Interlocked.Read(ref heartbeat)).TotalSeconds > 5)
            {
                link.RequestStop(); lifetime.Cancel();
                try { link.Stop(); } catch { /* In-game lease also expires after 10 seconds. */ }
                Environment.Exit(3);
            }
        }, null, 500, 500);
        Emit(new { type = "ready", protocol = 1 });
        try
        {
            foreach (var req in queue.GetConsumingEnumerable())
            {
                try
                {
                    object? result = null;
                    switch (req.Op)
                    {
                        case "connect":
                            if (connectedPid != 0) throw new InvalidOperationException("Already connected");
                            int pid = req.Data.GetProperty("pid").GetInt32();
                            double started = req.Data.GetProperty("started").GetDouble();
                            result = new FishingConnection().Connect(
                                progress: message => Emit(new { type = "progress", message }),
                                cancellationToken: lifetime.Token, processId: pid, processStarted: started);
                            connectedPid = pid;
                            break;
                        case "configure":
                            if (connectedPid == 0) throw new InvalidOperationException("Not connected");
                            var settings = req.Data.GetProperty("settings").Deserialize<FishingSettings>()!;
                            // Never unlock protected fish through this integration.
                            settings.Retention.KeepLocked = true;
                            settings.Retention.KeepUnknown = true;
                            link.Configure(settings); configured = true;
                            break;
                        case "start":
                            var fresh = Snapshot();
                            if (!configured || !FishingControlLink.Fresh(fresh, DateTime.UtcNow)
                                || fresh!.ProcessId != connectedPid || !fresh.Ready)
                                throw new InvalidOperationException("请进入钓场，关闭游戏内自动钓鱼，等待钓点就绪。");
                            if (fresh.State == "Auto") throw new InvalidOperationException("请关闭游戏内自动钓鱼。");
                            lifetime.Token.ThrowIfCancellationRequested();
                            link.Start(connectedPid, req.StopVersion);
                            result = new { owner = link.OwnerId };
                            break;
                        case "status":
                            result = new { snapshot = Snapshot(), error = link.Error };
                            break;
                        case "stop": if (connectedPid != 0) link.Stop(); break;
                        case "shutdown":
                            if (connectedPid != 0) link.Stop();
                            Emit(new { id = req.Id, ok = true }); return 0;
                        default: throw new InvalidDataException("Unknown operation");
                    }
                    Emit(new { id = req.Id, ok = true, result });
                }
                catch (Exception ex)
                {
                    link.RequestStop();
                    try { link.Stop(); } catch { }
                    Emit(new { id = req.Id, ok = false, error = ex.GetBaseException().Message });
                }
            }
        }
        finally { link.RequestStop(); }
        return 0;
    }

    private static FishingSnapshot? Snapshot() => FishingJson.Read<FishingSnapshot>(
        Path.Combine(FishingIdentity.DataRoot, "latest.json"));
}
