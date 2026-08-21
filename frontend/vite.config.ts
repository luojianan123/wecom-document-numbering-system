import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        // Windows 启动脚本中的 FastAPI 后端运行在 8088；
        // 如果仍代理到 8000，产品组件的 POST 请求会落到旧服务并返回 405。
        target: "http://localhost:8088",
        changeOrigin: true
      }
    }
  }
});
