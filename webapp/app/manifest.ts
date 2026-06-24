import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Customer 360 — Hyper-Personalization",
    short_name: "Customer 360",
    description: "Core Banking Customer 360 analytics dashboard",
    start_url: "/executive",
    display: "standalone",
    background_color: "#ffffff",
    theme_color: "#1565C0",
    icons: [
      { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png" },
      { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png" },
      { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  };
}
