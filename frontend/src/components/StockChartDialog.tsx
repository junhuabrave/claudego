import React, { useEffect, useRef, useState } from "react";
import {
  Box,
  CircularProgress,
  Dialog,
  DialogContent,
  DialogTitle,
  IconButton,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
  useMediaQuery,
  useTheme,
} from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";
import TrendingUpIcon from "@mui/icons-material/TrendingUp";
import TrendingDownIcon from "@mui/icons-material/TrendingDown";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import dayjs from "dayjs";
import { useTranslation } from "react-i18next";
import { getCandles } from "../services/api";
import type { CandlePoint, Ticker } from "../types";
import type { EnhancedCandlePoint } from "../workers/priceStats.worker";

interface Props {
  ticker: Ticker | null;
  onClose: () => void;
}

type Resolution = "1D" | "1W" | "1M";

const RESOLUTION_PARAMS: Record<Resolution, { resolution: string; days: number }> = {
  "1D": { resolution: "5", days: 1 },
  "1W": { resolution: "D", days: 7 },
  "1M": { resolution: "D", days: 30 },
};

const STAT_LABELS = ["Open", "High", "Low", "Close"] as const;

export default function StockChartDialog({ ticker, onClose }: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const fullScreen = useMediaQuery(theme.breakpoints.down("sm"));

  const [resolution, setResolution] = useState<Resolution>("1D");
  const [candles, setCandles] = useState<CandlePoint[]>([]);
  const [enhanced, setEnhanced] = useState<EnhancedCandlePoint[]>([]);
  const [loading, setLoading] = useState(false);

  // Web Worker for SMA computation (Phase 3 — offloads moving-average maths from main thread).
  const workerRef = useRef<Worker | null>(null);

  useEffect(() => {
    workerRef.current = new Worker(
      new URL("../workers/priceStats.worker.ts", import.meta.url)
    );
    workerRef.current.onmessage = (e: MessageEvent<EnhancedCandlePoint[]>) => {
      setEnhanced(e.data);
    };
    return () => {
      workerRef.current?.terminate();
    };
  }, []);

  // Stable dep key: avoids re-fetching on price-only WebSocket updates.
  const symbol = ticker?.symbol;

  // Reset to 1D when the symbol changes.
  useEffect(() => {
    if (!symbol) return;
    setResolution("1D");
  }, [symbol]);

  // Fetch candles whenever symbol or resolution changes.
  useEffect(() => {
    if (!symbol) return;
    setLoading(true);
    setCandles([]);
    setEnhanced([]);
    const { resolution: res, days } = RESOLUTION_PARAMS[resolution];
    getCandles(symbol, res, days)
      .then((data) => {
        setCandles(data);
        // Dispatch to worker for SMA computation.
        workerRef.current?.postMessage({ candles: data });
      })
      .catch(() => setCandles([]))
      .finally(() => setLoading(false));
  }, [symbol, resolution]);

  const isPositive = (ticker?.change_percent ?? 0) >= 0;
  const chartColor = isPositive ? "#2e7d32" : "#c62828";
  const gradientId = "stockAreaGradient";

  const first = candles[0];
  const last = candles[candles.length - 1];
  const high = candles.length ? Math.max(...candles.map((c) => c.h)) : null;
  const low = candles.length ? Math.min(...candles.map((c) => c.l)) : null;

  const statValues: Record<(typeof STAT_LABELS)[number], number | null> = {
    Open: first?.o ?? null,
    High: high,
    Low: low,
    Close: last?.c ?? null,
  };

  const formatXAxis = (ts: number) =>
    resolution === "1D"
      ? dayjs(ts * 1000).format("HH:mm")
      : dayjs(ts * 1000).format("MMM D");

  const formatTooltipLabel = (ts: number) =>
    resolution === "1D"
      ? dayjs(ts * 1000).format("HH:mm")
      : dayjs(ts * 1000).format("MMM D, YYYY");

  // Use enhanced data (with SMAs) when available, fall back to raw candles.
  const chartData = enhanced.length > 0 ? enhanced : candles;

  return (
    <Dialog
      open={!!ticker}
      onClose={onClose}
      fullWidth
      maxWidth="md"
      fullScreen={fullScreen}
    >
      <DialogTitle sx={{ pb: 1 }}>
        <Box sx={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
          <Box>
            <Typography variant="h6" fontWeight={700} component="span">
              {ticker?.symbol}
            </Typography>
            <Typography variant="body2" color="text.secondary" component="span" sx={{ ml: 1 }}>
              {ticker?.name}
            </Typography>
          </Box>

          <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
            {ticker?.last_price != null && (
              <Box sx={{ textAlign: "right" }}>
                <Typography variant="h6" fontWeight={700} lineHeight={1.2}>
                  ${ticker.last_price.toFixed(2)}
                </Typography>
                <Box
                  sx={{ display: "flex", alignItems: "center", justifyContent: "flex-end", gap: 0.25 }}
                >
                  {isPositive ? (
                    <TrendingUpIcon sx={{ fontSize: 16 }} color="success" />
                  ) : (
                    <TrendingDownIcon sx={{ fontSize: 16 }} color="error" />
                  )}
                  <Typography
                    variant="body2"
                    color={isPositive ? "success.main" : "error.main"}
                    fontWeight={600}
                  >
                    {isPositive ? "+" : ""}
                    {ticker.change_percent?.toFixed(2)}%
                  </Typography>
                </Box>
              </Box>
            )}
            <IconButton
              onClick={onClose}
              size="small"
              sx={{ mt: -0.5 }}
              aria-label={t("chart.close")}
            >
              <CloseIcon fontSize="small" />
            </IconButton>
          </Box>
        </Box>
      </DialogTitle>

      <DialogContent sx={{ pt: 0 }}>
        {/* OHLC summary row */}
        {!loading && candles.length > 0 && (
          <Box
            sx={{
              display: "flex",
              gap: 3,
              mb: 2,
              p: 1.5,
              bgcolor: "action.hover",
              borderRadius: 1,
              flexWrap: "wrap",
            }}
          >
            {STAT_LABELS.map((label) => (
              <Box key={label}>
                <Typography variant="caption" color="text.secondary" display="block">
                  {label}
                </Typography>
                <Typography variant="body2" fontWeight={600}>
                  {statValues[label] != null ? `$${statValues[label]!.toFixed(2)}` : "—"}
                </Typography>
              </Box>
            ))}
            {last?.v != null && (
              <Box>
                <Typography variant="caption" color="text.secondary" display="block">
                  Volume
                </Typography>
                <Typography variant="body2" fontWeight={600}>
                  {last.v >= 1_000_000
                    ? `${(last.v / 1_000_000).toFixed(1)}M`
                    : last.v >= 1_000
                    ? `${(last.v / 1_000).toFixed(0)}K`
                    : last.v.toString()}
                </Typography>
              </Box>
            )}
            {/* SMA legend */}
            {enhanced.length > 0 && (
              <Box sx={{ ml: "auto", display: "flex", gap: 2, alignItems: "center" }}>
                <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
                  <Box sx={{ width: 20, height: 2, bgcolor: "#ff9800" }} />
                  <Typography variant="caption">SMA5</Typography>
                </Box>
                <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
                  <Box sx={{ width: 20, height: 2, bgcolor: "#9c27b0" }} />
                  <Typography variant="caption">SMA20</Typography>
                </Box>
              </Box>
            )}
          </Box>
        )}

        {/* Resolution toggle */}
        <Box sx={{ display: "flex", justifyContent: "flex-end", mb: 1 }}>
          <ToggleButtonGroup
            value={resolution}
            exclusive
            onChange={(_, v: Resolution | null) => v && setResolution(v)}
            size="small"
          >
            <ToggleButton value="1D">1D</ToggleButton>
            <ToggleButton value="1W">1W</ToggleButton>
            <ToggleButton value="1M">1M</ToggleButton>
          </ToggleButtonGroup>
        </Box>

        {/* Chart */}
        <Box sx={{ height: fullScreen ? "50vh" : 320 }}>
          {loading ? (
            <Box sx={{ display: "flex", justifyContent: "center", alignItems: "center", height: "100%" }}>
              <CircularProgress size={36} />
            </Box>
          ) : candles.length === 0 ? (
            <Box sx={{ display: "flex", justifyContent: "center", alignItems: "center", height: "100%" }}>
              <Typography color="text.secondary">{t("chart.noData")}</Typography>
            </Box>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={chartColor} stopOpacity={0.25} />
                    <stop offset="95%" stopColor={chartColor} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" vertical={false} />
                <XAxis
                  dataKey="t"
                  tickFormatter={formatXAxis}
                  tick={{ fontSize: 11, fill: "#888" }}
                  tickLine={false}
                  axisLine={false}
                  minTickGap={48}
                />
                <YAxis
                  domain={["auto", "auto"]}
                  tickFormatter={(v: number) => `$${v.toFixed(0)}`}
                  tick={{ fontSize: 11, fill: "#888" }}
                  tickLine={false}
                  axisLine={false}
                  width={58}
                />
                <Tooltip
                  formatter={(value: number) => [`$${value.toFixed(2)}`, "Price"]}
                  labelFormatter={formatTooltipLabel}
                  contentStyle={{ borderRadius: 8, border: "1px solid #e0e0e0", fontSize: 13 }}
                />
                <Area
                  type="monotone"
                  dataKey="c"
                  stroke={chartColor}
                  strokeWidth={2}
                  fill={`url(#${gradientId})`}
                  dot={false}
                  activeDot={{ r: 4, strokeWidth: 0, fill: chartColor }}
                />
                {enhanced.length > 0 && (
                  <>
                    <Line
                      type="monotone"
                      dataKey="sma5"
                      stroke="#ff9800"
                      strokeWidth={1.5}
                      dot={false}
                      activeDot={false}
                      isAnimationActive={false}
                    />
                    <Line
                      type="monotone"
                      dataKey="sma20"
                      stroke="#9c27b0"
                      strokeWidth={1.5}
                      dot={false}
                      activeDot={false}
                      isAnimationActive={false}
                    />
                  </>
                )}
              </AreaChart>
            </ResponsiveContainer>
          )}
        </Box>
      </DialogContent>
    </Dialog>
  );
}
