import withSerwistInit from "@serwist/next";

const withSerwist = withSerwistInit({
  swSrc: "app/sw.ts",
  swDest: "public/sw.js",
  disable: process.env.NODE_ENV === "development",
});

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  // BigQuery client is server-only; keep it out of the client bundle.
  experimental: {
    serverComponentsExternalPackages: ["@google-cloud/bigquery", "google-auth-library"],
  },
};

export default withSerwist(nextConfig);
