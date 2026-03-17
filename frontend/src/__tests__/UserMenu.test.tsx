/**
 * Test E — UserMenu component
 *
 * Verifies that UserMenu shows Google sign-in button when anonymous
 * and shows avatar + display name when authenticated.
 */

import React from "react";
import { render, screen } from "@testing-library/react";
import { GoogleOAuthProvider } from "@react-oauth/google";
import UserMenu from "../components/UserMenu";
import * as AuthContext from "../contexts/AuthContext";

vi.mock("@react-oauth/google", () => ({
  GoogleOAuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  GoogleLogin: ({ onSuccess }: { onSuccess: (r: { credential: string }) => void }) => (
    <button data-testid="google-login-btn" onClick={() => onSuccess({ credential: "fake" })}>
      Sign in with Google
    </button>
  ),
}));

function renderMenu(overrides: Partial<AuthContext.AuthContextValue> = {}) {
  const defaults: AuthContext.AuthContextValue = {
    user: null,
    isAuthenticated: false,
    isLoading: false,
    login: vi.fn(),
    logout: vi.fn(),
    refreshUser: vi.fn(),
  };
  vi.spyOn(AuthContext, "useAuth").mockReturnValue({ ...defaults, ...overrides });

  return render(
    <GoogleOAuthProvider clientId="test-client-id">
      <UserMenu />
    </GoogleOAuthProvider>
  );
}

afterEach(() => vi.restoreAllMocks());

test("shows Google sign-in button when anonymous", () => {
  renderMenu({ isAuthenticated: false, user: null });
  expect(screen.getByTestId("google-login-btn")).toBeInTheDocument();
});

test("shows avatar with initials when authenticated", () => {
  renderMenu({
    isAuthenticated: true,
    user: {
      id: 1,
      email: "alice@example.com",
      display_name: "Alice",
      tier: "free",
      public_profile: false,
      is_anonymous: false,
    },
  });
  // Avatar shows first letter of display name
  expect(screen.getByText("A")).toBeInTheDocument();
  // No sign-in button
  expect(screen.queryByTestId("google-login-btn")).toBeNull();
});

test("shows Premium chip when tier is premium", () => {
  renderMenu({
    isAuthenticated: true,
    user: {
      id: 2,
      email: "bob@example.com",
      display_name: "Bob",
      tier: "premium",
      public_profile: false,
      is_anonymous: false,
    },
  });
  expect(screen.getByText("Premium")).toBeInTheDocument();
});
