import { NextResponse } from "next/server";
import { trendsData } from "@/lib/queries";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    return NextResponse.json(await trendsData());
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 500 });
  }
}
