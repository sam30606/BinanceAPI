## 介紹

接收從 TradingView Webhook 功能發出的 Request ，經由 PineScript 配合產生下單時所需的 Payload 來達到指標分析後自動下單

## TradingView Webhook Payload

- 設定內容示範

```json
{
  "PASSWORD": "aa",
  "TOTAL_ORDER": 2,
  "TICKER": "{{ticker}}",
  "SIDE": "{{strategy.order.alert_message}}",
  "ORDER_PRICE": {{plot_0}},
  "LIMIT_PRICE": {{plot_1}},
  "STOP_PRICE": {{plot_2}},
  "LEVER": {{plot_3}},
  "ORDER_PERC": {{plot_4}},
  "ORDER_TIME": {{plot_5}}
}
```

- 實際收到內容

```json
{
  "PASSWORD": "aa",
  "TOTAL_ORDER": 2,
  "TICKER": "GBPUSD",
  "SIDE": "sell",
  "ORDER_PRICE": 1.238,
  "LIMIT_PRICE": 1.2376578968407697,
  "STOP_PRICE": 1.2388021031592302,
  "ORDER_TIME": 16748962
}
```

- PASSWORD：自訂字串
- TOTAL_ORDER：這個帳號會開的交易數
- TICKER：交易別 (PineScript產生)
- SIDE：賣賣方向 (PineScript產生)
- ORDER_PRICE：下單價格 (PineScript產生)
- LIMIT_PRICE：TP價格 (PineScript產生)
- STOP_PRICE：SL價格 (PineScript產生)
- ORDER_TIME：訂單產生時間 (PineScript產生)
