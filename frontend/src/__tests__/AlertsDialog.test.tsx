/**
 * Test F — AlertsDialog + WatchList bell icon
 *
 * Verifies alert CRUD UI, validation, and WatchList bell icon presence.
 */

import React from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import AlertsDialog from "../components/AlertsDialog";
import WatchList from "../components/WatchList";
import * as api from "../services/api";
import type { PriceAlert, Ticker } from "../types";

// ---- Helpers ----------------------------------------------------------------

const MOCK_ALERT: PriceAlert = {
  id: 1,
  symbol: "AAPL",
  threshold_pct: 5,
  direction: "up",
  is_active: true,
  triggered_at: null,
  created_at: "2026-01-01T00:00:00Z",
};

function renderDialog(symbol = "AAPL") {
  return render(<AlertsDialog open symbol={symbol} onClose={jest.fn()} />);
}

// ---- AlertsDialog tests -----------------------------------------------------

test("renders dialog title with correct symbol", async () => {
  jest.spyOn(api.alertsApi, "list").mockResolvedValue([]);
  renderDialog("MSFT");
  expect(await screen.findByText(/Price Alerts — MSFT/i)).toBeInTheDocument();
});

test("loads and displays existing alerts", async () => {
  jest.spyOn(api.alertsApi, "list").mockResolvedValue([MOCK_ALERT]);
  renderDialog("AAPL");
  expect(await screen.findByText(/≥ 5%/i)).toBeInTheDocument();
});

test("shows empty state when no alerts", async () => {
  jest.spyOn(api.alertsApi, "list").mockResolvedValue([]);
  renderDialog("AAPL");
  expect(await screen.findByText(/No alerts set for AAPL/i)).toBeInTheDocument();
});

test("add alert calls alertsApi.create with correct payload", async () => {
  jest.spyOn(api.alertsApi, "list").mockResolvedValue([]);
  const createSpy = jest.spyOn(api.alertsApi, "create").mockResolvedValue({
    ...MOCK_ALERT,
    id: 2,
    threshold_pct: 10,
    direction: "both",
  });

  renderDialog("AAPL");
  await screen.findByText(/No alerts set/i);

  // Clear default value and type new threshold
  const input = screen.getByLabelText(/Threshold %/i);
  fireEvent.change(input, { target: { value: "10" } });

  fireEvent.click(screen.getByRole("button", { name: /Add/i }));

  await waitFor(() => {
    expect(createSpy).toHaveBeenCalledWith(
      expect.objectContaining({ symbol: "AAPL", threshold_pct: 10 })
    );
  });
});

test("shows error for threshold > 100", async () => {
  jest.spyOn(api.alertsApi, "list").mockResolvedValue([]);
  renderDialog();
  await screen.findByLabelText(/Threshold %/i);

  fireEvent.change(screen.getByLabelText(/Threshold %/i), { target: { value: "999" } });
  fireEvent.click(screen.getByRole("button", { name: /Add/i }));

  expect(screen.getByText(/must be between/i)).toBeInTheDocument();
});

test("delete alert calls alertsApi.remove", async () => {
  jest.spyOn(api.alertsApi, "list").mockResolvedValue([MOCK_ALERT]);
  const removeSpy = jest.spyOn(api.alertsApi, "remove").mockResolvedValue(undefined);

  renderDialog("AAPL");
  await screen.findByText(/≥ 5%/i);

  fireEvent.click(screen.getAllByRole("button", { name: /Delete/i })[0]);
  expect(removeSpy).toHaveBeenCalledWith(1);
});

// ---- WatchList bell icon test -----------------------------------------------

const MOCK_TICKER: Ticker = {
  id: 1,
  symbol: "AAPL",
  name: "Apple Inc.",
  exchange: "NASDAQ",
  last_price: 150,
  change_percent: 1.5,
  active: true,
  created_at: "2026-01-01T00:00:00Z",
};

test("WatchList renders bell icon button for each ticker", () => {
  const onManageAlerts = jest.fn();
  render(
    <WatchList
      tickers={[MOCK_TICKER]}
      onRemove={jest.fn()}
      onSelectSymbol={jest.fn()}
      onManageAlerts={onManageAlerts}
    />
  );
  // MUI Tooltip sets aria-label on the child button, not a title attribute
  const bellButtons = screen.getAllByRole("button", { name: /manage alerts/i });
  expect(bellButtons).toHaveLength(1);
});

test("clicking bell icon calls onManageAlerts with correct symbol", () => {
  const onManageAlerts = jest.fn();
  render(
    <WatchList
      tickers={[MOCK_TICKER]}
      onRemove={jest.fn()}
      onSelectSymbol={jest.fn()}
      onManageAlerts={onManageAlerts}
    />
  );
  fireEvent.click(screen.getByRole("button", { name: /manage alerts/i }));
  expect(onManageAlerts).toHaveBeenCalledWith("AAPL");
});
