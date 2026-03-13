import React, { useCallback, useContext, useEffect, useState } from "react";
import {
  Alert,
  AppBar,
  Box,
  Chip,
  Container,
  Grid,
  IconButton,
  MenuItem,
  Paper,
  Select,
  Snackbar,
  Tab,
  Tabs,
  Toolbar,
  Tooltip,
  Typography,
  useTheme,
} from "@mui/material";
import ShowChartIcon from "@mui/icons-material/ShowChart";
import InfoOutlinedIcon from "@mui/icons-material/InfoOutlined";
import Brightness4Icon from "@mui/icons-material/Brightness4";
import Brightness7Icon from "@mui/icons-material/Brightness7";
import { Trans, useTranslation } from "react-i18next";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import AlertsDialog from "../components/AlertsDialog";
import ChatBox from "../components/ChatBox";
import IPOCalendar from "../components/IPOCalendar";
import NewsFeed from "../components/NewsFeed";
import SetNameDialog from "../components/SetNameDialog";
import StatusBar from "../components/StatusBar";
import StockChartDialog from "../components/StockChartDialog";
import UserMenu from "../components/UserMenu";
import WatchList from "../components/WatchList";
// NOTE: React.lazy() for dialogs deferred to Phase 2 (Vite migration).
// CRA's Fast Refresh uses flushSync which is incompatible with Suspense on HMR.
import {
  IPOCalendarSkeleton,
  NewsFeedSkeleton,
  WatchListSkeleton,
} from "../components/common/LoadingSkeleton";
import { ColorModeContext } from "../contexts/ColorModeContext";
import { useAuth } from "../contexts/AuthContext";
import { useWebSocket } from "../hooks/useWebSocket";
import { getIPOs, getNews, getTickers, removeTicker } from "../services/api";
import type { AlertTriggered, NewsArticle, Ticker, WSMessage } from "../types";

const SUPPORTED_LANGUAGES = [
  { code: "en", label: "EN" },
  { code: "ko", label: "한국어" },
  { code: "ja", label: "日本語" },
  { code: "zh", label: "中文" },
] as const;

export default function Dashboard() {
  const { t, i18n } = useTranslation();
  const theme = useTheme();
  const { toggleColorMode } = useContext(ColorModeContext);
  const queryClient = useQueryClient();
  const { user, isAuthenticated } = useAuth();

  const [rightTab, setRightTab] = useState(0);
  const [selectedTicker, setSelectedTicker] = useState<Ticker | null>(null);
  const [alertsSymbol, setAlertsSymbol] = useState<string | null>(null);
  const [activeAlerts, setActiveAlerts] = useState<AlertTriggered[]>([]);
  const [setNameOpen, setSetNameOpen] = useState(false);

  // Prompt for display name after first Google login (never for anonymous users)
  useEffect(() => {
    if (isAuthenticated && user && !user.is_anonymous && !user.display_name) {
      setSetNameOpen(true);
    } else {
      setSetNameOpen(false);
    }
  }, [isAuthenticated, user]);

  // ── React Query ──────────────────────────────────────────────────────────
  const { data: tickers = [], isLoading: loadingTickers } = useQuery({
    queryKey: ["tickers", user?.id],
    queryFn: getTickers,
  });

  const { data: news = [], isLoading: loadingNews } = useQuery({
    queryKey: ["news"],
    queryFn: () => getNews(),
    staleTime: 60_000,
  });

  const { data: ipos = [], isLoading: loadingIPOs } = useQuery({
    queryKey: ["ipos"],
    queryFn: getIPOs,
    staleTime: 300_000, // IPOs update infrequently
  });

  // Optimistic ticker removal: removes from UI instantly, rolls back on error.
  const removeMutation = useMutation({
    mutationFn: removeTicker,
    onMutate: async (symbol) => {
      await queryClient.cancelQueries({ queryKey: ["tickers", user?.id] });
      const previous = queryClient.getQueryData<Ticker[]>(["tickers", user?.id]);
      queryClient.setQueryData<Ticker[]>(["tickers", user?.id], (old = []) =>
        old.filter((tk) => tk.symbol !== symbol)
      );
      return { previous };
    },
    onError: (_err, _symbol, ctx) => {
      queryClient.setQueryData(["tickers", user?.id], ctx?.previous);
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["tickers", user?.id] });
    },
  });

  // ── WebSocket ─────────────────────────────────────────────────────────────
  const handleWSMessage = useCallback(
    (msg: WSMessage) => {
      switch (msg.type) {
        case "news":
          queryClient.setQueryData<NewsArticle[]>(["news"], (old) => {
            const existing = old ?? [];
            return [msg.data as unknown as NewsArticle, ...existing].slice(0, 100);
          });
          break;
        case "quotes":
          queryClient.invalidateQueries({ queryKey: ["tickers", user?.id] });
          break;
        case "ipo_update":
          queryClient.invalidateQueries({ queryKey: ["ipos"] });
          break;
        case "alert": {
          const payload = msg.data as unknown as AlertTriggered;
          if (payload.user_id !== user?.id) break;
          setActiveAlerts((prev) => [payload, ...prev]);
          break;
        }
      }
    },
    [queryClient, user?.id]
  );

  const { connected } = useWebSocket(handleWSMessage);

  const dismissAlert = (alertId: number) =>
    setActiveAlerts((prev) => prev.filter((a) => a.alert_id !== alertId));

  const handleLanguageChange = (lang: string) => {
    i18n.changeLanguage(lang);
    try {
      localStorage.setItem("language", lang);
    } catch {
      // storage unavailable
    }
  };

  return (
    <Box sx={{ display: "flex", flexDirection: "column", minHeight: "100vh" }}>
      <AppBar position="static" elevation={1}>
        <Toolbar>
          <ShowChartIcon sx={{ mr: 1 }} />
          <Typography
            variant="h6"
            sx={{ flexGrow: 1, display: { xs: "none", sm: "block" } }}
          >
            {t("app.title")}
          </Typography>

          {/* StatusBar hidden on very small screens to prevent overflow */}
          <Box sx={{ display: { xs: "none", md: "flex" }, mr: 1 }}>
            <StatusBar
              wsConnected={connected}
              tickerCount={tickers.length}
              newsCount={news.length}
            />
          </Box>

          {/* Language selector */}
          <Select
            value={i18n.language.split("-")[0]}
            onChange={(e) => handleLanguageChange(e.target.value as string)}
            size="small"
            variant="standard"
            inputProps={{ "aria-label": t("nav.language") }}
            sx={{
              color: "inherit",
              mr: 1,
              minWidth: 56,
              ".MuiSelect-icon": { color: "inherit" },
              "&:before": { borderColor: "rgba(255,255,255,0.4)" },
            }}
          >
            {SUPPORTED_LANGUAGES.map((l) => (
              <MenuItem key={l.code} value={l.code}>
                {l.label}
              </MenuItem>
            ))}
          </Select>

          {/* Dark mode toggle */}
          <Tooltip
            title={
              theme.palette.mode === "dark" ? t("nav.darkModeOff") : t("nav.darkModeOn")
            }
          >
            <IconButton color="inherit" onClick={toggleColorMode} size="small" sx={{ mr: 1 }}>
              {theme.palette.mode === "dark" ? (
                <Brightness7Icon fontSize="small" />
              ) : (
                <Brightness4Icon fontSize="small" />
              )}
            </IconButton>
          </Tooltip>

          <UserMenu />
        </Toolbar>
      </AppBar>

      {/* Anonymous mode banner */}
      {!isAuthenticated && (
        <Box
          sx={{
            bgcolor: "info.light",
            color: "info.contrastText",
            px: 3,
            py: 0.75,
            display: "flex",
            alignItems: "center",
            gap: 1,
          }}
        >
          <InfoOutlinedIcon fontSize="small" />
          <Typography variant="body2" sx={{ flexGrow: 1 }}>
            <Trans i18nKey="banner.anonymous" />
          </Typography>
        </Box>
      )}

      {/* WebSocket reconnection indicator */}
      {!connected && (
        <Box sx={{ display: "flex", justifyContent: "center", py: 0.5, bgcolor: "warning.light" }}>
          <Chip label={t("banner.reconnecting")} color="warning" size="small" />
        </Box>
      )}

      <Container maxWidth="xl" sx={{ flex: 1, py: 2 }}>
        <Grid container spacing={2}>
          {/* Left column */}
          <Grid item xs={12} md={7} lg={8}>
            <Paper sx={{ p: 2, mb: 2 }}>
              <Typography variant="h6" gutterBottom>
                {t("news.title")}
              </Typography>
              <Box sx={{ maxHeight: "60vh", overflow: "hidden" }}>
                {loadingNews ? (
                  <NewsFeedSkeleton />
                ) : (
                  <NewsFeed articles={news} listHeight={500} />
                )}
              </Box>
            </Paper>

            <Paper sx={{ p: 2 }}>
              <Typography variant="h6" gutterBottom>
                {t("watchlist.title")}
              </Typography>
              {loadingTickers ? (
                <WatchListSkeleton />
              ) : (
                <WatchList
                  tickers={tickers}
                  onRemove={(symbol) => removeMutation.mutate(symbol)}
                  onSelectSymbol={setSelectedTicker}
                  onManageAlerts={(symbol) => setAlertsSymbol(symbol)}
                />
              )}
            </Paper>
          </Grid>

          {/* Right column */}
          <Grid item xs={12} md={5} lg={4}>
            <Paper sx={{ mb: 2 }}>
              <Tabs value={rightTab} onChange={(_, v) => setRightTab(v)} variant="fullWidth">
                <Tab label={t("ipo.title")} />
                <Tab label={t("reminders.title")} />
              </Tabs>
              <Box sx={{ p: 2, maxHeight: "40vh", overflow: "auto" }}>
                {rightTab === 0 &&
                  (loadingIPOs ? <IPOCalendarSkeleton /> : <IPOCalendar ipos={ipos} />)}
                {rightTab === 1 && (
                  <Typography color="text.secondary">{t("reminders.empty")}</Typography>
                )}
              </Box>
            </Paper>

            <Paper sx={{ p: 0 }}>
              <Box sx={{ p: 2, pb: 0 }}>
                <Typography variant="h6">{t("chat.title")}</Typography>
              </Box>
              <ChatBox
                onTickerChanged={() =>
                  queryClient.invalidateQueries({ queryKey: ["tickers", user?.id] })
                }
              />
            </Paper>
          </Grid>
        </Grid>
      </Container>

      <StockChartDialog ticker={selectedTicker} onClose={() => setSelectedTicker(null)} />

      {alertsSymbol && (
        <AlertsDialog
          open={true}
          symbol={alertsSymbol}
          onClose={() => setAlertsSymbol(null)}
        />
      )}

      <SetNameDialog open={setNameOpen} onClose={() => setSetNameOpen(false)} />

      {/* Price alert Snackbars */}
      {activeAlerts.map((a) => (
        <Snackbar
          key={a.alert_id}
          open
          autoHideDuration={8000}
          onClose={() => dismissAlert(a.alert_id)}
          anchorOrigin={{ vertical: "top", horizontal: "right" }}
        >
          <Alert
            severity={a.actual_change_pct >= 0 ? "success" : "error"}
            variant="filled"
            onClose={() => dismissAlert(a.alert_id)}
          >
            <strong>{a.symbol}</strong>{" "}
            {a.actual_change_pct >= 0 ? "▲" : "▼"}
            {Math.abs(a.actual_change_pct).toFixed(2)}% — ${a.current_price.toFixed(2)}
          </Alert>
        </Snackbar>
      ))}
    </Box>
  );
}
