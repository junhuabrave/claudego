import React, { useCallback, useEffect, useState } from "react";
import {
  Alert,
  AppBar,
  Box,
  Chip,
  Container,
  Grid,
  Paper,
  Snackbar,
  Tab,
  Tabs,
  Toolbar,
  Typography,
} from "@mui/material";
import ShowChartIcon from "@mui/icons-material/ShowChart";
import InfoOutlinedIcon from "@mui/icons-material/InfoOutlined";
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
import { useAuth } from "../contexts/AuthContext";
import { useWebSocket } from "../hooks/useWebSocket";
import { getIPOs, getNews, getTickers, removeTicker } from "../services/api";
import type { AlertTriggered, IPOEvent, NewsArticle, Ticker, WSMessage } from "../types";

export default function Dashboard() {
  const { user, isAuthenticated } = useAuth();

  const [tickers, setTickers] = useState<Ticker[]>([]);
  const [news, setNews] = useState<NewsArticle[]>([]);
  const [ipos, setIpos] = useState<IPOEvent[]>([]);
  const [loadingTickers, setLoadingTickers] = useState(true);
  const [loadingNews, setLoadingNews] = useState(true);
  const [loadingIPOs, setLoadingIPOs] = useState(true);
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

  const loadTickers = useCallback(async () => {
    try {
      setTickers(await getTickers());
    } catch {
      // backend may not be running yet
    } finally {
      setLoadingTickers(false);
    }
  }, []);

  const loadNews = useCallback(async () => {
    try {
      setNews(await getNews());
    } catch {
    } finally {
      setLoadingNews(false);
    }
  }, []);

  const loadIPOs = useCallback(async () => {
    try {
      setIpos(await getIPOs());
    } catch {
    } finally {
      setLoadingIPOs(false);
    }
  }, []);

  useEffect(() => {
    loadTickers();
    loadNews();
    loadIPOs();
  }, [loadTickers, loadNews, loadIPOs]);

  // Reload tickers when user changes (login / logout)
  useEffect(() => {
    loadTickers();
  }, [user?.id, loadTickers]);

  const handleWSMessage = useCallback(
    (msg: WSMessage) => {
      switch (msg.type) {
        case "news":
          setNews((prev) => [msg.data as unknown as NewsArticle, ...prev].slice(0, 100));
          break;
        case "quotes":
          loadTickers();
          break;
        case "ipo_update":
          loadIPOs();
          break;
        case "alert": {
          const payload = msg.data as unknown as AlertTriggered;
          if (payload.user_id !== user?.id) break;
          setActiveAlerts((prev) => [payload, ...prev]);
          break;
        }
      }
    },
    [loadTickers, loadIPOs, user?.id]
  );

  const { connected } = useWebSocket(handleWSMessage);

  const handleRemoveTicker = async (symbol: string) => {
    try {
      await removeTicker(symbol);
      await loadTickers();
    } catch {}
  };

  const dismissAlert = (alertId: number) =>
    setActiveAlerts((prev) => prev.filter((a) => a.alert_id !== alertId));

  return (
    <Box sx={{ display: "flex", flexDirection: "column", minHeight: "100vh", bgcolor: "grey.50" }}>
      <AppBar position="static" elevation={1}>
        <Toolbar>
          <ShowChartIcon sx={{ mr: 1 }} />
          <Typography variant="h6" sx={{ flexGrow: 1 }}>
            Financial Markets Monitor
          </Typography>
          <StatusBar wsConnected={connected} tickerCount={tickers.length} newsCount={news.length} />
          <Box sx={{ ml: 2 }}>
            <UserMenu />
          </Box>
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
            Your watchlist is session-only.{" "}
            <strong>Sign in with Google</strong> in the toolbar to save it permanently.
          </Typography>
        </Box>
      )}

      {/* WebSocket reconnection indicator */}
      {!connected && (
        <Box sx={{ display: "flex", justifyContent: "center", py: 0.5, bgcolor: "warning.light" }}>
          <Chip label="Reconnecting to live feed…" color="warning" size="small" />
        </Box>
      )}

      <Container maxWidth="xl" sx={{ flex: 1, py: 2 }}>
        <Grid container spacing={2}>
          {/* Left column */}
          <Grid item xs={12} md={7} lg={8}>
            <Paper sx={{ p: 2, mb: 2 }}>
              <Typography variant="h6" gutterBottom>
                Breaking News
              </Typography>
              <Box sx={{ maxHeight: "60vh", overflow: "auto" }}>
                {loadingNews ? <NewsFeedSkeleton /> : <NewsFeed articles={news} />}
              </Box>
            </Paper>

            <Paper sx={{ p: 2 }}>
              <Typography variant="h6" gutterBottom>
                Watchlist
              </Typography>
              {loadingTickers ? (
                <WatchListSkeleton />
              ) : (
                <WatchList
                  tickers={tickers}
                  onRemove={handleRemoveTicker}
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
                <Tab label="IPO Calendar" />
                <Tab label="Reminders" />
              </Tabs>
              <Box sx={{ p: 2, maxHeight: "40vh", overflow: "auto" }}>
                {rightTab === 0 &&
                  (loadingIPOs ? <IPOCalendarSkeleton /> : <IPOCalendar ipos={ipos} />)}
                {rightTab === 1 && (
                  <Typography color="text.secondary">
                    Your active reminders will appear here.
                  </Typography>
                )}
              </Box>
            </Paper>

            <Paper sx={{ p: 0 }}>
              <Box sx={{ p: 2, pb: 0 }}>
                <Typography variant="h6">Chat</Typography>
              </Box>
              <ChatBox onTickerChanged={loadTickers} />
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
