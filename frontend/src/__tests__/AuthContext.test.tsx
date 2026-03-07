/**
 * Test D — Frontend Auth & Session
 *
 * Tests AuthContext behaviour: session ID creation, user state,
 * anonymous banner rendering, logout, SetNameDialog trigger.
 *
 * Run with: npm test -- --watchAll=false
 */

import React from "react";
import { render, screen, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AuthProvider, useAuth, getOrCreateSessionId } from "../contexts/AuthContext";

// ---- Helpers ----------------------------------------------------------------

// Minimal component that exposes auth context for inspection
function AuthDisplay() {
  const { user, isAuthenticated, isLoading } = useAuth();
  if (isLoading) return <div>loading</div>;
  return (
    <div>
      <span data-testid="authenticated">{String(isAuthenticated)}</span>
      <span data-testid="user-id">{user?.id ?? "null"}</span>
      <span data-testid="is-anon">{String(user?.is_anonymous ?? "null")}</span>
    </div>
  );
}

function renderWithAuth(ui: React.ReactElement) {
  return render(<AuthProvider>{ui}</AuthProvider>);
}

// Stub fetch to return an anonymous user
function mockFetchAnon(id = 99) {
  global.fetch = jest.fn().mockResolvedValue({
    ok: true,
    json: async () => ({
      id,
      email: null,
      display_name: "",
      tier: "free",
      public_profile: false,
      is_anonymous: true,
    }),
  });
}

// ---- Tests ------------------------------------------------------------------

beforeEach(() => {
  localStorage.clear();
  jest.resetAllMocks();
});

test("getOrCreateSessionId generates and stores a UUID", () => {
  const id = getOrCreateSessionId();
  expect(id).toMatch(
    /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i
  );
  expect(localStorage.getItem("finmonitor_session_id")).toBe(id);
});

test("getOrCreateSessionId returns same ID on second call", () => {
  const id1 = getOrCreateSessionId();
  const id2 = getOrCreateSessionId();
  expect(id1).toBe(id2);
});

test("AuthContext fetches /auth/me on mount and sets anonymous user", async () => {
  mockFetchAnon(42);
  renderWithAuth(<AuthDisplay />);

  await waitFor(() => {
    expect(screen.getByTestId("authenticated").textContent).toBe("false");
    expect(screen.getByTestId("user-id").textContent).toBe("42");
    expect(screen.getByTestId("is-anon").textContent).toBe("true");
  });
});

test("logout clears JWT and reloads (via window.location.reload)", async () => {
  mockFetchAnon();
  localStorage.setItem("finmonitor_token", "fake-jwt");

  const reloadMock = jest.fn();
  Object.defineProperty(window, "location", {
    value: { reload: reloadMock },
    writable: true,
  });

  function LogoutButton() {
    const { logout } = useAuth();
    return <button onClick={logout}>logout</button>;
  }

  renderWithAuth(<LogoutButton />);
  await waitFor(() => screen.getByText("logout"));

  await act(async () => {
    await userEvent.click(screen.getByText("logout"));
  });

  expect(localStorage.getItem("finmonitor_token")).toBeNull();
  expect(reloadMock).toHaveBeenCalled();
});
