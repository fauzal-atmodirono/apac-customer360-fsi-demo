import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

const BOT_URL = process.env.BOT_URL ?? "http://localhost:8100";

async function forward(method: "GET" | "POST", path: string[], body?: string) {
  const url = `${BOT_URL}/${path.join("/")}`;
  try {
    const res = await fetch(url, {
      method,
      headers: { "Content-Type": "application/json" },
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
