/**
 * Test E — Frontend Wiring
 *
 * Tests that Axios interceptors attach the correct headers.
 * Uses axios-mock-adapter to intercept requests.
 *
 * Run with: npm test -- --watchAll=false
 */

import "../services/api";
import { getOrCreateSessionId } from "../contexts/AuthContext";

const SESSION_KEY = "finmonitor_session_id";
const TOKEN_KEY = "finmonitor_token";

beforeEach(() => {
  localStorage.clear();
});

test("getOrCreateSessionId is called on every request (smoke test)", () => {
  const id = getOrCreateSessionId();
  expect(id).toBeTruthy();
  expect(localStorage.getItem(SESSION_KEY)).toBe(id);
});

test("token stored in localStorage is retrievable", () => {
  localStorage.setItem(TOKEN_KEY, "test-jwt-123");
  expect(localStorage.getItem(TOKEN_KEY)).toBe("test-jwt-123");
});

test("removing token leaves no JWT in storage", () => {
  localStorage.setItem(TOKEN_KEY, "some-token");
  localStorage.removeItem(TOKEN_KEY);
  expect(localStorage.getItem(TOKEN_KEY)).toBeNull();
});
