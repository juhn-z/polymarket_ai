"use client";
import * as React from "react";

interface BinanceTicker {
  s: string;       // symbol
  c: string;       // last close price
  P: string;       // 24h change percent
}

const WS_URL = "wss://stream.binance.com:9443/ws/btcusdt@ticker";

export function useBTCPrice() {
  const [price, setPrice] = React.useState<number | null>(null);
  const [change, setChange] = React.useState<number | null>(null);
  const [connected, setConnected] = React.useState(false);

  React.useEffect(() => {
    let ws: WebSocket | null = null;
    let cancelled = false;
    function open() {
      if (cancelled) return;
      ws = new WebSocket(WS_URL);
      ws.onopen = () => setConnected(true);
      ws.onmessage = (ev) => {
        try {
          const t = JSON.parse(ev.data) as BinanceTicker;
          setPrice(parseFloat(t.c));
          setChange(parseFloat(t.P));
        } catch { /* ignore */ }
      };
      ws.onclose = () => {
        setConnected(false);
        if (!cancelled) setTimeout(open, 2_000); // auto-reconnect
      };
      ws.onerror = () => ws?.close();
    }
    open();
    return () => { cancelled = true; ws?.close(); };
  }, []);

  return { price, change, connected };
}
