# Frontend decisions

- Router: React Router data router (`createBrowserRouter` and `RouterProvider` from `react-router-dom`). One route tree holds the admin shell, the portal shell, and the public pages. `BrowserRouter` was skipped so layouts stay nested routes; TanStack Router was skipped to stay on the library named in the plan.
- The API client is a small `fetch` wrapper. It sends `credentials: "include"` and, on every mutating request, `X-CSRF-Token` copied from the readable `hris_csrf` cookie. Screens call the `/api/v1` paths the desk needs. A 403 or 404 becomes a quiet empty card instead of a crash, because several module routers are not mounted yet.
- The org chart uses `reactflow` with a small tree layout. No second layout package.
