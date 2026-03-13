import React from "react";
import { Box, Card, CardContent, Chip, Link, List, ListItem, Typography } from "@mui/material";
import OpenInNewIcon from "@mui/icons-material/OpenInNew";
import { List as VirtualList, RowComponentProps } from "react-window";
import { useTranslation } from "react-i18next";
import type { NewsArticle } from "../types";

interface Props {
  articles: NewsArticle[];
  /** Container height in px for virtualized list. Default 500. */
  listHeight?: number;
}

// Virtualize when article count exceeds this threshold.
const VIRTUALIZE_THRESHOLD = 15;
// Estimated height per article card (headline + 2-line summary + chips + padding).
const ITEM_HEIGHT = 130;

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

function ArticleCard({ article }: { article: NewsArticle }) {
  return (
    <Card variant="outlined" sx={{ width: "100%" }}>
      <CardContent sx={{ py: 1.5, "&:last-child": { pb: 1.5 } }}>
        <Box sx={{ flex: 1 }}>
          <Link
            href={article.url}
            target="_blank"
            rel="noopener noreferrer"
            underline="hover"
            color="inherit"
            sx={{ fontWeight: 600, fontSize: "0.95rem" }}
            aria-label={`${article.headline} (opens in new tab)`}
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
        <Box sx={{ display: "flex", gap: 1, mt: 1, alignItems: "center", flexWrap: "wrap" }}>
          <Chip label={article.source} size="small" variant="outlined" />
          <Chip
            label={article.sentiment}
            size="small"
            color={sentimentColor(article.sentiment)}
          />
          {article.related_tickers && (
            <Chip
              label={article.related_tickers}
              size="small"
              color="primary"
              variant="outlined"
            />
          )}
          <Typography variant="caption" color="text.secondary" sx={{ ml: "auto" }}>
            {timeAgo(article.published_at)}
          </Typography>
        </Box>
      </CardContent>
    </Card>
  );
}

interface NewsRowProps {
  articles: NewsArticle[];
}

function VirtualRow({ index, style, articles }: RowComponentProps<NewsRowProps>) {
  return (
    <div style={{ ...style, paddingBottom: 8, boxSizing: "border-box" }}>
      <ArticleCard article={articles[index]} />
    </div>
  );
}

export default function NewsFeed({ articles, listHeight = 500 }: Props) {
  const { t } = useTranslation();

  if (!articles.length) {
    return (
      <Typography color="text.secondary" sx={{ p: 2 }}>
        {t("news.empty")}
      </Typography>
    );
  }

  // Small lists: plain rendering with no virtualization overhead.
  if (articles.length <= VIRTUALIZE_THRESHOLD) {
    return (
      <List disablePadding aria-label={t("news.ariaLabel")}>
        {articles.map((article) => (
          <ListItem key={article.id} disablePadding sx={{ mb: 1 }}>
            <ArticleCard article={article} />
          </ListItem>
        ))}
      </List>
    );
  }

  // Large lists (>15 articles): virtualized for smooth scrolling.
  return (
    <Box
      sx={{ height: listHeight, overflow: "hidden" }}
      role="list"
      aria-label={t("news.ariaLabel")}
    >
      <VirtualList
        style={{ width: "100%" }}
        rowCount={articles.length}
        rowHeight={ITEM_HEIGHT}
        rowComponent={VirtualRow}
        rowProps={{ articles }}
        overscanCount={3}
      />
    </Box>
  );
}
