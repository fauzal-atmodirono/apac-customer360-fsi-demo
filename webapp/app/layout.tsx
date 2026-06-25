import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { SwCleanup } from "@/components/sw-cleanup";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "Bank Muamalat Malaysia — Customer 360",
  description: "Bank Muamalat Malaysia Islamic-banking Customer 360 & hyper-personalization dashboard",
  manifest: "/manifest.webmanifest",
  appleWebApp: { capable: true, statusBarStyle: "default", title: "Muamalat C360" },
  other: { "mobile-web-app-capable": "yes" },
};

export const viewport: Viewport = { themeColor: "#1565C0" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={inter.variable} suppressHydrationWarning>
      <body className="font-sans"><SwCleanup />{children}</body>
    </html>
  );
}
