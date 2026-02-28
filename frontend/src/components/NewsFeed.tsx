import React from "react";
import {
  Box,
  Card,
  CardContent,
  Chip,
  Link,
  List,
  ListItem,
  Typography,
} from "@mui/material";
import OpenInNewIcon from "@mui/icons-material/OpenInNew";
import type { NewsArticle } from "../types";

interface Props {
  articles: NewsArticle[];
}

function sentimentColor(s: string): "success" | "error" | "default" {
  if (s === "positive") return "success";
  if (s === "negative") return "error";
  return "default";
}

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

export default function NewsFeed({ articles }: Props) {
  if (!articles.length) {
    return (
      <Typography color="text.secondary" sx={{ p: 2 }}>
        No news articles yet. Data will appear once the backend starts polling.
      </Typography>
    );
  }

  return (
    <List disablePadding>
      {articles.map((article) => (
        <ListItem key={article.id} disablePadding sx={{ mb: 1 }}>
          <Card variant="outlined" sx={{ width: "100%" }}>
            <CardContent sx={{ py: 1.5, "&:last-child": { pb: 1.5 } }}>
              <Box
                sx={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "flex-start",
                  gap: 1,
                }}
              >
                <Box sx={{ flex: 1 }}>
                  <Link
                    href={article.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    underline="hover"
                    color="inherit"
                    sx={{ fontWeight: 600, fontSize: "0.95rem" }}
                  >
                    {article.headline}
                    <OpenInNewIcon sx={{ fontSize: 14, ml: 0.5, verticalAlign: "middle" }} />
                  </Link>
                  {article.summary && (
                    <Typography
                      variant="body2"
                      color="text.secondary"
                      sx={{
                        mt: 0.5,
                        display: "-webkit-box",
                        WebkitLineClamp: 2,
                        WebkitBoxOrient: "vertical",
                        overflow: "hidden",
                      }}
                    >
                      {article.summary}
                    </Typography>
                  )}
                </Box>
              </Box>
              <Box sx={{ display: "flex", gap: 1, mt: 1, alignItems: "center", flexWrap: "wrap" }}>
                <Chip label={article.source} size="small" variant="outlined" />
                <Chip
                  label={article.sentiment}
                  size="small"
                  color={sentimentColor(article.sentiment)}
                />
                {article.related_tickers && (
                  <Chip label={article.related_tickers} size="small" color="primary" variant="outlined" />
                )}
                <Typography variant="caption" color="text.secondary" sx={{ ml: "auto" }}>
                  {timeAgo(article.published_at)}
                </Typography>
              </Box>
            </CardContent>
          </Card>
        </ListItem>
      ))}
    </List>
  );
}
