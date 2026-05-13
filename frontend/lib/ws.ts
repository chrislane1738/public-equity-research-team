import type { JobEvent } from "./types";

export interface JobStreamHandle {
  close: () => void;
}

export function openJobStream(
  baseUrl: string,
  jobId: string,
  onEvent: (event: JobEvent) => void,
  opts?: { onClose?: () => void; onError?: (e: Event) => void },
): JobStreamHandle {
  const wsUrl = baseUrl.replace(/^http/, "ws") + `/jobs/${jobId}/stream`;
  let closedByUs = false;
  let socket: WebSocket | null = null;
  let attempt = 0;

  function connect() {
    socket = new WebSocket(wsUrl);
    socket.onmessage = (msg) => {
      try {
        onEvent(JSON.parse(msg.data) as JobEvent);
      } catch (e) {
        console.error("ws parse error", e, msg.data);
      }
    };
    socket.onerror = (e) => opts?.onError?.(e);
    socket.onclose = () => {
      if (closedByUs) return;
      attempt += 1;
      if (attempt > 5) {
        opts?.onClose?.();
        return;
      }
      setTimeout(connect, Math.min(attempt * 500, 5000));
    };
  }
  connect();

  return {
    close() {
      closedByUs = true;
      socket?.close();
    },
  };
}
