import { useEffect, useRef } from 'react';
import type { WSMessage } from '../types';

export function useWebSocket(onMessage: (msg: WSMessage) => void) {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeout = useRef<ReturnType<typeof setTimeout>>();
  const cbRef = useRef(onMessage);
  cbRef.current = onMessage;

  useEffect(() => {
    let active = true;

    const connect = () => {
      if (!active) return;
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${protocol}//${window.location.host}/ws/dashboard`;

      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {};
      ws.onmessage = (event) => {
        try {
          const msg: WSMessage = JSON.parse(event.data);
          cbRef.current(msg);
        } catch {}
      };
      ws.onclose = () => {
        if (!active) return;
        reconnectTimeout.current = setTimeout(connect, 5000);
      };
      ws.onerror = () => ws.close();
    };

    connect();

    return () => {
      active = false;
      if (reconnectTimeout.current) clearTimeout(reconnectTimeout.current);
      wsRef.current?.close();
    };
  }, []);

  return wsRef;
}
