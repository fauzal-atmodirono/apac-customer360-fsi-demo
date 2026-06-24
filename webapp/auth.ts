import NextAuth from "next-auth";
import Google from "next-auth/providers/google";

// Comma-separated allowlist of domains (e.g. "devoteam.com") and/or explicit emails.
const ALLOWED_DOMAINS = (process.env.ALLOWED_DOMAIN ?? "")
  .split(",").map((s) => s.trim().toLowerCase()).filter(Boolean);
const ALLOWED_EMAILS = (process.env.ALLOWED_EMAILS ?? "")
  .split(",").map((s) => s.trim().toLowerCase()).filter(Boolean);

const PUBLIC_PREFIXES = ["/signin", "/api/auth", "/icons", "/manifest.webmanifest", "/sw.js", "/favicon"];

function isAllowed(email?: string | null): boolean {
  if (!email) return false;
  const e = email.toLowerCase();
  if (ALLOWED_EMAILS.length && ALLOWED_EMAILS.includes(e)) return true;
  const domain = e.split("@")[1];
  if (ALLOWED_DOMAINS.length) return ALLOWED_DOMAINS.includes(domain);
  // If no allowlist configured, deny by default (fail closed) unless explicitly opened.
  return process.env.ALLOW_ANY_GOOGLE === "true";
}

export const { handlers, signIn, signOut, auth } = NextAuth({
  trustHost: true, // Cloud Run terminates TLS upstream
  providers: [Google],
  pages: { signIn: "/signin" },
  callbacks: {
    signIn({ profile }) {
      return isAllowed(profile?.email);
    },
    authorized({ auth, request }) {
      // When the service is private (Cloud Run IAM / proxy gates access), the app's
      // own Google sign-in is bypassed — its OAuth callback needs a public URL.
      if (process.env.DISABLE_AUTH === "true") return true;
      const { pathname } = request.nextUrl;
      if (PUBLIC_PREFIXES.some((p) => pathname.startsWith(p))) return true;
      return !!auth?.user; // unauthenticated → redirected to pages.signIn
    },
  },
});
