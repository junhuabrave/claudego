import React from "react";
import { CssBaseline, ThemeProvider, createTheme } from "@mui/material";
import Dashboard from "./pages/Dashboard";

const theme = createTheme({
  palette: {
    primary: { main: "#1565c0" },
    secondary: { main: "#f57c00" },
  },
  typography: {
    fontFamily: '"Inter", "Roboto", "Helvetica", "Arial", sans-serif',
  },
});

export default function App() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Dashboard />
    </ThemeProvider>
  );
}
