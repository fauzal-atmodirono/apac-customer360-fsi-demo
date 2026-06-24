import { NextResponse } from "next/server";
import { personalizationData } from "@/lib/queries";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    return NextResponse.json(await personalizationData());
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 500 });
  }
}
