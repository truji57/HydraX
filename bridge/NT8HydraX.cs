#region Using declarations
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using System.Web.Script.Serialization;
using NinjaTrader.Cbi;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.AddOns;
#endregion

namespace NinjaTrader.NinjaScript.AddOns
{
    public class NT8HydraX : AddOnBase
    {
        private TcpListener _server;
        private Thread _serverThread;
        private JavaScriptSerializer _json = new JavaScriptSerializer();
        private int _port = 5555;

        private Dictionary<string, string> _posIdMap = new Dictionary<string, string>();
        private Dictionary<string, string> _idToKey = new Dictionary<string, string>();
        private int _posIdCounter = 0;
        private readonly object _posIdLock = new object();

        private void LoadConfig()
        {
            try
            {
                string path = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments),
                    "NinjaTrader 8", "hydrax_config.json");
                if (File.Exists(path))
                {
                    string json = File.ReadAllText(path);
                    var cfg = _json.Deserialize<Dictionary<string, object>>(json);
                    if (cfg != null && cfg.ContainsKey("port"))
                        _port = Convert.ToInt32(cfg["port"]);
                    Log("HydraX: Config loaded, port=" + _port, LogLevel.Information);
                }
                else
                {
                    Log("HydraX: No config file found, using default port " + _port, LogLevel.Information);
                }
            }
            catch (Exception ex)
            {
                Log("HydraX: Config error - " + ex.Message + ", using default port " + _port, LogLevel.Warning);
            }
        }

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Name = "NT8HydraX";
            }
            else if (State == State.Configure)
            {
                // Accounts might not be loaded yet - use timer to retry
                var timer = new System.Timers.Timer(2000);
                timer.Elapsed += (sender, args) =>
                {
                    if (_server == null && Account.All.Count > 0)
                    {
                        timer.Stop();
                        timer.Dispose();
                        StartServer();
                    }
                };
                timer.AutoReset = true;
                timer.Start();
                Log("HydraX: Waiting for accounts...", LogLevel.Information);
            }
            else if (State == State.Terminated)
            {
                try { _server?.Stop(); }
                catch { }
                _server = null;
            }
        }

        private void StartServer()
        {
            if (_server != null) return;

            LoadConfig();

            if (Account.All.Count == 0)
            {
                Log("HydraX: No accounts found", LogLevel.Warning);
                return;
            }

            Log("HydraX: " + Account.All.Count() + " accounts on port " + _port, LogLevel.Information);
            foreach (var a in Account.All)
            {
                try
                {
                    double bal = a.Get(AccountItem.CashValue, Currency.UsDollar);
                    Log("  " + a.Name + " (Balance: " + bal.ToString("F2") + ")", LogLevel.Information);
                }
                catch { }
            }

            _serverThread = new Thread(RunServer) { IsBackground = true, Name = "HydraX" };
            _serverThread.Start();
        }

        private void RunServer()
        {
            try
            {
                _server = new TcpListener(IPAddress.Loopback, _port);
                _server.Start();
                Log("HydraX: TCP ready on :" + _port, LogLevel.Information);

                while (_server != null)
                {
                    try
                    {
                        var client = _server.AcceptTcpClient();
                        new Thread(() => HandleClient(client)) { IsBackground = true }.Start();
                    }
                    catch { break; }
                }
            }
            catch (Exception ex)
            {
                Log("HydraX Error: " + ex.Message, LogLevel.Error);
            }
        }

        private void HandleClient(TcpClient client)
        {
            using (client)
            using (var stream = client.GetStream())
            {
                var reader = new StreamReader(stream, new UTF8Encoding(false));
                var writer = new StreamWriter(stream, new UTF8Encoding(false)) { AutoFlush = true, NewLine = "\n" };
                try
                {
                    while (true)
                    {
                        string line = reader.ReadLine();
                        if (string.IsNullOrEmpty(line)) break;

                        var cmd = _json.Deserialize<Dictionary<string, object>>(line);
                        string action = cmd.ContainsKey("action") ? cmd["action"].ToString() : "";
                        string response = "{}";

                        if (action == "ACCOUNT") response = GetAccountInfo(cmd);
                        else if (action == "ACCOUNTS") response = GetAccounts();
                        else if (action == "POSITIONS") response = GetPositions(cmd);
                        else if (action == "ORDERS") response = GetOrders(cmd);
                        else if (action == "OPEN") response = OpenPosition(cmd);
                        else if (action == "CLOSE") response = ClosePosition(cmd);
                        else if (action == "MODIFY") response = ModifyPosition(cmd);

                        writer.WriteLine(response);
                    }
                }
                catch (Exception ex)
                {
                    Log("HydraX: " + ex.Message, LogLevel.Warning);
                }
            }
        }

        private Account GetAccount(Dictionary<string, object> cmd)
        {
            if (cmd.ContainsKey("account"))
            {
                string name = cmd["account"].ToString();
                return Account.All.FirstOrDefault(a => a.Name == name);
            }
            return Account.All.FirstOrDefault();
        }

        private string MakePositionKey(Account acc, Position p)
        {
            return acc.Name + "|" + p.Instrument.FullName;
        }

        private string GetOrAssignPositionId(Account acc, Position p)
        {
            string key = MakePositionKey(acc, p);
            lock (_posIdLock)
            {
                if (!_posIdMap.ContainsKey(key))
                {
                    string id = "hp_" + (++_posIdCounter);
                    _posIdMap[key] = id;
                    _idToKey[id] = key;
                }
                return _posIdMap[key];
            }
        }

        private Position FindPositionById(Account acc, string positionId)
        {
            lock (_posIdLock)
            {
                if (_idToKey.TryGetValue(positionId, out string key))
                {
                    string[] parts = key.Split('|');
                    if (parts.Length >= 2 && parts[0] == acc.Name)
                    {
                        string instrument = parts[1];
                        return acc.Positions.FirstOrDefault(p =>
                            p.Instrument.FullName == instrument && p.Quantity != 0);
                    }
                }
            }
            return null;
        }

        private void CleanupStalePositionIds(Account acc)
        {
            lock (_posIdLock)
            {
                var currentKeys = new HashSet<string>(
                    acc.Positions.Where(p => p.Quantity != 0)
                        .Select(p => MakePositionKey(acc, p))
                );

                var staleKeys = _posIdMap.Keys
                    .Where(k => k.StartsWith(acc.Name + "|") && !currentKeys.Contains(k))
                    .ToList();

                foreach (var k in staleKeys)
                {
                    if (_posIdMap.TryGetValue(k, out string id))
                    {
                        _posIdMap.Remove(k);
                        _idToKey.Remove(id);
                    }
                }
            }
        }

        private string GetAccounts()
        {
            try
            {
                var names = new List<string>();
                foreach (var a in Account.All)
                {
                    if (!string.IsNullOrEmpty(a.Name))
                        names.Add(a.Name);
                }
                var result = new Dictionary<string, object> { ["ok"] = true, ["accounts"] = names };
                return _json.Serialize(result);
            }
            catch (Exception ex)
            {
                return "{\"ok\":false,\"error\":\"" + ex.Message.Replace("\"", "'") + "\"}";
            }
        }

        private string GetAccountInfo(Dictionary<string, object> cmd)
        {
            var acc = GetAccount(cmd);
            if (acc == null) return "{\"ok\":false,\"error\":\"No account\"}";

            try
            {
                double pnl = 0;
                try { pnl = acc.Get(AccountItem.UnrealizedProfitLoss, Currency.UsDollar); } catch { }
                double realized = 0;
                try { realized = acc.Get(AccountItem.RealizedProfitLoss, Currency.UsDollar); } catch { }
                var data = new Dictionary<string, object>
                {
                    ["ok"] = true,
                    ["name"] = acc.Name,
                    ["balance"] = acc.Get(AccountItem.CashValue, Currency.UsDollar),
                    ["positions"] = acc.Positions.Count(p => p.Quantity != 0),
                    ["unrealized"] = pnl,
                    ["realized"] = realized,
                };
                return _json.Serialize(data);
            }
            catch
            {
                return "{\"ok\":true,\"name\":\"" + acc.Name + "\"}";
            }
        }

        private string GetOrders(Dictionary<string, object> cmd)
        {
            var acc = GetAccount(cmd);
            if (acc == null) return "{\"ok\":false,\"error\":\"No account\"}";

            var list = new List<Dictionary<string, object>>();
            foreach (var o in acc.Orders.Where(o => o.OrderState == OrderState.Working || o.OrderState == OrderState.Accepted))
            {
                string otype = o.OrderType == OrderType.StopMarket ? "STOP" :
                               o.OrderType == OrderType.Limit ? "LIMIT" :
                               o.OrderType == OrderType.StopLimit ? "STOP_LIMIT" : "OTHER";
                list.Add(new Dictionary<string, object>
                {
                    ["ticket"] = o.Id,
                    ["symbol"] = o.Instrument.FullName,
                    ["type"] = otype,
                    ["direction"] = o.OrderAction == OrderAction.Buy ? "BUY" : "SELL",
                    ["quantity"] = o.Quantity,
                    ["limit_price"] = o.LimitPrice,
                    ["stop_price"] = o.StopPrice,
                    ["state"] = o.OrderState.ToString(),
                });
            }

            var result = new Dictionary<string, object> { ["ok"] = true, ["orders"] = list };
            return _json.Serialize(result);
        }
        private string GetPositions(Dictionary<string, object> cmd)
        {
            var acc = GetAccount(cmd);
            if (acc == null) return "{\"ok\":false,\"error\":\"No account\"}";

            CleanupStalePositionIds(acc);

            var list = new List<Dictionary<string, object>>();
            foreach (var p in acc.Positions.Where(p => p.Quantity != 0))
            {
                double sl = 0, tp = 0;
                bool isLong = p.MarketPosition == MarketPosition.Long;
                foreach (var o in acc.Orders.Where(o => o.Instrument == p.Instrument &&
                    (o.OrderState == OrderState.Working || o.OrderState == OrderState.Accepted)))
                {
                    if (o.OrderType == OrderType.StopMarket && o.StopPrice > 0 &&
                        ((isLong && o.OrderAction == OrderAction.Sell) || (!isLong && o.OrderAction == OrderAction.Buy)))
                        sl = o.StopPrice;
                    if (o.OrderType == OrderType.Limit && o.LimitPrice > 0 &&
                        ((isLong && o.OrderAction == OrderAction.Sell) || (!isLong && o.OrderAction == OrderAction.Buy)))
                        tp = o.LimitPrice;
                }

                string pid = GetOrAssignPositionId(acc, p);

                double tickSize = p.Instrument.MasterInstrument.TickSize;
                double tickValue = p.Instrument.MasterInstrument.PointValue * tickSize;

                list.Add(new Dictionary<string, object>
                {
                    ["symbol"] = p.Instrument.FullName,
                    ["direction"] = p.MarketPosition == MarketPosition.Long ? "BUY" : "SELL",
                    ["contracts"] = Math.Abs(p.Quantity),
                    ["entry_price"] = p.AveragePrice,
                    ["sl"] = sl,
                    ["tp"] = tp,
                    ["id"] = pid,
                    ["tick_size"] = tickSize,
                    ["tick_value"] = tickValue,
                });
            }

            var result = new Dictionary<string, object> { ["ok"] = true, ["positions"] = list };
            return _json.Serialize(result);
        }

        private string OpenPosition(Dictionary<string, object> cmd)
        {
            var acc = GetAccount(cmd);
            if (acc == null) return "{\"ok\":false,\"error\":\"No account\"}";

            try
            {
                string symbol = cmd["symbol"].ToString();
                int contracts = Convert.ToInt32(cmd["contracts"]);
                string direction = cmd["direction"].ToString().ToUpper();

                var instrument = Instrument.GetInstrument(symbol);
                if (instrument == null)
                    return "{\"ok\":false,\"error\":\"Symbol not found: " + symbol + "\"}";

                var orderAction = direction == "BUY" ? OrderAction.Buy : OrderAction.Sell;
                string magic = cmd.ContainsKey("magic") ? cmd["magic"].ToString() : "0";

                var order = acc.CreateOrder(
                    instrument,
                    orderAction,
                    OrderType.Market,
                    TimeInForce.Gtc,
                    contracts,
                    0, 0, "", "HydraX-" + magic, null
                );

                if (order == null)
                    return "{\"ok\":false,\"error\":\"CreateOrder returned null\"}";

                acc.Submit(new[] { order });

                // Esperar a que se ejecute
                for (int i = 0; i < 50; i++)
                {
                    if (order.OrderState == OrderState.Filled ||
                        order.OrderState == OrderState.PartFilled ||
                        order.OrderState == OrderState.Rejected ||
                        order.OrderState == OrderState.Cancelled)
                        break;
                    System.Threading.Thread.Sleep(100);
                }

                Log("HydraX: " + direction + " " + contracts + "x " + symbol + " on " + acc.Name +
                    " - OrderState=" + order.OrderState, LogLevel.Information);

                // SL/TP as separate orders (NT8 futures style)
                double sl = cmd.ContainsKey("sl") ? Convert.ToDouble(cmd["sl"]) : 0;
                double tp = cmd.ContainsKey("tp") ? Convert.ToDouble(cmd["tp"]) : 0;

                if (order.OrderState == OrderState.Filled || order.OrderState == OrderState.PartFilled)
                {
                    string ocoId = "HydraX-OCO-" + magic + "-" + DateTime.Now.Ticks;
                    if (sl > 0)
                    {
                        var slAction = direction == "BUY" ? OrderAction.Sell : OrderAction.Buy;
                        var slOrder = acc.CreateOrder(instrument, slAction, OrderType.StopMarket, TimeInForce.Gtc,
                            contracts, 0, sl, ocoId, "HydraX-SL-" + magic, null);
                        if (slOrder != null)
                        {
                            acc.Submit(new[] { slOrder });
                            Log("HydraX: SL " + sl + " placed for " + symbol + " on " + acc.Name, LogLevel.Information);
                        }
                    }
                    if (tp > 0)
                    {
                        var tpAction = direction == "BUY" ? OrderAction.Sell : OrderAction.Buy;
                        var tpOrder = acc.CreateOrder(instrument, tpAction, OrderType.Limit, TimeInForce.Gtc,
                            contracts, tp, 0, ocoId, "HydraX-TP-" + magic, null);
                        if (tpOrder != null)
                        {
                            acc.Submit(new[] { tpOrder });
                            Log("HydraX: TP " + tp + " placed for " + symbol + " on " + acc.Name, LogLevel.Information);
                        }
                    }
                    var pos = acc.Positions.FirstOrDefault(p => p.Instrument == instrument && p.Quantity != 0);
                    string posId = pos != null ? GetOrAssignPositionId(acc, pos) : (symbol + "_" + DateTime.Now.Ticks);
                    return "{\"ok\":true,\"position_id\":\"" + posId + "\"}";
                }

                return "{\"ok\":false,\"error\":\"Order " + order.OrderState + "\"}";
            }
            catch (Exception ex)
            {
                return "{\"ok\":false,\"error\":\"" + ex.Message.Replace("\"", "'") + "\"}";
            }
        }

        private string ModifyPosition(Dictionary<string, object> cmd)
        {
            var acc = GetAccount(cmd);
            if (acc == null) return "{\"ok\":false,\"error\":\"No account\"}";

            try
            {
                string symbol = cmd.ContainsKey("symbol") ? cmd["symbol"].ToString() : "";
                double sl = cmd.ContainsKey("sl") ? Convert.ToDouble(cmd["sl"]) : 0;
                double tp = cmd.ContainsKey("tp") ? Convert.ToDouble(cmd["tp"]) : 0;
                string magic = cmd.ContainsKey("magic") ? cmd["magic"].ToString() : "0";
                string positionId = cmd.ContainsKey("position_id") ? cmd["position_id"].ToString() : "";

                Position pos = null;
                if (!string.IsNullOrEmpty(positionId))
                    pos = FindPositionById(acc, positionId);
                if (pos == null && !string.IsNullOrEmpty(symbol))
                    pos = acc.Positions.FirstOrDefault(p => p.Instrument.FullName == symbol && p.Quantity != 0);

                if (pos == null) return "{\"ok\":false,\"error\":\"Position not found\"}";

                var instrument = pos.Instrument;

                var ordersToCancel = acc.Orders.Where(o => o.Instrument == instrument &&
                    (o.OrderState == OrderState.Working || o.OrderState == OrderState.Accepted) &&
                    (o.OrderType == OrderType.StopMarket || o.OrderType == OrderType.Limit)).ToList();

                foreach (var o in ordersToCancel)
                {
                    acc.Cancel(new[] { o });
                    Log("HydraX: Cancelling " + o.OrderType + " for " + instrument.FullName + " on " + acc.Name, LogLevel.Information);
                }

                foreach (var o in ordersToCancel)
                {
                    for (int i = 0; i < 50; i++)
                    {
                        if (o.OrderState == OrderState.Cancelled ||
                            o.OrderState == OrderState.Filled ||
                            o.OrderState == OrderState.Rejected)
                            break;
                        System.Threading.Thread.Sleep(100);
                    }
                    Log("HydraX: Cancelled " + o.OrderType + " state=" + o.OrderState + " for " + instrument.FullName, LogLevel.Information);
                }

                string ocoId = "HydraX-OCO-" + magic + "-" + DateTime.Now.Ticks;

                if (sl > 0)
                {
                    var slAction = pos.MarketPosition == MarketPosition.Long ? OrderAction.Sell : OrderAction.Buy;
                    var slOrder = acc.CreateOrder(instrument, slAction, OrderType.StopMarket,
                        TimeInForce.Gtc, Math.Abs(pos.Quantity), 0, sl, ocoId, "HydraX-SL-" + magic, null);
                    if (slOrder != null) acc.Submit(new[] { slOrder });
                }
                if (tp > 0)
                {
                    var tpAction = pos.MarketPosition == MarketPosition.Long ? OrderAction.Sell : OrderAction.Buy;
                    var tpOrder = acc.CreateOrder(instrument, tpAction, OrderType.Limit,
                        TimeInForce.Gtc, Math.Abs(pos.Quantity), tp, 0, ocoId, "HydraX-TP-" + magic, null);
                    if (tpOrder != null) acc.Submit(new[] { tpOrder });
                }

                return "{\"ok\":true}";
            }
            catch (Exception ex)
            {
                return "{\"ok\":false,\"error\":\"" + ex.Message.Replace("\"", "'") + "\"}";
            }
        }
        private string ClosePosition(Dictionary<string, object> cmd)
        {
            var acc = GetAccount(cmd);
            if (acc == null) return "{\"ok\":false,\"error\":\"No account\"}";

            try
            {
                string positionId = cmd.ContainsKey("position_id") ? cmd["position_id"].ToString() : "";
                string symbol = cmd.ContainsKey("symbol") ? cmd["symbol"].ToString() : "";

                Position pos = null;
                if (!string.IsNullOrEmpty(positionId))
                    pos = FindPositionById(acc, positionId);

                if (pos == null && !string.IsNullOrEmpty(symbol))
                    pos = acc.Positions.FirstOrDefault(p => p.Instrument.FullName == symbol && p.Quantity != 0);

                if (pos == null)
                    return "{\"ok\":false,\"error\":\"Position not found\"}";

                var instrument = pos.Instrument;

                var ordersToCancel = acc.Orders.Where(o => o.Instrument == instrument &&
                    (o.OrderState == OrderState.Working || o.OrderState == OrderState.Accepted) &&
                    (o.OrderType == OrderType.StopMarket || o.OrderType == OrderType.Limit)).ToList();

                foreach (var o in ordersToCancel)
                {
                    acc.Cancel(new[] { o });
                }

                foreach (var o in ordersToCancel)
                {
                    for (int i = 0; i < 50; i++)
                    {
                        if (o.OrderState == OrderState.Cancelled ||
                            o.OrderState == OrderState.Filled ||
                            o.OrderState == OrderState.Rejected)
                            break;
                        System.Threading.Thread.Sleep(100);
                    }
                }

                var orderAction = pos.MarketPosition == MarketPosition.Long
                    ? OrderAction.Sell : OrderAction.Buy;

                var order = acc.CreateOrder(
                    instrument,
                    orderAction,
                    OrderType.Market,
                    TimeInForce.Gtc,
                    Math.Abs(pos.Quantity),
                    0, 0, "", "HydraX Close", null
                );

                if (order != null)
                {
                    acc.Submit(new[] { order });
                    return "{\"ok\":true,\"closed\":1}";
                }

                return "{\"ok\":false,\"error\":\"CreateOrder returned null\"}";
            }
            catch (Exception ex)
            {
                return "{\"ok\":false,\"error\":\"" + ex.Message.Replace("\"", "'") + "\"}";
            }
        }
    }
}
