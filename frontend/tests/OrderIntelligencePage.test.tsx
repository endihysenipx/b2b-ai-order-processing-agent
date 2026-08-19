import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { OrderIntelligencePage } from "../src/pages/OrderIntelligencePage";
import type { OrderIntelligenceResult } from "../src/types/intelligence";

const intelligenceResult: OrderIntelligenceResult = {
  duplicate: false,
  email_id: "email-demo",
  subject: "Bestellung DEMO26 von Lutz",
  sender_email: "orders@lutz-demo.invalid",
  classification: "order",
  client_profile: "lutz",
  client_name: "Lutz",
  client_confidence: 0.8,
  client_evidence: ["Contains the Lutz 'Filiale:' field."],
  next_action: "ready_for_validation",
  reference_codes: ["DEMO26"],
  notes: ["Order headers were extracted from the email body."],
  attachments: [],
  orders: [
    {
      id: "order-demo",
      ticket_number: "DEMO26",
      commission_number: "DEMO26-1",
      delivery_week: "KW38/2026",
      status: "Waiting for Reply",
      item_count: 1,
      issue_count: 1,
    },
  ],
  requires_review: true,
  clarification_draft: "Hello,\n\nPlease provide the missing delivery address.",
  timeline: [
    { key: "received", label: "Message received", status: "completed", detail: "Stored safely." },
    { key: "classified", label: "Message classified", status: "completed", detail: "Classified as order." },
    { key: "client", label: "Client identified", status: "completed", detail: "Matched Lutz." },
    { key: "extracted", label: "Evidence extracted", status: "completed", detail: "Extracted one order." },
    { key: "validated", label: "Business rules validated", status: "attention", detail: "Found one issue." },
    { key: "review", label: "Human decision", status: "attention", detail: "Review is required." },
  ],
};

describe("OrderIntelligencePage", () => {
  const fetchMock = vi.fn((url: string, options?: RequestInit) => {
    void url;
    void options;
    return Promise.resolve(new Response(JSON.stringify(intelligenceResult), { status: 200 }));
  });

  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    fetchMock.mockClear();
  });

  it("imports the safe demo and renders the explainable human-review handoff", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <OrderIntelligencePage />
      </MemoryRouter>,
    );

    await user.click(screen.getByRole("button", { name: "Load exception demo" }));
    expect(screen.getByText("flowforge-exception-demo.eml")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Analyze and import" }));

    expect(await screen.findByText("Human review required")).toBeInTheDocument();
    expect(screen.getByText("Waiting for Reply")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Review order/ })).toHaveAttribute("href", "/orders/order-demo");
    expect(screen.getByLabelText("Clarification draft")).toHaveValue(
      "Hello,\n\nPlease provide the missing delivery address.",
    );

    const [, options] = fetchMock.mock.calls[0];
    expect(options?.body).toBeInstanceOf(FormData);
    expect(new Headers(options?.headers).has("Content-Type")).toBe(false);
  });
});
