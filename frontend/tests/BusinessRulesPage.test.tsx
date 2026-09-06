import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { BusinessRulesPage } from "../src/pages/BusinessRulesPage";

const rules = { currency: "EUR", freight_enabled: true, freight_below: "500", freight_charge: "35", discount_enabled: false,
  discount_from: "1000", discount_percent: "5", minimum_enabled: false, minimum_order: "250", review_enabled: false, review_from: "2500" };
const terms = { currency: "EUR", subtotal: "420.00", discount: "0.00", freight: "35.00", total: "455.00", enabled: true,
  applied: ["Freight below 500"], blockers: [], review_required: false };
afterEach(() => { vi.unstubAllGlobals(); sessionStorage.clear(); });

it("previews unsaved rules and saves the selected client only", async () => {
  sessionStorage.setItem("auth_user", JSON.stringify({ role: "admin" }));
  const fetcher = vi.fn((url: string, options?: RequestInit) => {
    let result: unknown = [];
    if (url.endsWith("/business-rules")) result = [{ client_id: "one", client_name: "Alpine", is_active: true, rules }];
    if (url.endsWith("/preview")) result = terms;
    if (options?.method === "PUT") result = { updated_orders: 1 };
    return Promise.resolve(new Response(JSON.stringify(result)));
  });
  vi.stubGlobal("fetch", fetcher);
  render(<MemoryRouter><BusinessRulesPage /></MemoryRouter>);
  expect(await screen.findByLabelText("Freight charge")).toHaveValue(35);
  fireEvent.change(screen.getByLabelText("Freight charge"), { target: { value: "40" } });
  expect(screen.getByText(/Previewing unsaved rules/)).toBeInTheDocument();
  await screen.findByText("455.00 EUR");
  expect(fetcher.mock.calls.some(([, options]) => options?.method === "PUT")).toBe(false);
  fireEvent.click(screen.getByRole("button", { name: "Save client rules" }));
  await waitFor(() => expect(fetcher.mock.calls.some(([url, options]) => url.endsWith("/clients/one") &&
    options?.method === "PUT" && JSON.parse(String(options.body)).freight_charge === "40")).toBe(true));
  expect(await screen.findByRole("status")).toHaveTextContent("1 unsent order(s) recalculated");
});

it("shows a read-only editor to non-admin users", async () => {
  sessionStorage.setItem("auth_user", JSON.stringify({ role: "operator" }));
  vi.stubGlobal("fetch", vi.fn((url: string) => Promise.resolve(new Response(JSON.stringify(
    url.endsWith("/business-rules") ? [{ client_id: "one", client_name: "Alpine", is_active: true, rules }] : url.endsWith("/preview") ? terms : []
  )))));
  render(<MemoryRouter><BusinessRulesPage /></MemoryRouter>);
  expect(await screen.findByLabelText("Freight charge")).toBeDisabled();
  expect(screen.queryByRole("button", { name: "Save client rules" })).not.toBeInTheDocument();
  expect(screen.queryByText("Turn a forwarded order into a client case")).not.toBeInTheDocument();
});
