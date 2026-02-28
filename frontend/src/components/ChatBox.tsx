import React, { useCallback, useRef, useState } from "react";
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
import { sendChatMessage } from "../services/api";

interface Message {
  id: number;
  text: string;
  from: "user" | "bot";
}

interface Props {
  onTickerChanged: () => void;
}

export default function ChatBox({ onTickerChanged }: Props) {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 0,
      text: "Hi! I can help manage your watchlist. Try 'add AAPL', 'remove TSLA', or 'list'. Type 'help' for all commands.",
      from: "bot",
    },
  ]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const listRef = useRef<HTMLUListElement>(null);
  const nextId = useRef(1);

  const scrollToBottom = useCallback(() => {
    setTimeout(() => {
      if (listRef.current) {
        listRef.current.scrollTop = listRef.current.scrollHeight;
      }
    }, 50);
  }, []);

  const handleSend = async () => {
    const text = input.trim();
    if (!text || sending) return;

    const userMsg: Message = { id: nextId.current++, text, from: "user" };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setSending(true);
    scrollToBottom();

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
        text: "Sorry, something went wrong. Please try again.",
        from: "bot",
      };
      setMessages((prev) => [...prev, errMsg]);
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
        sx={{
          flex: 1,
          overflow: "auto",
          p: 1,
          minHeight: 200,
          maxHeight: 350,
        }}
      >
        {messages.map((msg) => (
          <ListItem
            key={msg.id}
            sx={{
              justifyContent: msg.from === "user" ? "flex-end" : "flex-start",
              px: 0,
            }}
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
          placeholder="Type a command (e.g., add AAPL)..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={sending}
        />
        <IconButton color="primary" onClick={handleSend} disabled={!input.trim() || sending}>
          <SendIcon />
        </IconButton>
      </Box>
    </Box>
  );
}
