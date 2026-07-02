import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Devoteam — Customer 360",
    short_name: "Devoteam C360",
    description: "Devoteam Customer 360 & hyper-personalization dashboard (Bank Muamalat Islamic-banking demo)",
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
