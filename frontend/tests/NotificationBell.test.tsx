import { act, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { NotificationBell } from "../src/components/layout/NotificationBell";

afterEach(() => vi.unstubAllGlobals());
it("refreshes unread count and reports unavailable counts without claiming zero", async () => {
  let failed = false;
  vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(new Response(JSON.stringify(failed ? { detail: "Unavailable" } :
    { unread_count: 3 }), { status: failed ? 500 : 200 }))));
  render(<MemoryRouter><NotificationBell /></MemoryRouter>);
  expect(await screen.findByRole("link", { name: "Notifications, 3 unread" })).toHaveAttribute("href", "/notifications");
  failed = true;
  await act(async () => window.dispatchEvent(new Event("notifications-changed")));
  expect(await screen.findByRole("link", { name: "Notifications unavailable" })).toBeInTheDocument();
});
