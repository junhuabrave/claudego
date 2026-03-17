import React from "react";
import {
  Box,
  Chip,
  IconButton,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tooltip,
  Typography,
} from "@mui/material";
import DeleteIcon from "@mui/icons-material/Delete";
import BarChartIcon from "@mui/icons-material/BarChart";
import NotificationsNoneIcon from "@mui/icons-material/NotificationsNone";
import TrendingUpIcon from "@mui/icons-material/TrendingUp";
import TrendingDownIcon from "@mui/icons-material/TrendingDown";
import { FixedSizeList, ListChildComponentProps } from "react-window";
import { useTranslation } from "react-i18next";
import type { Ticker } from "../types";

interface Props {
  tickers: Ticker[];
  onRemove: (symbol: string) => void;
  onSelectSymbol: (ticker: Ticker) => void;
  onManageAlerts: (symbol: string) => void;
}

// Virtualize when ticker count exceeds this threshold.
const VIRTUALIZE_THRESHOLD = 50;
// Row height must match the CSS height of VirtualRow below.
const ROW_HEIGHT = 48;
const VIRTUAL_LIST_HEIGHT = 320;

interface VRowData {
  tickers: Ticker[];
  onRemove: (symbol: string) => void;
  onSelectSymbol: (ticker: Ticker) => void;
  onManageAlerts: (symbol: string) => void;
  removeLabel: (symbol: string) => string;
  alertsLabel: (symbol: string) => string;
  chartLabel: (symbol: string) => string;
  removeTooltip: string;
  alertsTooltip: string;
}

// Column flex widths mirror the Table column widths for visual consistency.
const COL_SYMBOL = "18%";
const COL_NAME = "28%";
const COL_PRICE = "18%";
const COL_CHANGE = "22%";
const COL_ACTIONS = "14%";

function VirtualRow({ index, style, data }: ListChildComponentProps<VRowData>) {
  const {
    tickers,
    onRemove,
    onSelectSymbol,
    onManageAlerts,
    removeLabel,
    alertsLabel,
    chartLabel,
    removeTooltip,
    alertsTooltip,
  } = data;
  const t = tickers[index];
  const isUp = (t.change_percent ?? 0) >= 0;

  return (
    <Box
      style={style}
      role="row"
      tabIndex={0}
      onClick={() => onSelectSymbol(t)}
      onKeyDown={(e) => e.key === "Enter" && onSelectSymbol(t)}
      aria-label={chartLabel(t.symbol)}
      sx={{
        display: "flex",
        alignItems: "center",
        height: ROW_HEIGHT,
        px: 1,
        borderBottom: "1px solid",
        borderColor: "divider",
        cursor: "pointer",
        "&:hover": { bgcolor: "action.hover" },
        "&:focus": { outline: "2px solid", outlineColor: "primary.main", outlineOffset: -2 },
        boxSizing: "border-box",
      }}
    >
      <Box sx={{ flex: `0 0 ${COL_SYMBOL}`, display: "flex", alignItems: "center", gap: 0.75 }}>
        <BarChartIcon sx={{ fontSize: 15, color: "text.disabled" }} />
        <Typography fontWeight={600} variant="body2">
          {t.symbol}
        </Typography>
      </Box>
      <Box sx={{ flex: `0 0 ${COL_NAME}`, overflow: "hidden" }}>
        <Typography variant="body2" noWrap>
          {t.name}
        </Typography>
      </Box>
      <Box sx={{ flex: `0 0 ${COL_PRICE}`, textAlign: "right" }}>
        <Typography variant="body2">
          {t.last_price != null ? `$${t.last_price.toFixed(2)}` : "—"}
        </Typography>
      </Box>
      <Box sx={{ flex: `0 0 ${COL_CHANGE}`, display: "flex", justifyContent: "flex-end" }}>
        {t.change_percent != null ? (
          <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
            {isUp ? (
              <TrendingUpIcon fontSize="small" color="success" />
            ) : (
              <TrendingDownIcon fontSize="small" color="error" />
            )}
            <Chip
              label={`${isUp ? "+" : ""}${t.change_percent.toFixed(2)}%`}
              size="small"
              color={isUp ? "success" : "error"}
              variant="outlined"
            />
          </Box>
        ) : (
          <Typography variant="body2">—</Typography>
        )}
      </Box>
      <Box
        sx={{ flex: `0 0 ${COL_ACTIONS}`, display: "flex", justifyContent: "center" }}
        onClick={(e) => e.stopPropagation()}
      >
        <Tooltip title={alertsTooltip}>
          <IconButton
            size="small"
            aria-label={alertsLabel(t.symbol)}
            onClick={() => onManageAlerts(t.symbol)}
          >
            <NotificationsNoneIcon fontSize="small" />
          </IconButton>
        </Tooltip>
        <Tooltip title={removeTooltip}>
          <IconButton
            size="small"
            color="error"
            aria-label={removeLabel(t.symbol)}
            onClick={() => onRemove(t.symbol)}
          >
            <DeleteIcon fontSize="small" />
          </IconButton>
        </Tooltip>
      </Box>
    </Box>
  );
}

function VirtualHeader() {
  const { t } = useTranslation();
  return (
    <Box
      role="row"
      sx={{
        display: "flex",
        alignItems: "center",
        px: 1,
        py: 0.75,
        borderBottom: "2px solid",
        borderColor: "divider",
        bgcolor: "background.paper",
      }}
    >
      <Box sx={{ flex: `0 0 ${COL_SYMBOL}` }}>
        <Typography variant="caption" color="text.secondary" fontWeight={600}>
          {t("watchlist.symbol")}
        </Typography>
      </Box>
      <Box sx={{ flex: `0 0 ${COL_NAME}` }}>
        <Typography variant="caption" color="text.secondary" fontWeight={600}>
          {t("watchlist.name")}
        </Typography>
      </Box>
      <Box sx={{ flex: `0 0 ${COL_PRICE}`, textAlign: "right" }}>
        <Typography variant="caption" color="text.secondary" fontWeight={600}>
          {t("watchlist.price")}
        </Typography>
      </Box>
      <Box sx={{ flex: `0 0 ${COL_CHANGE}`, textAlign: "right", pr: 1 }}>
        <Typography variant="caption" color="text.secondary" fontWeight={600}>
          {t("watchlist.change")}
        </Typography>
      </Box>
      <Box sx={{ flex: `0 0 ${COL_ACTIONS}` }} />
    </Box>
  );
}

export default function WatchList({ tickers, onRemove, onSelectSymbol, onManageAlerts }: Props) {
  const { t } = useTranslation();

  if (!tickers.length) {
    return (
      <Typography color="text.secondary" sx={{ p: 2 }}>
        {t("watchlist.empty")}
      </Typography>
    );
  }

  // Standard MUI Table for small lists (≤50 items).
  if (tickers.length <= VIRTUALIZE_THRESHOLD) {
    return (
      <TableContainer>
        <Table size="small" aria-label={t("watchlist.ariaLabel")}>
          <TableHead>
            <TableRow>
              <TableCell>{t("watchlist.symbol")}</TableCell>
              <TableCell>{t("watchlist.name")}</TableCell>
              <TableCell align="right">{t("watchlist.price")}</TableCell>
              <TableCell align="right">{t("watchlist.change")}</TableCell>
              <TableCell align="center" width={100} />
            </TableRow>
          </TableHead>
          <TableBody>
            {tickers.map((tk) => {
              const isUp = (tk.change_percent ?? 0) >= 0;
              return (
                <TableRow
                  key={tk.id}
                  hover
                  tabIndex={0}
                  onClick={() => onSelectSymbol(tk)}
                  onKeyDown={(e) => e.key === "Enter" && onSelectSymbol(tk)}
                  aria-label={t("watchlist.chartAriaLabel", { symbol: tk.symbol })}
                  sx={{ cursor: "pointer" }}
                >
                  <TableCell>
                    <Box sx={{ display: "flex", alignItems: "center", gap: 0.75 }}>
                      <BarChartIcon sx={{ fontSize: 15, color: "text.disabled" }} />
                      <Typography fontWeight={600}>{tk.symbol}</Typography>
                    </Box>
                  </TableCell>
                  <TableCell>{tk.name}</TableCell>
                  <TableCell align="right">
                    {tk.last_price != null ? `$${tk.last_price.toFixed(2)}` : "—"}
                  </TableCell>
                  <TableCell align="right">
                    {tk.change_percent != null ? (
                      <Box
                        sx={{
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "flex-end",
                          gap: 0.5,
                        }}
                      >
                        {isUp ? (
                          <TrendingUpIcon fontSize="small" color="success" />
                        ) : (
                          <TrendingDownIcon fontSize="small" color="error" />
                        )}
                        <Chip
                          label={`${isUp ? "+" : ""}${tk.change_percent.toFixed(2)}%`}
                          size="small"
                          color={isUp ? "success" : "error"}
                          variant="outlined"
                        />
                      </Box>
                    ) : (
                      "—"
                    )}
                  </TableCell>
                  <TableCell align="center">
                    <Tooltip title={t("watchlist.alertsAriaLabel", { symbol: tk.symbol })}>
                      <IconButton
                        size="small"
                        aria-label={t("watchlist.alertsAriaLabel", { symbol: tk.symbol })}
                        onClick={(e) => {
                          e.stopPropagation();
                          onManageAlerts(tk.symbol);
                        }}
                      >
                        <NotificationsNoneIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title={t("watchlist.removeAriaLabel", { symbol: tk.symbol })}>
                      <IconButton
                        size="small"
                        color="error"
                        aria-label={t("watchlist.removeAriaLabel", { symbol: tk.symbol })}
                        onClick={(e) => {
                          e.stopPropagation();
                          onRemove(tk.symbol);
                        }}
                      >
                        <DeleteIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </TableContainer>
    );
  }

  // Virtualized list for large watchlists (>50 tickers).
  const rowProps: VRowData = {
    tickers,
    onRemove,
    onSelectSymbol,
    onManageAlerts,
    removeLabel: (symbol) => t("watchlist.removeAriaLabel", { symbol }),
    alertsLabel: (symbol) => t("watchlist.alertsAriaLabel", { symbol }),
    chartLabel: (symbol) => t("watchlist.chartAriaLabel", { symbol }),
    removeTooltip: t("watchlist.actions"),
    alertsTooltip: t("watchlist.actions"),
  };

  return (
    <Box role="table" aria-label={t("watchlist.ariaLabel")}>
      <VirtualHeader />
      <Box sx={{ height: VIRTUAL_LIST_HEIGHT }}>
        <FixedSizeList
          height={VIRTUAL_LIST_HEIGHT}
          width="100%"
          itemCount={tickers.length}
          itemSize={ROW_HEIGHT}
          itemData={rowProps}
          overscanCount={5}
        >
          {VirtualRow}
        </FixedSizeList>
      </Box>
    </Box>
  );
}
