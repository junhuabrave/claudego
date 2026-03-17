import React, { useState } from "react";
import {
  Avatar,
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  IconButton,
  Menu,
  MenuItem,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import { GoogleLogin, CredentialResponse } from "@react-oauth/google";
import { useAuth } from "../contexts/AuthContext";

export default function UserMenu() {
  const { user, isAuthenticated, login, logout, refreshUser } = useAuth();
  const [anchor, setAnchor] = useState<null | HTMLElement>(null);
  const [renaming, setRenaming] = useState(false);
  const [newName, setNewName] = useState("");
  const [loginError, setLoginError] = useState(false);

  const apiUrl = import.meta.env.VITE_API_URL || "https://localhost:3443/api";

  const handleGoogleSuccess = async (credentialResponse: CredentialResponse) => {
    if (!credentialResponse.credential) return;
    try {
      await login(credentialResponse.credential);
    } catch {
      setLoginError(true);
    }
  };

  const handleRename = async () => {
    if (!newName.trim()) return;
    const token = localStorage.getItem("finmonitor_token");
    await fetch(`${apiUrl}/auth/me`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ display_name: newName.trim() }),
    });
    await refreshUser();
    setRenaming(false);
    setNewName("");
  };

  if (!isAuthenticated) {
    return (
      <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
        {loginError && (
          <Typography variant="caption" color="error">
            Login failed
          </Typography>
        )}
        <GoogleLogin
          onSuccess={handleGoogleSuccess}
          onError={() => setLoginError(true)}
          size="medium"
          shape="pill"
          text="signin_with"
        />
      </Box>
    );
  }

  const initials = user?.display_name
    ? user.display_name.charAt(0).toUpperCase()
    : user?.email?.charAt(0).toUpperCase() ?? "?";

  return (
    <>
      <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
        {user?.tier === "premium" && (
          <Chip label="Premium" size="small" color="warning" variant="outlined" />
        )}
        <Tooltip title={user?.display_name || user?.email || "Account"}>
          <IconButton onClick={(e) => setAnchor(e.currentTarget)} sx={{ p: 0.5 }}>
            <Avatar sx={{ width: 32, height: 32, bgcolor: "secondary.main", fontSize: 14 }}>
              {initials}
            </Avatar>
          </IconButton>
        </Tooltip>
      </Box>

      <Menu
        anchorEl={anchor}
        open={Boolean(anchor)}
        onClose={() => setAnchor(null)}
        transformOrigin={{ horizontal: "right", vertical: "top" }}
        anchorOrigin={{ horizontal: "right", vertical: "bottom" }}
      >
        <Box sx={{ px: 2, py: 1 }}>
          <Typography variant="subtitle2">
            {user?.display_name || "(no name set)"}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            {user?.email}
          </Typography>
        </Box>
        <Divider />
        <MenuItem
          onClick={() => {
            setAnchor(null);
            setNewName(user?.display_name ?? "");
            setRenaming(true);
          }}
        >
          Change display name
        </MenuItem>
        <MenuItem
          onClick={() => {
            setAnchor(null);
            logout();
          }}
          sx={{ color: "error.main" }}
        >
          Sign out
        </MenuItem>
      </Menu>

      {/* Rename dialog */}
      <Dialog open={renaming} onClose={() => setRenaming(false)} maxWidth="xs" fullWidth>
        <DialogTitle>Change display name</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            fullWidth
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleRename()}
            inputProps={{ maxLength: 50 }}
            sx={{ mt: 1 }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setRenaming(false)}>Cancel</Button>
          <Button onClick={handleRename} variant="contained" disabled={!newName.trim()}>
            Save
          </Button>
        </DialogActions>
      </Dialog>

    </>
  );
}
