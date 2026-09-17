/*
 * NT8Bridge.cs — Standalone TCP Bridge para NinjaTrader 8
 * 
 * Se ejecuta como aplicacion de consola independiente.
 * No requiere compilar contra DLLs de NinjaTrader.
 * 
 * Compilar: dotnet build -c Release
 * Ejecutar: dotnet run
 */

using System;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Text.Json;
using System.Threading.Tasks;

namespace HydraXNT
{
    class Program
    {
        private const int PORT = 5555;
        private const string SIGNALS_PATH = @"C:\HydraX-NT\signals";
        private static bool _running = true;

        static async Task Main(string[] args)
        {
            Console.WriteLine("HydraX-NT Bridge v1.0.0");
            Console.WriteLine($"Listening on port {PORT}...");
            Console.WriteLine($"Signals path: {SIGNALS_PATH}");
            Console.WriteLine();
            Console.WriteLine("Asegurate de que NinjaTrader 8 esta abierto con el AddOn HydraXNTSignal.");
            Console.WriteLine();

            Directory.CreateDirectory(SIGNALS_PATH);

            var server = new TcpListener(IPAddress.Loopback, PORT);
            server.Start();

            while (_running)
            {
                try
                {
                    var client = await server.AcceptTcpClientAsync();
                    _ = Task.Run(() => HandleClient(client));
                }
                catch (Exception ex)
                {
                    Console.WriteLine($"Server error: {ex.Message}");
                }
            }
        }

        static async Task HandleClient(TcpClient client)
        {
            using (client)
            using (var stream = client.GetStream())
            using (var reader = new StreamReader(stream, Encoding.UTF8))
            using (var writer = new StreamWriter(stream, Encoding.UTF8) { AutoFlush = true })
            {
                try
                {
                    var line = await reader.ReadLineAsync();
                    if (string.IsNullOrEmpty(line)) return;

                    var cmd = JsonDocument.Parse(line).RootElement;
                    var action = cmd.GetProperty("action").GetString();
                    var response = "{}";
                    var timestamp = DateTime.Now.Ticks;

                    switch (action)
                    {
                        case "ACCOUNT":
                            response = "{\"ok\":true,\"message\":\"Bridge ready\"}";
                            break;
                        case "ACCOUNTS":
                            response = "{\"ok\":true,\"accounts\":[\"Sim101\"]}";
                            break;
                        case "POSITIONS":
                            response = "{\"ok\":true,\"positions\":[]}";
                            break;
                        case "OPEN":
                            response = WriteSignal("OPEN", cmd, timestamp);
                            break;
                        case "CLOSE":
                            response = WriteSignal("CLOSE", cmd, timestamp);
                            break;
                        case "MODIFY":
                            response = WriteSignal("MODIFY", cmd, timestamp);
                            break;
                    }

                    await writer.WriteLineAsync(response);
                }
                catch (Exception ex)
                {
                    Console.WriteLine($"Client error: {ex.Message}");
                }
            }
        }

        static string WriteSignal(string action, JsonElement cmd, long timestamp)
        {
            try
            {
                var account = "Sim101";
                if (cmd.TryGetProperty("account", out var acc))
                    account = acc.GetString() ?? "Sim101";

                var signal = new
                {
                    action,
                    account,
                    symbol = cmd.TryGetProperty("symbol", out var s) ? s.GetString() : "",
                    contracts = cmd.TryGetProperty("contracts", out var c) ? c.GetInt32() : 1,
                    direction = cmd.TryGetProperty("direction", out var d) ? d.GetString() : "BUY",
                    sl = cmd.TryGetProperty("sl", out var sl) ? sl.GetDouble() : 0,
                    tp = cmd.TryGetProperty("tp", out var tp) ? tp.GetDouble() : 0,
                    position_id = cmd.TryGetProperty("position_id", out var pid) ? pid.GetString() : "",
                    timestamp,
                };

                var filename = Path.Combine(SIGNALS_PATH, $"signal_{timestamp}.json");
                File.WriteAllText(filename, JsonSerializer.Serialize(signal));

                Console.WriteLine($"[{DateTime.Now:HH:mm:ss}] {action} {signal.symbol} x{signal.contracts} -> {filename}");
                return $"{{\"ok\":true,\"position_id\":\"{signal.symbol}_{timestamp}\"}}";
            }
            catch (Exception ex)
            {
                return $"{{\"ok\":false,\"error\":\"{ex.Message}\"}}";
            }
        }
    }
}
