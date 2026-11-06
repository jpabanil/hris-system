# HRIS frontend

```bash
npm install
npm run dev -- --host 127.0.0.1 --port 5174 --strictPort
```

The dev server proxies `/api` to `http://127.0.0.1:8010`. Sign-in uses cookie auth (`hris_access`, `hris_refresh`, `hris_csrf`).
