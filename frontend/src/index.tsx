import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./i18n"; // initialise i18n before first render
import { register as registerSW } from "./serviceWorkerRegistration";
import { reportWebVitals } from "./reportWebVitals";

const root = ReactDOM.createRoot(document.getElementById("root") as HTMLElement);
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);

// Precache static assets for offline capability (production builds only).
registerSW();

// Collect Core Web Vitals.
// In production pipe to analytics: reportWebVitals((m) => fetch('/api/analytics/vitals', { method: 'POST', body: JSON.stringify(m) }));
reportWebVitals(
  process.env.NODE_ENV === "development"
    ? (metric) => console.warn("[Web Vitals]", metric.name, metric.value.toFixed(1))
    : undefined
);
