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
  Typography,
} from "@mui/material";
import DeleteIcon from "@mui/icons-material/Delete";
import TrendingUpIcon from "@mui/icons-material/TrendingUp";
import TrendingDownIcon from "@mui/icons-material/TrendingDown";
import type { Ticker } from "../types";

interface Props {
  tickers: Ticker[];
  onRemove: (symbol: string) => void;
}

export default function WatchList({ tickers, onRemove }: Props) {
  if (!tickers.length) {
    return (
      <Typography color="text.secondary" sx={{ p: 2 }}>
        Your watchlist is empty. Use the chat to add tickers (e.g., "add AAPL").
      </Typography>
    );
  }

  return (
    <TableContainer>
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>Symbol</TableCell>
            <TableCell>Name</TableCell>
            <TableCell align="right">Price</TableCell>
            <TableCell align="right">Change</TableCell>
            <TableCell align="center" width={50}></TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {tickers.map((t) => {
            const isUp = (t.change_percent ?? 0) >= 0;
            return (
              <TableRow key={t.id} hover>
                <TableCell>
                  <Typography fontWeight={600}>{t.symbol}</Typography>
                </TableCell>
                <TableCell>{t.name}</TableCell>
                <TableCell align="right">
                  {t.last_price != null ? `$${t.last_price.toFixed(2)}` : "—"}
                </TableCell>
                <TableCell align="right">
                  {t.change_percent != null ? (
                    <Box sx={{ display: "flex", alignItems: "center", justifyContent: "flex-end", gap: 0.5 }}>
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
                    "—"
                  )}
                </TableCell>
                <TableCell align="center">
                  <IconButton size="small" onClick={() => onRemove(t.symbol)} color="error">
                    <DeleteIcon fontSize="small" />
                  </IconButton>
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </TableContainer>
  );
}
