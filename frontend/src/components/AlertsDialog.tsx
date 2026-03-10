import React, { useEffect, useState } from "react";
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogContent,
  DialogTitle,
  Divider,
  FormControl,
  IconButton,
  InputLabel,
  MenuItem,
  Select,
  Switch,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import DeleteIcon from "@mui/icons-material/Delete";
import NotificationsNoneIcon from "@mui/icons-material/NotificationsNone";
import { alertsApi } from "../services/api";
import type { PriceAlert } from "../types";

interface Props {
  open: boolean;
  symbol: string;
  onClose: () => void;
}

export default function AlertsDialog({ open, symbol, onClose }: Props) {
  const [alerts, setAlerts] = useState<PriceAlert[]>([]);
  const [loading, setLoading] = useState(false);
  const [threshold, setThreshold] = useState("5");
  const [direction, setDirection] = useState<"up" | "down" | "both">("both");
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    alertsApi
      .list()
      .then((all) => setAlerts(all.filter((a) => a.symbol === symbol)))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [open, symbol]);

  const handleAdd = async () => {
    const pct = parseFloat(threshold);
    if (isNaN(pct) || pct <= 0 || pct > 100) {
      setError("Threshold must be between 0 and 100");
      return;
    }
    setError("");
    setAdding(true);
    try {
      const created = await alertsApi.create({ symbol, threshold_pct: pct, direction });
      setAlerts((prev) => [created, ...prev]);
      setThreshold("5");
      setDirection("both");
    } catch {
      setError("Failed to create alert");
    } finally {
      setAdding(false);
    }
  };

  const handleToggle = async (alert: PriceAlert) => {
    const updated = await alertsApi.update(alert.id, { is_active: !alert.is_active });
    setAlerts((prev) => prev.map((a) => (a.id === alert.id ? updated : a)));
  };

  const handleDelete = async (id: number) => {
    await alertsApi.remove(id);
    setAlerts((prev) => prev.filter((a) => a.id !== id));
  };

  const directionLabel = (d: string) => ({ up: "▲ Up", down: "▼ Down", both: "↕ Both" }[d] ?? d);

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle sx={{ display: "flex", alignItems: "center", gap: 1 }}>
        <NotificationsNoneIcon />
        Price Alerts — {symbol}
      </DialogTitle>

      <DialogContent>
        {/* Add new alert */}
        <Typography variant="subtitle2" gutterBottom>
          Add alert
        </Typography>
        <Box sx={{ display: "flex", gap: 1, alignItems: "flex-start", mb: 2 }}>
          <TextField
            label="Threshold %"
            value={threshold}
            onChange={(e) => setThreshold(e.target.value)}
            size="small"
            sx={{ width: 120 }}
            error={!!error}
            helperText={error}
            inputProps={{ min: 0.1, max: 100, step: 0.5 }}
            type="number"
          />
          <FormControl size="small" sx={{ width: 130 }}>
            <InputLabel>Direction</InputLabel>
            <Select
              value={direction}
              label="Direction"
              onChange={(e) => setDirection(e.target.value as "up" | "down" | "both")}
            >
              <MenuItem value="up">▲ Up</MenuItem>
              <MenuItem value="down">▼ Down</MenuItem>
              <MenuItem value="both">↕ Both</MenuItem>
            </Select>
          </FormControl>
          <Button
            variant="contained"
            startIcon={adding ? <CircularProgress size={14} /> : <AddIcon />}
            onClick={handleAdd}
            disabled={adding}
            sx={{ mt: 0.25 }}
          >
            Add
          </Button>
        </Box>

        <Divider sx={{ mb: 2 }} />

        {/* Existing alerts */}
        <Typography variant="subtitle2" gutterBottom>
          Active alerts
        </Typography>

        {loading && <CircularProgress size={20} />}

        {!loading && alerts.length === 0 && (
          <Typography variant="body2" color="text.secondary">
            No alerts set for {symbol}
          </Typography>
        )}

        {alerts.map((alert) => (
          <Box
            key={alert.id}
            sx={{
              display: "flex",
              alignItems: "center",
              gap: 1,
              py: 0.75,
              borderBottom: "1px solid",
              borderColor: "divider",
            }}
          >
            <Chip
              label={directionLabel(alert.direction)}
              size="small"
              variant="outlined"
              color={alert.direction === "up" ? "success" : alert.direction === "down" ? "error" : "default"}
            />
            <Typography variant="body2" sx={{ flexGrow: 1 }}>
              ≥ {alert.threshold_pct}%
            </Typography>
            {alert.triggered_at && (
              <Typography variant="caption" color="text.secondary">
                Last fired {new Date(alert.triggered_at).toLocaleDateString()}
              </Typography>
            )}
            <Tooltip title={alert.is_active ? "Active — click to pause" : "Paused — click to activate"}>
              <Switch
                size="small"
                checked={alert.is_active}
                onChange={() => handleToggle(alert)}
              />
            </Tooltip>
            <Tooltip title="Delete">
              <IconButton size="small" color="error" onClick={() => handleDelete(alert.id)}>
                <DeleteIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          </Box>
        ))}
      </DialogContent>
    </Dialog>
  );
}
