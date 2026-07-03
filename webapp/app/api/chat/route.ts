import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export const maxDuration = 120;

const AGENT_URL = process.env.AGENT_URL ?? "http://localhost:8000";

// Deployed: mint a Google-signed ID token for the (private) agent Cloud Run service.
// Local: AGENT_URL is localhost → no auth header needed.
async function authHeader(): Promise<Record<string, string>> {
  if (AGENT_URL.startsWith("http://localhost") || AGENT_URL.startsWith("http://127.")) return {};
  try {
    const { GoogleAuth } = await import("google-auth-library");
    const client = await new GoogleAuth().getIdTokenClient(AGENT_URL);
    const headers = await client.getRequestHeaders();
    const token = (headers as Record<string, string>).Authorization ?? (headers as Record<string, string>).authorization;
    return token ? { Authorization: token } : {};
  } catch {
    return {};
  }
}

export async function POST(req: Request) {
  try {
    const { message, session_id } = await req.json();
    if (!message || typeof message !== "string") {
      return NextResponse.json({ error: "message required" }, { status: 400 });
    }
    const res = await fetch(`${AGENT_URL}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...(await authHeader()) },
      body: JSON.stringify({ message, session_id }),
      signal: AbortSignal.timeout(115_000),
    });
    if (!res.ok) {
      return NextResponse.json({ error: `agent ${res.status}` }, { status: 502 });
    }
    return NextResponse.json(await res.json());
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 500 });
  }
}
