import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Bank Muamalat Malaysia — Customer 360",
    short_name: "Muamalat C360",
    description: "Bank Muamalat Malaysia Islamic-banking Customer 360 & hyper-personalization dashboard",
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
