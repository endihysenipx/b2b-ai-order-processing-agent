import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { OrderDetailsPage } from "../src/pages/OrderDetailsPage";
import { orderDetail } from "./testData";

describe("OrderDetailsPage", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(new Response(JSON.stringify(orderDetail), { status: 200 }))));
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
    expect(screen.getByText("ART-01")).toBeInTheDocument();
    expect(screen.getByText("Purchase order TCK-10001")).toBeInTheDocument();
  });
});
