import { NextResponse } from "next/server";
import { customerDetail } from "@/lib/queries";

export const dynamic = "force-dynamic";

export async function GET(_req: Request, { params }: { params: { id: string } }) {
  try {
    const data = await customerDetail(params.id);
    if (!data.profile) return NextResponse.json({ error: "not found" }, { status: 404 });
    return NextResponse.json(data);
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 500 });
  }
}
