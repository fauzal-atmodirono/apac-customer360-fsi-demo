import { NextResponse } from "next/server";
import { churnData } from "@/lib/queries";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    return NextResponse.json(await churnData());
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 500 });
  }
}
