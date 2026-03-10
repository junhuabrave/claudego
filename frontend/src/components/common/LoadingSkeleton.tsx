import React from "react";
import { Box, Skeleton, Stack } from "@mui/material";

export function NewsFeedSkeleton() {
  return (
    <Stack spacing={1.5}>
      {Array.from({ length: 5 }).map((_, i) => (
        <Box key={i} sx={{ p: 1.5, border: "1px solid", borderColor: "divider", borderRadius: 1 }}>
          <Skeleton variant="text" width="80%" height={20} />
          <Skeleton variant="text" width="60%" height={16} sx={{ mt: 0.5 }} />
          <Box sx={{ display: "flex", gap: 1, mt: 1 }}>
            <Skeleton variant="rounded" width={60} height={20} />
            <Skeleton variant="rounded" width={60} height={20} />
          </Box>
        </Box>
      ))}
    </Stack>
  );
}

export function WatchListSkeleton() {
  return (
    <Stack spacing={0}>
      {Array.from({ length: 4 }).map((_, i) => (
        <Box
          key={i}
          sx={{
            display: "flex",
            alignItems: "center",
            gap: 2,
            py: 1.25,
            borderBottom: "1px solid",
            borderColor: "divider",
          }}
        >
          <Skeleton variant="text" width={50} />
          <Skeleton variant="text" width={120} sx={{ flex: 1 }} />
          <Skeleton variant="text" width={60} />
          <Skeleton variant="rounded" width={60} height={22} />
        </Box>
      ))}
    </Stack>
  );
}

export function IPOCalendarSkeleton() {
  return (
    <Stack spacing={1.5}>
      {Array.from({ length: 3 }).map((_, i) => (
        <Box key={i}>
          <Skeleton variant="text" width="70%" height={20} />
          <Skeleton variant="text" width="40%" height={16} />
        </Box>
      ))}
    </Stack>
  );
}
