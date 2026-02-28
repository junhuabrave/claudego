import React from "react";
import { Box, Chip } from "@mui/material";
import FiberManualRecordIcon from "@mui/icons-material/FiberManualRecord";

interface Props {
  wsConnected: boolean;
  tickerCount: number;
  newsCount: number;
}

export default function StatusBar({ wsConnected, tickerCount, newsCount }: Props) {
  return (
    <Box sx={{ display: "flex", gap: 1, alignItems: "center" }}>
      <Chip
        icon={<FiberManualRecordIcon sx={{ fontSize: 12 }} />}
        label={wsConnected ? "Live" : "Disconnected"}
        size="small"
        color={wsConnected ? "success" : "error"}
        variant="outlined"
      />
      <Chip label={`${tickerCount} tickers`} size="small" variant="outlined" />
      <Chip label={`${newsCount} articles`} size="small" variant="outlined" />
    </Box>
  );
}
