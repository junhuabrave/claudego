import React, { useMemo, useState } from "react";
import { CssBaseline, ThemeProvider, createTheme } from "@mui/material";
import { GoogleOAuthProvider } from "@react-oauth/google";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthProvider } from "./contexts/AuthContext";
import { ColorModeContext } from "./contexts/ColorModeContext";
import ErrorBoundary from "./components/common/ErrorBoundary";
import Dashboard from "./pages/Dashboard";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      // 30 s stale time matches backend quote cache; WS invalidations override when live.
      staleTime: 30_000,
      refetchOnWindowFocus: false,
    },
  },
});

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID || "";

export default function App() {
  const [mode, setMode] = useState<"light" | "dark">(() => {
    try {
      return (localStorage.getItem("colorMode") as "light" | "dark") || "light";
    } catch {
      return "light";
    }
  });

  const colorMode = useMemo(
    () => ({
      toggleColorMode: () => {
        setMode((prev) => {
          const next = prev === "light" ? "dark" : "light";
          try {
            localStorage.setItem("colorMode", next);
          } catch {
            // storage unavailable — still toggle in memory
          }
          return next;
        });
      },
    }),
    []
  );

  const theme = useMemo(
    () =>
      createTheme({
        palette: {
          mode,
          primary: { main: "#1565c0" },
          secondary: { main: "#f57c00" },
        },
        typography: {
          fontFamily: '"Inter", "Roboto", "Helvetica", "Arial", sans-serif',
        },
      }),
    [mode]
  );

  return (
    <QueryClientProvider client={queryClient}>
      <GoogleOAuthProvider clientId={GOOGLE_CLIENT_ID}>
        <AuthProvider>
          <ColorModeContext.Provider value={colorMode}>
            <ThemeProvider theme={theme}>
              <CssBaseline />
              <ErrorBoundary>
                <Dashboard />
              </ErrorBoundary>
            </ThemeProvider>
          </ColorModeContext.Provider>
        </AuthProvider>
      </GoogleOAuthProvider>
    </QueryClientProvider>
  );
}
