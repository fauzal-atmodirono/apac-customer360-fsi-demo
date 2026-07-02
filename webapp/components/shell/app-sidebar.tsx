"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard, MapPin, TrendingDown, Megaphone, LineChart, ShieldCheck, Landmark, Users, Sparkles, Package,
  Wallet, Send, HandHeart, AlertTriangle, ArrowLeftRight, ClipboardList,
} from "lucide-react";
import { cn } from "@/lib/utils";

const NAV_GROUPS = [
  {
    section: "Overview",
    items: [{ href: "/executive", label: "Executive overview", icon: LayoutDashboard }],
  },
  {
    section: "Customer 360",
    items: [
      { href: "/customers", label: "Customers", icon: Users },
      { href: "/personalization", label: "Personalization", icon: Sparkles },
      { href: "/demographics", label: "Demographics", icon: MapPin },
    ],
  },
  {
    section: "Products & Marketing",
    items: [
      { href: "/products", label: "Products", icon: Package },
      { href: "/campaigns", label: "Campaigns", icon: Send },
      { href: "/marketing", label: "Marketing / NBA", icon: Megaphone },
    ],
  },
  {
    section: "Transactions & Money",
    items: [
      { href: "/payments", label: "Payments & channels", icon: ArrowLeftRight },
      { href: "/trends", label: "Spend & trends", icon: LineChart },
      { href: "/wellness", label: "Financial wellness", icon: Wallet },
      { href: "/social-finance", label: "Social finance", icon: HandHeart },
    ],
  },
  {
    section: "Credit & Risk",
    items: [
      { href: "/financing-health", label: "Financing health", icon: AlertTriangle },
      { href: "/collections", label: "Collections & recovery", icon: ClipboardList },
      { href: "/churn", label: "Churn risk", icon: TrendingDown },
    ],
  },
  {
    section: "Governance",
    items: [{ href: "/governance", label: "Governance", icon: ShieldCheck }],
  },
];

export function AppSidebar({ userSlot }: { userSlot?: React.ReactNode }) {
  const pathname = usePathname();
  return (
    <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col border-r bg-card md:flex">
      <div className="flex items-center gap-2 px-5 py-5">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary text-primary-foreground">
          <Landmark className="h-5 w-5" />
        </div>
        <div>
          <p className="text-sm font-semibold leading-tight">Devoteam</p>
          <p className="text-xs text-muted-foreground">Customer 360</p>
        </div>
      </div>
      <nav className="flex-1 space-y-4 overflow-y-auto px-3 py-2">
        {NAV_GROUPS.map(({ section, items }) => (
          <div key={section} className="space-y-1">
            <p className="px-3 pb-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/70">{section}</p>
            {items.map(({ href, label, icon: Icon }) => {
              const active = pathname === href || pathname.startsWith(`${href}/`);
              return (
                <Link
                  key={href}
                  href={href}
                  className={cn(
                    "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                    active
                      ? "bg-accent text-accent-foreground"
                      : "text-muted-foreground hover:bg-muted hover:text-foreground",
                  )}
                >
                  <Icon className="h-4 w-4" />
                  {label}
                </Link>
              );
            })}
          </div>
        ))}
      </nav>
      <div className="space-y-3 border-t px-5 py-4 text-xs text-muted-foreground">
        {userSlot}
        <div className="border-t pt-3">
          <p>Source: <code className="text-[11px]">mart_customer_360</code></p>
          <p className="mt-1">BigQuery · asia-southeast2</p>
        </div>
      </div>
    </aside>
  );
}
