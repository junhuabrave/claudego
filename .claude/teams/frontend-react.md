# Frontend React/TypeScript Engineering — Team Standards

> Load this file as agent context when working on `frontend/` code.

## Team Scope

You own **all frontend code** in `frontend/src/` and frontend build/deploy configs.

**Your files:**
- `frontend/src/components/` — Reusable UI components (ChatBox, NewsFeed, WatchList, AlertsDialog, etc.)
- `frontend/src/pages/` — Page-level components (Dashboard)
- `frontend/src/contexts/` — React Context providers (AuthContext)
- `frontend/src/hooks/` — Custom hooks (useWebSocket)
- `frontend/src/services/` — API client layer (api.ts)
- `frontend/src/types/` — TypeScript interfaces
- `frontend/src/__tests__/` — Frontend test suite
- `frontend/public/` — Static assets
- `frontend/package.json` — Dependencies
- `frontend/tsconfig.json` — TypeScript config
- `frontend/nginx.conf` / `frontend/nginx.prod.conf` — nginx reverse proxy configs

**Not your files (coordinate with respective teams):**
- `backend/` → Backend team (you consume their API, don't modify it)
- Auth flow implementation → coordinate with Auth/Security team
- `deploy/` → DevOps team
- `frontend/Dockerfile` → Shared with DevOps (you can modify build stages, they own runtime config)

---

## Coding Standards

### TypeScript
- **Strict mode**: `"strict": true` in tsconfig — no `any` types allowed
- **Interfaces over types** for object shapes: `interface UserData { ... }`
- **Types for unions/intersections**: `type Status = "active" | "inactive"`
- **No implicit returns** from async functions — always explicit return type
- **Formatter**: Prettier (default config)
- **Linter**: ESLint with `@typescript-eslint/recommended`

### Component Patterns
```tsx
// Functional components only — no class components
// Props interface defined above the component

interface WatchListProps {
  tickers: TickerData[];
  onRemove: (symbol: string) => void;
  isLoading?: boolean;
}

export default function WatchList({ tickers, onRemove, isLoading = false }: WatchListProps) {
  // hooks at the top
  const [filter, setFilter] = useState("");

  // derived state (no useEffect for computed values)
  const filtered = useMemo(
    () => tickers.filter(t => t.symbol.includes(filter.toUpperCase())),
    [tickers, filter]
  );

  // early returns for loading/empty states
  if (isLoading) return <CircularProgress />;
  if (tickers.length === 0) return <EmptyState message="No tickers yet" />;

  return (
    <List>
      {filtered.map(ticker => (
        <TickerRow key={ticker.symbol} ticker={ticker} onRemove={onRemove} />
      ))}
    </List>
  );
}
```

### File Organization
```
src/
├── components/
│   ├── WatchList.tsx           # Component
│   ├── WatchList.test.tsx      # Co-located test (preferred)
│   ├── ChatBox.tsx
│   └── common/                 # Shared UI primitives
│       ├── EmptyState.tsx
│       ├── ErrorBoundary.tsx
│       └── LoadingSkeleton.tsx
├── pages/
│   └── Dashboard.tsx           # Full page, composes components
├── contexts/
│   └── AuthContext.tsx          # Auth state + Google OAuth
├── hooks/
│   ├── useWebSocket.ts         # WebSocket connection + auto-reconnect
│   └── useLocalStorage.ts      # Typed localStorage wrapper
├── services/
│   └── api.ts                  # Axios instance + all API calls
├── types/
│   └── index.ts                # Shared TypeScript interfaces
└── __tests__/                  # Test files (alternative to co-located)
```

- One component per file
- File name matches component name: `WatchList.tsx` exports `WatchList`
- Co-locate tests next to components when possible: `WatchList.test.tsx`
- `common/` directory for shared UI primitives used by 3+ components

### MUI (Material UI) Conventions
```tsx
// Use MUI's sx prop for one-off styles
<Box sx={{ display: "flex", gap: 2, p: 2 }}>

// Use theme spacing units (1 unit = 8px)
sx={{ mt: 2, px: 3 }}  // margin-top: 16px, padding-x: 24px

// Use theme palette for colors — never hardcode hex values
sx={{ color: "primary.main", bgcolor: "background.paper" }}

// For reusable styled components, use styled()
const StyledCard = styled(Card)(({ theme }) => ({
  borderRadius: theme.shape.borderRadius * 2,
  transition: theme.transitions.create("box-shadow"),
}));
```

- **Never hardcode colors** — use theme palette: `primary.main`, `error.light`, `text.secondary`
- **Use MUI components** for all UI primitives — don't create custom buttons, inputs, dialogs
- **Responsive breakpoints**: `sx={{ fontSize: { xs: 14, md: 16 } }}`
- **Icons**: Import from `@mui/icons-material` — don't add new icon libraries

### State Management
- **Server state**: API data fetched via `api.ts` + stored in component state
- **Auth state**: `AuthContext` — provides `user`, `token`, `sessionId`, `login()`, `logout()`
- **UI state**: Component-local `useState` — keep state as close to usage as possible
- **No Redux** — this app doesn't need it. Context + hooks is sufficient
- If a piece of state is used by only one component, keep it in that component
- If shared by 2–3 sibling components, lift to their common parent

### API Client (`services/api.ts`)
```typescript
// All API calls go through the axios instance in api.ts
// The interceptor auto-attaches both headers on every request:
//   - Authorization: Bearer <jwt>  (if logged in)
//   - X-Session-ID: <uuid>         (always — for anonymous tracking)

// Pattern 1: Simple named exports (used for tickers, news, IPOs, chat)
export const getTickers = () => client.get<Ticker[]>("/tickers").then(r => r.data);
export const addTicker = (symbol: string, name?: string) =>
  client.post<Ticker>("/tickers", { symbol, name: name || "" }).then(r => r.data);

// Pattern 2: Grouped object export (used for alerts — preferred for CRUD resources)
export const alertsApi = {
  list: () => client.get<PriceAlert[]>("/alerts").then(r => r.data),
  create: (payload: { symbol: string; threshold_pct: number; direction: string }) =>
    client.post<PriceAlert>("/alerts", payload).then(r => r.data),
  update: (id: number, payload: Partial<{...}>) =>
    client.put<PriceAlert>(`/alerts/${id}`, payload).then(r => r.data),
  remove: (id: number) => client.delete(`/alerts/${id}`).then(() => undefined),
};
```

**Important:** `AuthContext` uses raw `fetch()` for `/auth/me` and `/auth/google` instead of the axios client. This is intentional to avoid circular dependency (api.ts imports from AuthContext). Do not refactor this without careful consideration.

- Use TypeScript generics on axios calls: `client.get<ResponseType>()`
- Handle errors at the component level (toast/snackbar), not in the API layer
- Base URL comes from environment: `REACT_APP_API_URL`
- For new CRUD resources, prefer the grouped object pattern (`alertsApi` style)

### WebSocket (`hooks/useWebSocket.ts`)
```typescript
// The hook takes a callback — NOT a "lastMessage" pattern
// Signature: useWebSocket(onMessage: (msg: WSMessage) => void) => { connected: boolean }

// Usage in components:
const { connected } = useWebSocket((msg) => {
  switch (msg.type) {
    case "quotes":
      setTickers(prev => mergeQuotes(prev, msg.data.quotes));
      break;
    case "news":
      setNews(prev => [msg.data, ...prev]);
      break;
    case "alert":
      showAlertNotification(msg.data);
      break;
  }
});

// Show connection status to user
{!connected && <Chip label="Reconnecting..." color="warning" size="small" />}
```

**Hook internals (do not change without Backend coordination):**
- Auto-reconnects with 3s delay on disconnect
- Sends "ping" every 30s to keep connection alive
- WS URL from `REACT_APP_WS_URL` env var, fallback auto-detects protocol
- `onMessageRef` pattern avoids stale closure issues

**WebSocket message types:** `quotes`, `news`, `alert`, `ipo_update`
- New message types require coordination with Backend team
- Always handle connection errors gracefully — show "Reconnecting..." indicator

### Performance Rules
- **Memoize expensive computations**: `useMemo()` for filtered/sorted lists
- **Memoize callbacks**: `useCallback()` for functions passed as props to child components
- **Lazy load pages**: `React.lazy()` for route-level code splitting
- **Virtualize long lists**: Use `react-window` for lists >100 items (news feed, ticker lists)
- **Optimize re-renders**: Use React DevTools Profiler to identify unnecessary re-renders
- **Image optimization**: Use `loading="lazy"` on images, WebP format where possible

### Error Handling
```tsx
// Wrap pages in ErrorBoundary
<ErrorBoundary fallback={<ErrorFallback />}>
  <Dashboard />
</ErrorBoundary>

// Show user-friendly errors via MUI Snackbar
const [error, setError] = useState<string | null>(null);

try {
  await createAlert(payload);
} catch (err) {
  setError("Failed to create alert. Please try again.");
}

<Snackbar open={!!error} message={error} autoHideDuration={5000} />
```

- Never show raw error messages or stack traces to users
- Use `ErrorBoundary` at page level to catch render errors
- Show retry buttons for recoverable errors (network failures)
- Log errors to console in development, to monitoring service in production

---

## Scaling TODO

### Phase 1: Foundation (10K DAU)
- [ ] Add ESLint + Prettier configs to enforce coding standards
- [ ] Add ErrorBoundary component wrapping Dashboard
- [ ] Implement code-splitting: `React.lazy()` for Dialog components (AlertsDialog, etc.)
- [ ] Add loading skeletons for all data-fetching components
- [ ] Optimize bundle: analyze with `source-map-explorer`, tree-shake unused MUI components
- [ ] Add `.env.production` with production API URL and Google Client ID
- [ ] Add service worker for offline capability (show cached data when disconnected)
- [ ] Implement WebSocket reconnection indicator in the UI ("Reconnecting...")

### Phase 2: Scale (100K DAU)
- [ ] Add i18n framework (`react-i18next`) — extract all strings to translation files
- [ ] Add `react-window` for virtualizing NewsFeed and WatchList when >100 items
- [ ] Implement optimistic UI updates (add ticker → show immediately, rollback on error)
- [ ] Add PWA manifest + icons for mobile home screen installation
- [ ] Add dark mode support via MUI theme toggle
- [ ] Implement stale-while-revalidate pattern for API data
- [ ] Add accessibility audit: keyboard navigation, ARIA labels, screen reader testing
- [ ] Migrate from CRA to Vite for faster builds and HMR

### Phase 3: Global (1M DAU)
- [ ] Multi-language support: EN, KO, JA, ZH at minimum (major financial markets)
- [ ] Regional market pages: US Markets, Korea (KOSPI), Japan (Nikkei), etc.
- [ ] Add Web Workers for heavy computation (chart rendering, data transformation)
- [ ] Implement micro-frontend architecture if team grows beyond 5 engineers
- [ ] Add performance monitoring (Web Vitals → analytics dashboard)
- [ ] Mobile-first responsive redesign for tablet/phone users
- [ ] A/B testing framework for UI experiments

---

## Local Development

```bash
cd frontend

# Install dependencies
npm install

# Start dev server (port 3000)
npm start

# Run tests
npm test

# Run tests with coverage
npm test -- --coverage --watchAll=false

# Production build
npm run build

# Analyze bundle size
npx source-map-explorer 'build/static/js/*.js'
```

### Environment Variables
```bash
# frontend/.env.development
REACT_APP_API_URL=http://localhost:8000/api
REACT_APP_WS_URL=ws://localhost:8000/api/ws
REACT_APP_GOOGLE_CLIENT_ID=your-google-client-id
```

---

## PR Checklist

- [ ] No `any` types — use proper TypeScript interfaces
- [ ] No hardcoded colors — use MUI theme palette
- [ ] No hardcoded strings — use constants or i18n keys
- [ ] Components have loading and error states
- [ ] New components have at least one test
- [ ] Bundle size not increased by >50KB (check with `source-map-explorer`)
- [ ] Responsive: tested at mobile (375px), tablet (768px), desktop (1280px)
- [ ] Accessibility: interactive elements have ARIA labels
- [ ] API changes coordinated with Backend team
