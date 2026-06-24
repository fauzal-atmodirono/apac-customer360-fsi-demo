export { auth as middleware } from "@/auth";

export const config = {
  // Run on everything except Next internals + static assets (the `authorized`
  // callback in auth.ts decides what's public vs gated).
  matcher: ["/((?!_next/static|_next/image|favicon.ico|icons|manifest.webmanifest|sw.js).*)"],
};
