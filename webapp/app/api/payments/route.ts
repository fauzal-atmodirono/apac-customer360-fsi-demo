import { NextResponse } from "next/server";
import { paymentsData } from "@/lib/queries";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    return NextResponse.json(await paymentsData());
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 500 });
  }
}
