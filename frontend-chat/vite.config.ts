import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [
    react(),
    {
      name: 'chat-base-redirect',
      configureServer(server) {
        server.middlewares.use((req, res, next) => {
          if (req.url === '/chat') {
            res.statusCode = 302;
            res.setHeader('Location', '/chat/');
            res.end();
            return;
          }
          next();
        });
      },
    },
  ],
  base: '/chat/',
  server: {
    port: 5174,
    proxy: {
      '/api': {
        target: 'http://39.102.210.77:10086',
        changeOrigin: true,
      },
    },
  },
});
