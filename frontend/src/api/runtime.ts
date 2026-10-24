// Websocket client for runtime events and previews, with reconnection.

import { parseRuntimeEvent, type PreviewFrame, type RuntimeEvent } from "./events";
import { decodeFrame } from "./frames";

export interface RuntimeHandlers {
  onEvent: (event: RuntimeEvent) => void;
  onFrame: (frame: PreviewFrame) => void;
  onConnection?: (connected: boolean) => void;
}

type SocketFactory = (url: string) => WebSocket;

const MAX_BACKOFF_MS = 10_000;

export class RuntimeConnection {
  private socket: WebSocket | null = null;
  private closed = false;
  private attempts = 0;
  private timer: ReturnType<typeof setTimeout> | null = null;

  constructor(
    private readonly url: string,
    private readonly handlers: RuntimeHandlers,
    private readonly createSocket: SocketFactory = (target) => new WebSocket(target),
  ) {}

  open(): void {
    this.closed = false;
    this.connect();
  }

  close(): void {
    this.closed = true;
    if (this.timer) clearTimeout(this.timer);
    this.timer = null;
    this.socket?.close();
    this.socket = null;
  }

  private connect(): void {
    const socket = this.createSocket(this.url);
    socket.binaryType = "arraybuffer";
    socket.onopen = () => {
      this.attempts = 0;
      this.handlers.onConnection?.(true);
    };
    socket.onmessage = (message: MessageEvent) => this.dispatch(message.data);
    socket.onclose = () => {
      this.handlers.onConnection?.(false);
      if (!this.closed) this.scheduleReconnect();
    };
    socket.onerror = () => socket.close();
    this.socket = socket;
  }

  private dispatch(data: unknown): void {
    if (typeof data === "string") {
      const event = parseRuntimeEvent(data);
      if (event) this.handlers.onEvent(event);
    } else if (data instanceof ArrayBuffer) {
      const frame = decodeFrame(data);
      if (frame) this.handlers.onFrame(frame);
    }
  }

  private scheduleReconnect(): void {
    const delay = Math.min(500 * 2 ** this.attempts, MAX_BACKOFF_MS);
    this.attempts += 1;
    this.timer = setTimeout(() => this.connect(), delay);
  }
}
