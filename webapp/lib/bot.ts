import "server-only";

// Server-side client for the collections-bot. The X-Bot-Key secret stays on the
// server; the browser talks to the bot only via /api/outreach/* and /api/workbench.
const BOT_URL = process.env.BOT_URL ?? "http://localhost:8100";
const BOT_API_KEY = process.env.BOT_API_KEY ?? "";

export async function botGet<T>(path: string): Promise<T> {
  const res = await fetch(`${BOT_URL}/${path.replace(/^\//, "")}`, {
    headers: BOT_API_KEY ? { "X-Bot-Key": BOT_API_KEY } : undefined,
    signal: AbortSignal.timeout(30_000),
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`collections-bot ${path}: HTTP ${res.status}`);
  return (await res.json()) as T;
}
