import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { OrdersPage } from "../src/pages/OrdersPage";
import { orderList } from "./testData";

describe("OrdersPage", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) => {
        if (url.includes("/clients")) {
          return Promise.resolve(new Response(JSON.stringify([orderList.items[0].client]), { status: 200 }));
        }
        return Promise.resolve(new Response(JSON.stringify(orderList), { status: 200 }));
      }),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders backend order data", async () => {
    render(
      <MemoryRouter>
        <OrdersPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText("TCK-10001")).toBeInTheDocument();
    expect(screen.getAllByText("Northwind Retail Group").length).toBeGreaterThan(0);
  });
});
