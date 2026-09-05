import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { OrderDetailsPage } from "../src/pages/OrderDetailsPage";
import { orderDetail } from "./testData";

afterEach(() => vi.unstubAllGlobals());

function setup(failSave = false) {
  let order = structuredClone(orderDetail);
  order.items.push({ ...order.items[0], id: "item-2", article_number: "UNMATCHED" });
  order.validation_issues = [{ id: "problem", field_name: "items[2].article_number", issue_type: "unknown_product", message: "Article is not in the customer catalog.", severity: "error", is_resolved: false }];
  const products = [{ id: "p1", sku: "REAL-SKU", description: "Blue chair", aliases: ["BUYER-42"], is_active: true,
    unit: "each", unit_price: "12.50", currency: "EUR", minimum_quantity: 1, warehouse: "Main", on_hand: 20, reserved: 2,
    stock_updated_at: "2026-01-01T00:00:00Z" }];
  const fetchMock = vi.fn((url: string, options?: RequestInit) => {
    if (url.endsWith("/products")) return Promise.resolve(new Response(JSON.stringify(products)));
    if (options?.method === "PATCH") {
      if (failSave) return Promise.resolve(new Response(JSON.stringify({ detail: "Cannot save this line" }), { status: 422 }));
      const payload = JSON.parse(options.body as string);
      order = { ...order, items: order.items.map(item => url.endsWith(item.id) ? { ...item, ...payload, total_price: (payload.quantity * Number(payload.unit_price)).toFixed(2) } : item), validation_issues: [] };
    }
    return Promise.resolve(new Response(JSON.stringify(order)));
  });
  vi.stubGlobal("fetch", fetchMock);
  render(<MemoryRouter initialEntries={["/orders/order-1"]}><Routes>
    <Route path="/orders/:orderId" element={<OrderDetailsPage />} />
  </Routes></MemoryRouter>);
  return fetchMock;
}

describe("Order corrections", () => {
  it("matches an alias and saves the second line without discarding the first line draft", async () => {
    const fetchMock = setup();
    fireEvent.change(await screen.findByLabelText("Quantity for line 1"), { target: { value: "7" } });
    fireEvent.change(screen.getByLabelText("Search catalog for line 2"), { target: { value: "BUYER-42" } });
    expect(await within(screen.getByLabelText("Catalog match for line 2")).findByRole("option", { name: "REAL-SKU — Blue chair" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Catalog match for line 2"), { target: { value: "p1" } });
    expect(screen.getByLabelText("Article for line 2")).toHaveValue("REAL-SKU");
    // Product matching does not silently replace extracted prices.
    expect(screen.getByLabelText("Unit price for line 2")).toHaveValue(80);
    fireEvent.click(screen.getByRole("button", { name: "Use agreed price for line 2" }));
    fireEvent.change(screen.getByLabelText("Quantity for line 2"), { target: { value: "3" } });
    expect(screen.getByLabelText("Line total for line 2")).toHaveValue(37.5);
    expect(screen.getByRole("button", { name: "Approve" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Save line 2" }));
    expect(await screen.findByText(/Line saved and validation refreshed/)).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("button", { name: "Save line 2" })).toBeDisabled());
    const request = fetchMock.mock.calls.find(([, options]) => options?.method === "PATCH");
    expect(request?.[0]).toContain("/items/item-2");
    expect(JSON.parse(request?.[1]?.body as string)).toMatchObject({ article_number: "REAL-SKU", quantity: 3, unit_price: "12.50", currency: "EUR" });
    expect(screen.getByLabelText("Quantity for line 1")).toHaveValue(7);
    expect(screen.getByRole("button", { name: "Approve" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Cancel line 1 changes" }));
    expect(screen.getByLabelText("Quantity for line 1")).toHaveValue(4);
    expect(screen.getByRole("button", { name: "Approve" })).toBeEnabled();
  });

  it("shows field-level validation and retains a failed correction", async () => {
    setup(true);
    const line = await screen.findByRole("form", { name: "Edit line 2" });
    expect(within(line).getByText("Article is not in the customer catalog.")).toBeInTheDocument();
    expect(screen.getByLabelText("Article for line 2")).toHaveAttribute("aria-invalid", "true");
    fireEvent.change(screen.getByLabelText("Article for line 2"), { target: { value: "CORRECTION" } });
    fireEvent.click(screen.getByRole("button", { name: "Save line 2" }));
    expect(await within(line).findByRole("alert")).toHaveTextContent("Cannot save this line");
    expect(screen.getByLabelText("Article for line 2")).toHaveValue("CORRECTION");
    expect(screen.getByRole("button", { name: "Save line 2" })).toBeEnabled();
  });

  it("keeps a failed header draft and lets the user cancel it", async () => {
    setup(true);
    const form = await screen.findByRole("form", { name: "Header corrections" });
    const ticket = within(form).getByLabelText("Ticket number");
    fireEvent.change(ticket, { target: { value: "CORRECTED-TICKET" } });
    expect(screen.getByRole("button", { name: "Approve" })).toBeDisabled();
    fireEvent.click(within(form).getByRole("button", { name: "Save corrections" }));
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(ticket).toHaveValue("CORRECTED-TICKET");
    fireEvent.click(within(form).getByRole("button", { name: "Cancel header changes" }));
    expect(ticket).toHaveValue("TCK-10001");
    expect(screen.getByRole("button", { name: "Approve" })).toBeEnabled();
  });
});
