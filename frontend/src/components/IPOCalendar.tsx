import React, { useState } from "react";
import {
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  TextField,
  Typography,
} from "@mui/material";
import NotificationsIcon from "@mui/icons-material/Notifications";
import EventIcon from "@mui/icons-material/Event";
import type { IPOEvent } from "../types";
import { createReminder } from "../services/api";

interface Props {
  ipos: IPOEvent[];
}

export default function IPOCalendar({ ipos }: Props) {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [selectedIPO, setSelectedIPO] = useState<IPOEvent | null>(null);
  const [notifyVia, setNotifyVia] = useState<string>("email");
  const [notifyAddress, setNotifyAddress] = useState("");
  const [remindHours, setRemindHours] = useState(24);
  const [submitting, setSubmitting] = useState(false);

  const handleSetReminder = (ipo: IPOEvent) => {
    setSelectedIPO(ipo);
    setDialogOpen(true);
  };

  const handleSubmitReminder = async () => {
    if (!selectedIPO || !notifyAddress) return;
    setSubmitting(true);
    try {
      await createReminder({
        ipo_event_id: selectedIPO.id,
        notify_via: notifyVia,
        notify_address: notifyAddress,
        remind_before_hours: remindHours,
      });
      setDialogOpen(false);
      setNotifyAddress("");
    } catch {
      // handle error
    } finally {
      setSubmitting(false);
    }
  };

  if (!ipos.length) {
    return (
      <Typography color="text.secondary" sx={{ p: 2 }}>
        No upcoming IPOs found. Data will appear once the backend starts polling.
      </Typography>
    );
  }

  return (
    <>
      <Box sx={{ display: "flex", flexDirection: "column", gap: 1 }}>
        {ipos.map((ipo) => (
          <Card key={ipo.id} variant="outlined">
            <CardContent sx={{ py: 1.5, "&:last-child": { pb: 1.5 } }}>
              <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <Box>
                  <Typography fontWeight={600}>
                    {ipo.company_name}
                    {ipo.symbol && (
                      <Chip label={ipo.symbol} size="small" color="primary" sx={{ ml: 1 }} />
                    )}
                  </Typography>
                  <Box sx={{ display: "flex", gap: 1, mt: 0.5, flexWrap: "wrap" }}>
                    <Chip
                      icon={<EventIcon />}
                      label={ipo.expected_date}
                      size="small"
                      variant="outlined"
                    />
                    {ipo.exchange && <Chip label={ipo.exchange} size="small" variant="outlined" />}
                    {ipo.price_range && (
                      <Chip label={`$${ipo.price_range}`} size="small" variant="outlined" />
                    )}
                    <Chip label={ipo.status} size="small" color="info" />
                  </Box>
                </Box>
                <Button
                  variant="outlined"
                  size="small"
                  startIcon={<NotificationsIcon />}
                  onClick={() => handleSetReminder(ipo)}
                >
                  Remind
                </Button>
              </Box>
            </CardContent>
          </Card>
        ))}
      </Box>

      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Set Reminder - {selectedIPO?.company_name}</DialogTitle>
        <DialogContent>
          <Box sx={{ display: "flex", flexDirection: "column", gap: 2, mt: 1 }}>
            <FormControl fullWidth size="small">
              <InputLabel>Notify via</InputLabel>
              <Select
                value={notifyVia}
                label="Notify via"
                onChange={(e) => setNotifyVia(e.target.value)}
              >
                <MenuItem value="email">Email</MenuItem>
                <MenuItem value="pagerduty">PagerDuty</MenuItem>
              </Select>
            </FormControl>
            <TextField
              label={notifyVia === "email" ? "Email address" : "PagerDuty routing key"}
              value={notifyAddress}
              onChange={(e) => setNotifyAddress(e.target.value)}
              size="small"
              fullWidth
            />
            <FormControl fullWidth size="small">
              <InputLabel>Remind before</InputLabel>
              <Select
                value={remindHours}
                label="Remind before"
                onChange={(e) => setRemindHours(Number(e.target.value))}
              >
                <MenuItem value={1}>1 hour</MenuItem>
                <MenuItem value={6}>6 hours</MenuItem>
                <MenuItem value={24}>1 day</MenuItem>
                <MenuItem value={48}>2 days</MenuItem>
              </Select>
            </FormControl>
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            onClick={handleSubmitReminder}
            disabled={!notifyAddress || submitting}
          >
            {submitting ? "Saving..." : "Set Reminder"}
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}
