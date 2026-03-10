# Frontend Team — Phase 1 Completion Sprint

**Sprint Duration:** 2 weeks
**Team Lead:** Frontend React Team
**Reference:** [frontend-react.md](../frontend-react.md) for coding standards

---

## Sprint Goal

Ship **developer tooling** (ESLint + Prettier) and **user-facing resilience** (ErrorBoundary, loading states). The frontend has zero component tests — the test engineering team owns that, but we need to make components testable.

---

## Tasks

### Task 1: ESLint + Prettier Configuration (P0) — 1 day

**Why:** No linting config exists. Code style is inconsistent across components. This is a prerequisite for productive multi-developer work.

**Implementation:**

1. Install dependencies:
   ```bash
   npm install -D eslint @typescript-eslint/eslint-plugin @typescript-eslint/parser \
     eslint-plugin-react eslint-plugin-react-hooks eslint-config-prettier prettier
   ```

2. Create `.eslintrc.json`:
   ```json
   {
     "extends": [
       "react-app",
       "plugin:@typescript-eslint/recommended",
       "plugin:react-hooks/recommended",
       "prettier"
     ],
     "rules": {
       "@typescript-eslint/no-unused-vars": ["error", { "argsIgnorePattern": "^_" }],
       "react-hooks/exhaustive-deps": "warn",
       "no-console": ["warn", { "allow": ["warn", "error"] }]
     }
   }
   ```

3. Create `.prettierrc`:
   ```json
   {
     "semi": true,
     "singleQuote": false,
     "trailingComma": "es5",
     "printWidth": 100,
     "tabWidth": 2
   }
   ```

4. Add scripts to `package.json`:
   ```json
   "lint": "eslint src/ --ext .ts,.tsx",
   "lint:fix": "eslint src/ --ext .ts,.tsx --fix",
   "format": "prettier --write src/"
   ```

5. Run `npm run lint:fix && npm run format` to normalize existing code. Commit as a **standalone commit** (no other changes mixed in).

**Acceptance Criteria:**
- [ ] `npm run lint` passes with zero errors
- [ ] CI runs ESLint (add to GitHub Actions `ci.yml`)
- [ ] Prettier formats all files consistently

---

### Task 2: ErrorBoundary Component (P1) — 1 day

**Why:** A single component crash takes down the entire app. Users see a white screen with no recovery option.

**Implementation:**

Create `src/components/ErrorBoundary.tsx`:
```tsx
import { Component, type ErrorInfo, type ReactNode } from "react";
import { Alert, Button, Box } from "@mui/material";

interface Props { children: ReactNode; }
interface State { hasError: boolean; error: Error | null; }

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("ErrorBoundary caught:", error, info.componentStack);
    // Future: send to error reporting service
  }

  render() {
    if (this.state.hasError) {
      return (
        <Box sx={{ p: 3, textAlign: "center" }}>
          <Alert severity="error" sx={{ mb: 2 }}>
            Something went wrong. Please try refreshing.
          </Alert>
          <Button variant="contained" onClick={() => window.location.reload()}>
            Refresh Page
          </Button>
        </Box>
      );
    }
    return this.props.children;
  }
}
```

Wrap in `App.tsx`:
```tsx
<ErrorBoundary>
  <AuthProvider>
    {/* existing app tree */}
  </AuthProvider>
</ErrorBoundary>
```

**Acceptance Criteria:**
- [ ] Component renders fallback UI when child throws
- [ ] Error is logged to console
- [ ] Refresh button reloads the page
- [ ] Wrap each major section independently (dashboard, news, IPOs) for granular recovery

---

### Task 3: Code-Splitting with React.lazy (P1) — 2 days

**Why:** Current bundle loads everything upfront. Dialog components (stock chart, alerts, set-name) are loaded even if user never opens them.

**Implementation:**

1. Lazy-load dialog components in `pages/Dashboard.tsx` (use **actual file names**):
   ```tsx
   const StockChartDialog = React.lazy(() => import("../components/StockChartDialog"));
   const AlertsDialog = React.lazy(() => import("../components/AlertsDialog"));
   const ChatBox = React.lazy(() => import("../components/ChatBox"));
   const SetNameDialog = React.lazy(() => import("../components/SetNameDialog"));
   ```

2. Wrap with Suspense in `pages/Dashboard.tsx`:
   ```tsx
   <Suspense fallback={<CircularProgress size={24} />}>
     {showAlerts && <AlertsDialog ... />}
   </Suspense>
   ```

3. Verify with bundle analysis:
   ```bash
   npx source-map-explorer 'build/static/js/*.js'
   ```

**Acceptance Criteria:**
- [ ] Dialog chunks load only when dialog opens
- [ ] Main bundle size reduced by >10%
- [ ] No visible loading jank (Suspense fallback is smooth)

---

### Task 4: Loading Skeletons (P1) — 2 days

**Why:** Dashboard shows empty space while data loads. Users perceive this as broken.

**Implementation:**

Use MUI's `<Skeleton>` component:

```tsx
// TickerCard skeleton
<Card>
  <CardContent>
    <Skeleton variant="text" width="40%" />
    <Skeleton variant="text" width="60%" />
    <Skeleton variant="rectangular" height={40} />
  </CardContent>
</Card>
```

Add skeletons for:
- Ticker cards (in `WatchList.tsx`)
- News article list (in `NewsFeed.tsx`)
- IPO events table (in `IPOCalendar.tsx`)
- Chart area (in `StockChartDialog.tsx`)

**Acceptance Criteria:**
- [ ] All data components show skeletons while loading
- [ ] Skeletons match the layout of real content (no layout shift)
- [ ] Skeleton disappears immediately when data arrives

---

### Task 5: WebSocket Reconnection Indicator (P1) — 1 day

**Why:** When WebSocket disconnects, users don't know real-time data is stale.

**Implementation:**

The `useWebSocket` hook already tracks `connected` state. Add a banner:

```tsx
{!connected && (
  <Alert severity="warning" sx={{ mb: 1 }}>
    Live data paused — reconnecting...
  </Alert>
)}
```

Place in `pages/Dashboard.tsx` above the ticker grid. The hook returns `{ connected }` — already confirmed in `useWebSocket.ts`.

**Acceptance Criteria:**
- [ ] Banner shows within 2s of disconnect
- [ ] Banner disappears on reconnect
- [ ] No flicker on initial connection

---

## Coordination

- **With Test Engineering:** After Task 1 (ESLint), test team will add test config. Make sure `src/setupTests.ts` is not broken.
- **With Backend:** No direct dependencies this sprint. Code-splitting and skeletons are frontend-only.
- **With DevOps:** ESLint step needs to be added to CI. Coordinate the `ci.yml` update.

---

## Out of Scope This Sprint

- Vite migration (Phase 2)
- i18n (Phase 2)
- Dark mode (Phase 2)
- Virtual scrolling (Phase 2)
- Service worker / PWA (Phase 2)

---

*Questions? Tag @frontend-lead in the PR or post in #frontend-team channel.*
