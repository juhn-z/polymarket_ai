/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Avoid SSR-pre-evaluating wagmi/RainbowKit (browser-only deps).
  transpilePackages: ["@rainbow-me/rainbowkit"],
  webpack: (config) => {
    // wagmi sometimes pulls "pino-pretty" through transitive deps; mark optional.
    config.externals.push("pino-pretty", "lokijs", "encoding");
    return config;
  },
};

export default nextConfig;
