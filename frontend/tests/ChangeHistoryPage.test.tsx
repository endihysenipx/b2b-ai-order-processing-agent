import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ChangeHistoryPage } from "../src/pages/ChangeHistoryPage";

afterEach(() => vi.unstubAllGlobals());

const entry = {
  id: "audit-1", created_at: "2026-09-05T12:00:00Z", actor_id: "user-1", actor_name: "Alex Operator",
  client_id: "client-1", client_name: "Test customer", entity_type: "product", entity_id: "product-1",
  entity_label: "SKU-001", order_id: null, action: "product_updated", batch_id: null,
  changes: { unit_price: { before: "10.00", after: "12.50" }, on_hand: { before: 20, after: 15 } },
};

describe("Change history", () => {
  it("shows the actor and before/after values, and applies filters with pagination reset", async () => {
    const fetchMock = vi.fn((url: string) => Promise.resolve(new Response(JSON.stringify(url.endsWith("/clients")
      ? [{ id: "client-1", client_name: "Test customer" }]
      : { items: [entry], total: 1, page: 1, page_size: 20 }))));
    vi.stubGlobal("fetch", fetchMock);
    render(<MemoryRouter initialEntries={["/history?page=2"]}><ChangeHistoryPage /></MemoryRouter>);
    expect(await screen.findByText("Alex Operator")).toBeInTheDocument();
    fireEvent.click(screen.getByText("View 2 changed fields"));
    expect(screen.getByText("10.00")).toBeInTheDocument();
    expect(screen.getByText("12.50")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Changed by"), { target: { value: "Alex" } });
    fireEvent.change(screen.getByLabelText("Record type"), { target: { value: "product" } });
    fireEvent.click(screen.getByRole("button", { name: "Apply filters" }));
    await waitFor(() => expect(fetchMock.mock.calls.some(([url]) => url.includes("actor=Alex") && url.includes("entity_type=product") && !url.includes("page=2"))).toBe(true));
  });

  it("handles empty history without implying older changes were reconstructed", async () => {
    vi.stubGlobal("fetch", vi.fn((url: string) => Promise.resolve(new Response(JSON.stringify(url.endsWith("/clients")
      ? [] : { items: [], total: 0, page: 1, page_size: 20 })))));
    render(<MemoryRouter><ChangeHistoryPage /></MemoryRouter>);
    expect(await screen.findByText("No changes match these filters.")).toBeInTheDocument();
    expect(screen.getByText(/earlier changes are not reconstructed/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Next page" })).toBeDisabled();
  });

  it("shows a failed history request and allows refresh", async () => {
    vi.stubGlobal("fetch", vi.fn((url: string) => Promise.resolve(new Response(JSON.stringify(url.endsWith("/clients")
      ? [] : { detail: "History unavailable" }), { status: url.endsWith("/clients") ? 200 : 503 }))));
    render(<MemoryRouter><ChangeHistoryPage /></MemoryRouter>);
    expect(await screen.findByRole("alert")).toHaveTextContent("History unavailable");
    expect(screen.getByRole("button", { name: "Refresh history" })).toBeEnabled();
  });
});
