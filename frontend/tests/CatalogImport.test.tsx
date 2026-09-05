import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CatalogImport } from "../src/components/CatalogImport";

afterEach(() => vi.unstubAllGlobals());

const preview = {
  can_import: true, token: "preview-token", error_rows: 0,
  counts: { create: 1, update: 0, unchanged: 0 },
  rows: [{ row: 2, sku: "001", action: "create", errors: [], warnings: ["Stock remains unknown."],
    before: null, after: { sku: "001", description: "Test" } }],
};

describe("Catalog import", () => {
  it("requires preview and explicit confirmation before saving", async () => {
    const onImported = vi.fn();
    const fetchMock = vi.fn((url: string) => Promise.resolve(new Response(JSON.stringify(
      url.endsWith("/preview") ? preview : { created: 1, updated: 0, unchanged: 0 },
    ), { status: 200 })));
    vi.stubGlobal("fetch", fetchMock);
    render(<CatalogImport clientId="c1" onImported={onImported} onBusyChange={vi.fn()} />);
    expect(screen.queryByRole("button", { name: "Confirm import" })).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Catalog file"), { target: { files: [new File(["sku,description\n001,Test"], "items.csv")] } });
    fireEvent.click(screen.getByRole("button", { name: "Preview import" }));
    const confirm = await screen.findByRole("button", { name: "Confirm import" });
    expect(confirm).toBeDisabled();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.click(confirm);
    expect(await screen.findByRole("status")).toHaveTextContent("1 added");
    expect(onImported).toHaveBeenCalledOnce();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect((fetchMock.mock.calls[1] as unknown[])[0]).toContain("/confirm");
  });

  it("blocks invalid rows and clears the preview when the file changes", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(new Response(JSON.stringify({
      ...preview, can_import: false, token: null, error_rows: 1,
      rows: [{ ...preview.rows[0], errors: ["Duplicate SKU in this file."] }],
    }), { status: 200 }))));
    render(<CatalogImport clientId="c1" onImported={vi.fn()} onBusyChange={vi.fn()} />);
    const input = screen.getByLabelText("Catalog file");
    fireEvent.change(input, { target: { files: [new File(["x"], "items.csv")] } });
    fireEvent.click(screen.getByRole("button", { name: "Preview import" }));
    expect(await screen.findByText("Duplicate SKU in this file.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Confirm import" })).not.toBeInTheDocument();
    fireEvent.change(input, { target: { files: [new File(["y"], "fixed.csv")] } });
    expect(screen.queryByText("Import preview")).not.toBeInTheDocument();
  });

  it("requires a new preview after a stale confirmation", async () => {
    vi.stubGlobal("fetch", vi.fn((url: string) => Promise.resolve(new Response(JSON.stringify(
      url.endsWith("/preview") ? preview : { detail: "The catalog changed. Preview again." },
    ), { status: url.endsWith("/preview") ? 200 : 409 }))));
    render(<CatalogImport clientId="c1" onImported={vi.fn()} onBusyChange={vi.fn()} />);
    fireEvent.change(screen.getByLabelText("Catalog file"), { target: { files: [new File(["x"], "items.csv")] } });
    fireEvent.click(screen.getByRole("button", { name: "Preview import" }));
    fireEvent.click(await screen.findByRole("checkbox"));
    fireEvent.click(screen.getByRole("button", { name: "Confirm import" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("catalog changed");
    expect(screen.queryByRole("button", { name: "Confirm import" })).not.toBeInTheDocument();
  });
});
