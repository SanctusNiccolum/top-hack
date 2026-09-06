import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    // Без явного host Vite на этой машине слушает только IPv6 ([::1]),
    // и обращения на 127.0.0.1 висят без ответа.
    host: '127.0.0.1',
    port: 5173
  }
});
