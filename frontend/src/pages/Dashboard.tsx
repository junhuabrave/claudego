import React, { useCallback, useEffect, useState } from "react";
import {
  AppBar,
  Box,
  Container,
  Grid,
  Paper,
  Tab,
  Tabs,
  Toolbar,
  Typography,
} from "@mui/material";
import ShowChartIcon from "@mui/icons-material/ShowChart";
import ChatBox from "../components/ChatBox";
import IPOCalendar from "../components/IPOCalendar";
import NewsFeed from "../components/NewsFeed";
import StatusBar from "../components/StatusBar";
import StockChartDialog from "../components/StockChartDialog";
import WatchList from "../components/WatchList";
import { useWebSocket } from "../hooks/useWebSocket";
import { getIPOs, getNews, getTickers, removeTicker } from "../services/api";
import type { IPOEvent, NewsArticle, Ticker, WSMessage } from "../types";

export default function Dashboard() {
  const [tickers, setTickers] = useState<Ticker[]>([]);
  const [news, setNews] = useState<NewsArticle[]>([]);
  const [ipos, setIpos] = useState<IPOEvent[]>([]);
  const [rightTab, setRightTab] = useState(0);
  const [selectedTicker, setSelectedTicker] = useState<Ticker | null>(null);

  const loadTickers = useCallback(async () => {
    try {
      setTickers(await getTickers());
    } catch {
      // backend may not be running yet
    }
  }, []);

  const loadNews = useCallback(async () => {
    try {
      setNews(await getNews());
    } catch {
      // backend may not be running yet
    }
  }, []);

  const loadIPOs = useCallback(async () => {
    try {
      setIpos(await getIPOs());
    } catch {
      // backend may not be running yet
    }
  }, []);

  useEffect(() => {
    loadTickers();
    loadNews();
    loadIPOs();
  }, [loadTickers, loadNews, loadIPOs]);

  const handleWSMessage = useCallback(
    (msg: WSMessage) => {
      switch (msg.type) {
        case "news":
          // Prepend new article
          setNews((prev) => [msg.data as unknown as NewsArticle, ...prev].slice(0, 100));
          break;
        case "quotes":
          // Update ticker prices
          loadTickers();
          break;
        case "ipo_update":
          loadIPOs();
          break;
      }
    },
    [loadTickers, loadIPOs]
  );

  const { connected } = useWebSocket(handleWSMessage);

  const handleRemoveTicker = async (symbol: string) => {
    try {
      await removeTicker(symbol);
      await loadTickers();
    } catch {
      // handle error
    }
  };

  return (
    <Box sx={{ display: "flex", flexDirection: "column", minHeight: "100vh", bgcolor: "grey.50" }}>
      <AppBar position="static" elevation={1}>
        <Toolbar>
          <ShowChartIcon sx={{ mr: 1 }} />
          <Typography variant="h6" sx={{ flexGrow: 1 }}>
            Financial Markets Monitor
          </Typography>
          <StatusBar wsConnected={connected} tickerCount={tickers.length} newsCount={news.length} />
        </Toolbar>
      </AppBar>

      <Container maxWidth="xl" sx={{ flex: 1, py: 2 }}>
        <Grid container spacing={2}>
          {/* Left column - News */}
          <Grid item xs={12} md={7} lg={8}>
            <Paper sx={{ p: 2, mb: 2 }}>
              <Typography variant="h6" gutterBottom>
                Breaking News
              </Typography>
              <Box sx={{ maxHeight: "60vh", overflow: "auto" }}>
                <NewsFeed articles={news} />
              </Box>
            </Paper>

            <Paper sx={{ p: 2 }}>
              <Typography variant="h6" gutterBottom>
                Watchlist
              </Typography>
              <WatchList
                tickers={tickers}
                onRemove={handleRemoveTicker}
                onSelectSymbol={setSelectedTicker}
              />
            </Paper>
          </Grid>

          {/* Right column - IPO Calendar + Chat */}
          <Grid item xs={12} md={5} lg={4}>
            <Paper sx={{ mb: 2 }}>
              <Tabs
                value={rightTab}
                onChange={(_, v) => setRightTab(v)}
                variant="fullWidth"
              >
                <Tab label="IPO Calendar" />
                <Tab label="Reminders" />
              </Tabs>
              <Box sx={{ p: 2, maxHeight: "40vh", overflow: "auto" }}>
                {rightTab === 0 && <IPOCalendar ipos={ipos} />}
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

      <StockChartDialog
        ticker={selectedTicker}
        onClose={() => setSelectedTicker(null)}
      />
    </Box>
  );
}
