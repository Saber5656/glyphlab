/** Bounded, shared LRU for authenticated SVG previews. SVG is rendered only in img. */
export class BlobUrlCache {
  private urls = new Map<string, string>();
  private pending = new Map<string, { cancelled: boolean; promise: Promise<string | undefined> }>();
  private active = 0;
  private waiters: (() => void)[] = [];
  constructor(private capacity = 350, private concurrency = 6) {}
  load(key: string, fetchBlob: () => Promise<Blob>): Promise<string | undefined> {
    const hit = this.urls.get(key);
    if (hit) { this.urls.delete(key); this.urls.set(key, hit); return Promise.resolve(hit); }
    const pending = this.pending.get(key);
    if (pending) return pending.promise;
    const entry = { cancelled: false, promise: Promise.resolve<string | undefined>(undefined) };
    entry.promise = (async () => {
      if (this.active >= this.concurrency) await new Promise<void>(resolve => this.waiters.push(resolve));
      else this.active++;
      try {
        if (entry.cancelled) return undefined;
        const blob = await fetchBlob();
        if (entry.cancelled) return undefined;
        const url = URL.createObjectURL(blob);
        this.urls.set(key, url);
        while (this.urls.size > this.capacity) {
          const oldest = this.urls.keys().next().value!;
          URL.revokeObjectURL(this.urls.get(oldest)!); this.urls.delete(oldest);
        }
        return url;
      } finally {
        if (this.pending.get(key) === entry) this.pending.delete(key);
        const waiter = this.waiters.shift();
        if (waiter) waiter(); else this.active--;
      }
    })();
    this.pending.set(key, entry);
    return entry.promise;
  }
  clear(prefix = "") {
    for (const [key, url] of this.urls) if (key.startsWith(prefix)) { URL.revokeObjectURL(url); this.urls.delete(key); }
    for (const [key, entry] of this.pending) if (key.startsWith(prefix)) { entry.cancelled = true; this.pending.delete(key); }
  }
}
export const glyphSvgCache = new BlobUrlCache();
