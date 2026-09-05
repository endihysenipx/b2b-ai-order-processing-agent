import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { OrderDetailsPage } from "../src/pages/OrderDetailsPage";
import { orderDetail } from "./testData";

describe("OrderDetailsPage", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn((url: string) => Promise.resolve(new Response(JSON.stringify(url.includes("/products") ? [] : url.includes("/products") ? [] : orderDetail), { status: 200 }))));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("displays sample order header and items", async () => {
    render(
      <MemoryRouter initialEntries={["/orders/order-1"]}>
        <Routes>
          <Route path="/orders/:orderId" element={<OrderDetailsPage />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByDisplayValue("TCK-10001")).toBeInTheDocument();
    expect(screen.getByDisplayValue("1 Market Street")).toBeInTheDocument();
    expect(screen.getByDisplayValue("2026-W29")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Store rollout")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Buyer 1")).toBeInTheDocument();
    expect(screen.getByDisplayValue("500.00")).toBeInTheDocument();
    expect(screen.getAllByDisplayValue("EUR").length).toBeGreaterThan(0);
    expect(screen.getByLabelText("Article for line 1")).toHaveValue("ART-01");
    expect(screen.getByText("Purchase order TCK-10001")).toBeInTheDocument();
    expect(screen.getByLabelText("Currency for line 1")).toHaveValue("EUR");
    expect(screen.getByText("succeeded")).toBeInTheDocument();
    expect(screen.getByText("View extracted text")).toBeInTheDocument();
  });

  it("keeps the correction form visible when approval is blocked", async () => {
    vi.stubGlobal("fetch", vi.fn((url: string, options?: RequestInit) => Promise.resolve(
      new Response(JSON.stringify(options?.method === "POST" ? { detail: "Resolve stock shortage" } : url.includes("/products") ? [] : orderDetail),
        { status: options?.method === "POST" ? 409 : 200 }),
    )));
    render(<MemoryRouter initialEntries={["/orders/order-1"]}><Routes>
      <Route path="/orders/:orderId" element={<OrderDetailsPage />} />
    </Routes></MemoryRouter>);
    fireEvent.click(await screen.findByRole("button", { name: "Approve" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Resolve stock shortage");
    expect(screen.getByDisplayValue("TCK-10001")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Validate order" })).toBeInTheDocument();
  });
});
