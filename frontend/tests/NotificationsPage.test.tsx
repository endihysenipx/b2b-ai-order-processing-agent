import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { NotificationsPage } from "../src/pages/NotificationsPage";

const item = { order_id: "o", reference: "PO-42", client_name: "Test customer", category: "failed", title: "Processing failed",
  message: "Review the order", status: "Failed", is_demo: false, updated_at: "2026-09-06T09:00:00Z", fingerprint: "a".repeat(64), is_read: false };
afterEach(() => vi.unstubAllGlobals());

it("links the order and saves read state without changing the order", async () => {
  let read = false;
  const fetcher = vi.fn((url: string, options?: RequestInit) => {
    if (options?.method === "PUT") { read = true; return Promise.resolve(new Response(JSON.stringify({ is_read: true }))); }
    return Promise.resolve(new Response(JSON.stringify({ items: [{ ...item, is_read: read }], total: 1, unread_count: read ? 0 : 1, page: 1, page_size: 20 })));
  });
  vi.stubGlobal("fetch", fetcher);
  render(<MemoryRouter><NotificationsPage /></MemoryRouter>);
  expect(await screen.findByRole("link", { name: "PO-42" })).toHaveAttribute("href", "/orders/o");
  fireEvent.click(screen.getByRole("button", { name: "Mark read" }));
  expect(await screen.findByRole("button", { name: "Mark unread" })).toBeInTheDocument();
  expect(fetcher.mock.calls.some(([url, options]) => url.endsWith("/notifications/o/read") && options?.method === "PUT")).toBe(true);
  fireEvent.change(screen.getByLabelText("Category"), { target: { value: "duplicate" } });
  await waitFor(() => expect(fetcher.mock.calls.some(([url]) => url.includes("category=duplicate") && url.includes("page=1"))).toBe(true));
});

it("reports a load failure and can retry to an empty inbox", async () => {
  let failed = true;
  vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(new Response(JSON.stringify(failed ? { detail: "Unavailable" } :
    { items: [], total: 0, unread_count: 0, page: 1, page_size: 20 }), { status: failed ? 500 : 200 }))));
  render(<MemoryRouter><NotificationsPage /></MemoryRouter>);
  expect(await screen.findByRole("alert")).toHaveTextContent("Unavailable");
  failed = false;
  fireEvent.click(screen.getByRole("button", { name: "Refresh" }));
  expect(await screen.findByText("No notifications match these filters.")).toBeInTheDocument();
});
