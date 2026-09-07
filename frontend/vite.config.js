import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    // true = слушать на всех интерфейсах. Нужно по двум причинам: без
    // явного host Vite на этой машине поднимался только на IPv6 ([::1]),
    // и обращения на 127.0.0.1 висли; плюс так сайт доступен с телефона
    // и других устройств в той же сети.
    host: true,
    // Порт может назначаться снаружи (PORT), иначе обычный дефолт Vite.
    port: Number(process.env.PORT) || 5173
  }
});
