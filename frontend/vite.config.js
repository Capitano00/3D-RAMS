import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import cesium from "vite-plugin-cesium";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const agentcoreProxyTarget = env.VITE_AGENTCORE_PROXY_TARGET || "http://127.0.0.1:8080";

  return {
    plugins: [react(), cesium()],
    server: {
      port: 5173,
      proxy: {
        "/agentcore": {
          target: agentcoreProxyTarget,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/agentcore/, ""),
        },
      },
    },
  };
});
