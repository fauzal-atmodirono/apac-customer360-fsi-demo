import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

const BOT_URL = process.env.BOT_URL ?? "http://localhost:8100";
const BOT_API_KEY = process.env.BOT_API_KEY ?? "";

async function forward(method: "GET" | "POST", path: string[], body?: string) {
  const url = `${BOT_URL}/${path.join("/")}`;
  try {
    const res = await fetch(url, {
      method,
      headers: { "Content-Type": "application/json", ...(BOT_API_KEY ? { "X-Bot-Key": BOT_API_KEY } : {}) },
      body,
      signal: AbortSignal.timeout(30_000),
    });
    const text = await res.text();
    return new NextResponse(text, {
      status: res.status,
      headers: { "Content-Type": res.headers.get("Content-Type") ?? "application/json" },
    });
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 502 });
  }
}

export async function GET(_req: Request, { params }: { params: { path: string[] } }) {
  return forward("GET", params.path);
}

export async function POST(req: Request, { params }: { params: { path: string[] } }) {
  const body = await req.text();
  return forward("POST", params.path, body);
}
