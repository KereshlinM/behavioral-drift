export interface DriftClientOptions {
  apiKey: string;
  userId: string;
  baseUrl?: string;
  context?: string;
  flushIntervalMs?: number;
  maxBatchSize?: number;
}

interface RawEvent {
  type: string;
  ts: number;
  data?: Record<string, unknown>;
}

interface DriftResult {
  drift_type: string;
  severity: "low" | "medium" | "high";
  score: number;
  signals: Record<string, number>;
}

interface SessionEndResult {
  session_id: number;
  drift: DriftResult | null;
  duration_ms: number;
  event_count: number;
}

export class DriftClient {
  private apiKey: string;
  private userId: string;
  private baseUrl: string;
  private context?: string;
  private flushIntervalMs: number;
  private maxBatchSize: number;

  private sessionId: number | null = null;
  private queue: RawEvent[] = [];
  private flushTimer: ReturnType<typeof setInterval> | null = null;
  private lastActivityTs = 0;
  private idleStart: number | null = null;
  private readonly IDLE_THRESHOLD_MS = 3000;

  private boundHandlers: Map<string, EventListener> = new Map();

  constructor(opts: DriftClientOptions) {
    this.apiKey = opts.apiKey;
    this.userId = opts.userId;
    this.baseUrl = (opts.baseUrl ?? "http://localhost:8000").replace(/\/$/, "");
    this.context = opts.context;
    this.flushIntervalMs = opts.flushIntervalMs ?? 5000;
    this.maxBatchSize = opts.maxBatchSize ?? 50;
  }

  async startSession(): Promise<number> {
    const res = await this._post("/api/v1/sessions", {
      user_id: this.userId,
      context: this.context ?? null,
    });
    this.sessionId = res.session_id;
    this._attachListeners();
    this.flushTimer = setInterval(() => this._flush(), this.flushIntervalMs);
    return this.sessionId!;
  }

  async endSession(): Promise<SessionEndResult> {
    if (!this.sessionId) throw new Error("No active session. Call startSession() first.");
    await this._flush();
    this._detachListeners();
    if (this.flushTimer) clearInterval(this.flushTimer);
    const result = await this._post(`/api/v1/sessions/${this.sessionId}/end`, {});
    this.sessionId = null;
    return result as SessionEndResult;
  }

  track(type: string, data?: Record<string, unknown>): void {
    if (!this.sessionId) return;
    this.queue.push({ type, ts: Date.now(), data });
    if (this.queue.length >= this.maxBatchSize) this._flush();
  }

  private _attachListeners(): void {
    const click = (e: Event) => {
      const target = e.target as HTMLElement | null;
      this.track("click", {
        x: (e as MouseEvent).clientX,
        y: (e as MouseEvent).clientY,
        element_type: target?.tagName?.toLowerCase(),
        element_id: target?.id || undefined,
      });
      this._resetIdleTimer();
    };

    const scroll = () => {
      this.track("scroll", {
        delta: window.scrollY,
        depth_pct: document.documentElement.scrollHeight > 0
          ? window.scrollY / document.documentElement.scrollHeight
          : 0,
      });
      this._resetIdleTimer();
    };

    const keydown = (e: Event) => {
      const ke = e as KeyboardEvent;
      let key_type = "char";
      if (ke.key === "Backspace" || ke.key === "Delete") key_type = "backspace";
      else if (ke.key.length > 1) key_type = "special";
      this.track("keypress", { key_type, interval_ms: Date.now() - this.lastActivityTs });
      this._resetIdleTimer();
    };

    const beforeunload = () => {
      this._flush(true);
    };

    document.addEventListener("click", click, { passive: true });
    document.addEventListener("scroll", scroll, { passive: true });
    document.addEventListener("keydown", keydown, { passive: true });
    window.addEventListener("beforeunload", beforeunload);

    this.boundHandlers.set("click", click);
    this.boundHandlers.set("scroll", scroll);
    this.boundHandlers.set("keydown", keydown);
    this.boundHandlers.set("beforeunload", beforeunload);

    this.lastActivityTs = Date.now();
    this._startIdleWatcher();
  }

  private _detachListeners(): void {
    const click = this.boundHandlers.get("click");
    const scroll = this.boundHandlers.get("scroll");
    const keydown = this.boundHandlers.get("keydown");
    const beforeunload = this.boundHandlers.get("beforeunload");
    if (click) document.removeEventListener("click", click);
    if (scroll) document.removeEventListener("scroll", scroll);
    if (keydown) document.removeEventListener("keydown", keydown);
    if (beforeunload) window.removeEventListener("beforeunload", beforeunload);
    this.boundHandlers.clear();
    this._stopIdleWatcher();
  }

  private _idleWatcher: ReturnType<typeof setInterval> | null = null;

  private _startIdleWatcher(): void {
    this._idleWatcher = setInterval(() => {
      const now = Date.now();
      const gap = now - this.lastActivityTs;
      if (gap >= this.IDLE_THRESHOLD_MS && this.idleStart === null) {
        this.idleStart = this.lastActivityTs + this.IDLE_THRESHOLD_MS;
      }
    }, 1000);
  }

  private _stopIdleWatcher(): void {
    if (this._idleWatcher) clearInterval(this._idleWatcher);
  }

  private _resetIdleTimer(): void {
    const now = Date.now();
    if (this.idleStart !== null) {
      const idleDuration = now - this.idleStart;
      if (idleDuration > 0) {
        this.track("idle", { duration_ms: idleDuration });
      }
      this.idleStart = null;
    }
    this.lastActivityTs = now;
  }

  private async _flush(sync = false): Promise<void> {
    if (!this.sessionId || this.queue.length === 0) return;
    const batch = this.queue.splice(0, this.maxBatchSize);
    const body = JSON.stringify({ events: batch.map(e => ({ type: e.type, ts: e.ts, data: e.data })) });

    if (sync && navigator.sendBeacon) {
      navigator.sendBeacon(
        `${this.baseUrl}/api/v1/sessions/${this.sessionId}/events`,
        new Blob([body], { type: "application/json" }),
      );
      return;
    }

    try {
      await fetch(`${this.baseUrl}/api/v1/sessions/${this.sessionId}/events`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-API-Key": this.apiKey },
        body,
      });
    } catch {
      // Re-queue on failure
      this.queue.unshift(...batch);
    }
  }

  private async _post(path: string, body: unknown): Promise<Record<string, unknown>> {
    const res = await fetch(`${this.baseUrl}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-API-Key": this.apiKey },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail ?? `HTTP ${res.status}`);
    }
    return res.json();
  }
}
