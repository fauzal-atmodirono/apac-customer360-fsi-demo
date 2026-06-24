import { redirect } from "next/navigation";
import { auth } from "@/auth";
import { AppSidebar } from "@/components/shell/app-sidebar";
import { UserMenu } from "@/components/shell/user-menu";

export default async function DashboardLayout({ children }: { children: React.ReactNode }) {
  const session = await auth();
  if (process.env.DISABLE_AUTH !== "true" && !session?.user) redirect("/signin");
  return (
    <div className="flex min-h-screen bg-background">
      <AppSidebar userSlot={<UserMenu />} />
      <main className="flex-1 overflow-x-hidden">
        <div className="mx-auto max-w-[1400px] px-6 py-6 lg:px-10">{children}</div>
      </main>
    </div>
  );
}
