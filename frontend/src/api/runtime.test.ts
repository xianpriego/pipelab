import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { encodeFrame } from "./frames";
import { RuntimeConnection } from "./runtime";

class FakeSocket {
  static instances: FakeSocket[] = [];
  binaryType = "blob";
  onopen: (() => void) | null = null;
  onmessage: ((event: { data: unknown }) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  closed = false;
  constructor(readonly url: string) {
    FakeSocket.instances.push(this);
  }
  close() {
    this.closed = true;
    this.onclose?.();
  }
}

describe("RuntimeConnection", () => {
  beforeEach(() => {
    FakeSocket.instances = [];
    vi.useFakeTimers();
  });
  afterEach(() => vi.useRealTimers());

  const connect = () => {
    const handlers = { onEvent: vi.fn(), onFrame: vi.fn(), onConnection: vi.fn() };
    const connection = new RuntimeConnection("ws://x/ws", handlers, (url) => new FakeSocket(url) as unknown as WebSocket);
    connection.open();
    return { connection, handlers, socket: FakeSocket.instances[0] };
  };

  it("dispatches JSON events and binary frames", () => {
    const { handlers, socket } = connect();
    expect(socket.binaryType).toBe("arraybuffer");
    socket.onopen?.();
    socket.onmessage?.({ data: JSON.stringify({ type: "state", state: "playing" }) });
    socket.onmessage?.({ data: "not json" });
    socket.onmessage?.({ data: encodeFrame({ kind: "video", node_id: "n", mime: "image/jpeg", width: 1, height: 1 }, new Uint8Array([1])) });
    expect(handlers.onConnection).toHaveBeenCalledWith(true);
    expect(handlers.onEvent).toHaveBeenCalledTimes(1);
    expect(handlers.onEvent).toHaveBeenCalledWith({ type: "state", state: "playing" });
    expect(handlers.onFrame).toHaveBeenCalledTimes(1);
  });

  it("reconnects with backoff until closed", () => {
    const { connection, socket } = connect();
    socket.onclose?.();
    vi.advanceTimersByTime(500);
    expect(FakeSocket.instances).toHaveLength(2);
    connection.close();
    expect(FakeSocket.instances[1].closed).toBe(true);
    vi.advanceTimersByTime(20_000);
    expect(FakeSocket.instances).toHaveLength(2);
  });
});
