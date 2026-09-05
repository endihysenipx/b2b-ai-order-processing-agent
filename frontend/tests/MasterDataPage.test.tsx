import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MasterDataPage } from "../src/pages/MasterDataPage";
import { orderList } from "./testData";

afterEach(() => { vi.unstubAllGlobals(); sessionStorage.clear(); });

describe("MasterDataPage", () => {
  it("loads customer data and saves an administrator's approved addresses", async () => {
    sessionStorage.setItem("auth_user", JSON.stringify({ role: "admin" }));
    const customer = { ...orderList.items[0].client, approved_delivery_addresses: [], master_data_enabled: false };
    const fetchMock = vi.fn((url: string, options?: RequestInit) => {
      const data = url.endsWith("/products") ? [] : url.endsWith("/clients") ? [customer] :
        options?.method === "PUT" ? { ...customer, ...JSON.parse(options.body as string) } : customer;
      return Promise.resolve(new Response(JSON.stringify(data), { status: 200 }));
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<MasterDataPage />);
    fireEvent.change(await screen.findByLabelText("Approved delivery addresses (one per line)"), { target: { value: "Warehouse A" } });
    fireEvent.click(screen.getByRole("button", { name: "Save customer" }));
    expect(await screen.findByText("Customer details saved.")).toBeInTheDocument();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("/customer-data"), expect.objectContaining({ method: "PUT", body: expect.stringContaining("Warehouse A") })));
  });

  it("shows a load error", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(new Response(JSON.stringify({ detail: "Service unavailable" }), { status: 503 }))));
    render(<MasterDataPage />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Service unavailable");
  });
});
