import React, { useState } from "react";
import {
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  TextField,
  Typography,
} from "@mui/material";
import { useAuth } from "../contexts/AuthContext";

const API_URL = import.meta.env.VITE_API_URL || "https://localhost:3443/api";

interface Props {
  open: boolean;
  onClose: () => void;
}

export default function SetNameDialog({ open, onClose }: Props) {
  const { refreshUser } = useAuth();
  const [name, setName] = useState("");
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    if (!name.trim()) return;
    setSaving(true);
    try {
      const token = localStorage.getItem("finmonitor_token");
      await fetch(`${API_URL}/auth/me`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ display_name: name.trim() }),
      });
      await refreshUser();
      onClose();
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} maxWidth="xs" fullWidth>
      <DialogTitle>Welcome! Pick a display name</DialogTitle>
      <DialogContent>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          This is how you&apos;ll appear in the app. You can change it later.
        </Typography>
        <TextField
          autoFocus
          fullWidth
          label="Display name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSave()}
          inputProps={{ maxLength: 50 }}
        />
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={saving}>
          Skip
        </Button>
        <Button onClick={handleSave} variant="contained" disabled={!name.trim() || saving}>
          Save
        </Button>
      </DialogActions>
    </Dialog>
  );
}
