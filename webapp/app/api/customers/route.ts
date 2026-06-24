import { NextResponse } from "next/server";
import { customerList } from "@/lib/queries";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    return NextResponse.json({ customers: await customerList() });
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 500 });
  }
}
