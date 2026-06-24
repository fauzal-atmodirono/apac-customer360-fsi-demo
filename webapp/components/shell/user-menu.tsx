import { LogOut } from "lucide-react";
import { auth, signOut } from "@/auth";

export async function UserMenu() {
  const session = await auth();
  if (!session?.user) return null;
  const { name, email } = session.user;
  return (
    <div className="space-y-2">
      <div className="min-w-0">
        <p className="truncate text-sm font-medium text-foreground">{name ?? email}</p>
        {name && <p className="truncate text-xs text-muted-foreground">{email}</p>}
      </div>
      <form
        action={async () => {
          "use server";
          await signOut({ redirectTo: "/signin" });
        }}
      >
        <button
          type="submit"
          className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
        >
          <LogOut className="h-3.5 w-3.5" /> Sign out
        </button>
      </form>
    </div>
  );
}
