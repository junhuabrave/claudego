import React, { useCallback, useMemo, useRef, useState } from "react";
import {
  Box,
  IconButton,
  List,
  ListItem,
  Paper,
  TextField,
  Typography,
} from "@mui/material";
import SendIcon from "@mui/icons-material/Send";
import { useTranslation } from "react-i18next";
import { sendChatMessage } from "../services/api";

interface Message {
  id: number;
  text: string;
  from: "user" | "bot";
}

interface Props {
  onTickerChanged: () => void;
  onOptimisticMutation?: (action: "add" | "remove", symbol: string) => void;
}

// Mirrors backend: app/services/chat.py  r"(\^?[a-zA-Z0-9][\w.-]{0,14})"
// Supports: AAPL, ^KS11, VOD.L, 005930.KS
const TICKER_RE = /^\^?[A-Z0-9][\w.-]{0,14}$/i;

const ADD_RE = /^(?:add|watch|track|follow)\s+(\S+)/i;
const REMOVE_RE = /^(?:remove|delete|unwatch|untrack|unfollow|drop)\s+(\S+)/i;

/** Extract the ticker token from an add/remove command, or null if not an add/remove. */
function extractTicker(text: string): string | null {
  const m = text.match(
    /^(?:add|watch|track|follow|remove|delete|unwatch|untrack|unfollow|drop)\s+(\S+)/i
  );
  return m ? m[1] : null;
}

/** Detect the mutation intent of a command before sending to the API. */
function detectIntent(text: string): { action: "add" | "remove"; symbol: string } | null {
  const add = text.match(ADD_RE);
  if (add) return { action: "add", symbol: add[1].toUpperCase() };
  const remove = text.match(REMOVE_RE);
  if (remove) return { action: "remove", symbol: remove[1].toUpperCase() };
  return null;
}

export default function ChatBox({ onTickerChanged, onOptimisticMutation }: Props) {
  const { t } = useTranslation();

  const [messages, setMessages] = useState<Message[]>([
    { id: 0, text: t("chat.welcome"), from: "bot" },
  ]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const listRef = useRef<HTMLUListElement>(null);
  const nextId = useRef(1);

  const tickerError = useMemo<string | null>(() => {
    const ticker = extractTicker(input.trim());
    if (ticker && !TICKER_RE.test(ticker)) {
      return `"${ticker}" doesn't look like a valid symbol`;
    }
    return null;
  }, [input]);

  const scrollToBottom = useCallback(() => {
    setTimeout(() => {
      if (listRef.current) {
        listRef.current.scrollTop = listRef.current.scrollHeight;
      }
    }, 50);
  }, []);

  const handleSend = async () => {
    const text = input.trim();
    if (!text || sending || tickerError) return;

    const userMsg: Message = { id: nextId.current++, text, from: "user" };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setSending(true);
    scrollToBottom();

    // Fire optimistic update immediately — before the API round-trip.
    const intent = detectIntent(text);
    if (intent && onOptimisticMutation) {
      onOptimisticMutation(intent.action, intent.symbol);
    }

    try {
      const resp = await sendChatMessage(text);
      const botMsg: Message = { id: nextId.current++, text: resp.reply, from: "bot" };
      setMessages((prev) => [...prev, botMsg]);
      if (resp.action === "add_ticker" || resp.action === "remove_ticker") {
        onTickerChanged();
      }
    } catch {
      const errMsg: Message = {
        id: nextId.current++,
        text: t("chat.error"),
        from: "bot",
      };
      setMessages((prev) => [...prev, errMsg]);
      // Resync cache to roll back any optimistic update made above.
      if (intent) onTickerChanged();
    } finally {
      setSending(false);
      scrollToBottom();
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <Box sx={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <List
        ref={listRef}
        aria-label={t("chat.title")}
        aria-live="polite"
        sx={{ flex: 1, overflow: "auto", p: 1, minHeight: 200, maxHeight: 350 }}
      >
        {messages.map((msg) => (
          <ListItem
            key={msg.id}
            sx={{ justifyContent: msg.from === "user" ? "flex-end" : "flex-start", px: 0 }}
          >
            <Paper
              elevation={0}
              sx={{
                px: 2,
                py: 1,
                maxWidth: "80%",
                bgcolor: msg.from === "user" ? "primary.main" : "grey.100",
                color: msg.from === "user" ? "primary.contrastText" : "text.primary",
                borderRadius: 2,
              }}
            >
              <Typography variant="body2" sx={{ whiteSpace: "pre-wrap" }}>
                {msg.text}
              </Typography>
            </Paper>
          </ListItem>
        ))}
      </List>

      <Box sx={{ display: "flex", gap: 1, p: 1, borderTop: 1, borderColor: "divider" }}>
        <TextField
          fullWidth
          size="small"
          placeholder={t("chat.placeholder")}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={sending}
          error={!!tickerError}
          helperText={tickerError}
          inputProps={{ "aria-label": t("chat.placeholder") }}
        />
        <IconButton
          color="primary"
          onClick={handleSend}
          disabled={!input.trim() || sending || !!tickerError}
          aria-label={t("chat.sendAriaLabel")}
        >
          <SendIcon />
        </IconButton>
      </Box>
    </Box>
  );
}
