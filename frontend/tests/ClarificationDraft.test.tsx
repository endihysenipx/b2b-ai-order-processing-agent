import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { ClarificationDraft } from "../src/components/orders/ClarificationDraft";

const draft = { recipient: "buyer@example.test", subject: "Order question", body: "Please confirm quantity.",
  questions: ["Please confirm quantity."], internal_notes: ["Refresh stock internally."] };
afterEach(() => vi.unstubAllGlobals());

it("allows reviewed edits and copies only the email content", async () => {
  vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(new Response(JSON.stringify(draft)))));
  const writeText = vi.fn().mockResolvedValue(undefined);
  vi.stubGlobal("navigator", { clipboard: { writeText } });
  const view = render(<ClarificationDraft orderId="o" revision="one" disabled={false} />);
  fireEvent.click(screen.getByRole("button", { name: "Prepare clarification draft" }));
  fireEvent.change(await screen.findByLabelText("Message"), { target: { value: "Reviewed question" } });
  fireEvent.click(screen.getByRole("button", { name: "Copy reviewed draft" }));
  await waitFor(() => expect(writeText).toHaveBeenCalledWith("To: buyer@example.test\nSubject: Order question\n\nReviewed question"));
  view.rerender(<ClarificationDraft orderId="o" revision="two" disabled={false} />);
  expect(screen.getByRole("status")).toHaveTextContent("The order changed");
  expect(screen.getByRole("button", { name: "Copied" })).toBeDisabled();
});

it("shows an empty result and reports clipboard failures", async () => {
  vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(new Response(JSON.stringify({ ...draft, questions: [], body: "" })))));
  vi.stubGlobal("navigator", { clipboard: { writeText: vi.fn().mockRejectedValue(new Error("Denied")) } });
  render(<ClarificationDraft orderId="o" revision="one" disabled={false} />);
  fireEvent.click(screen.getByRole("button", { name: "Prepare clarification draft" }));
  expect(await screen.findByText(/No customer clarification questions/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Copy reviewed draft" })).toBeDisabled();
  fireEvent.change(screen.getByLabelText("Message"), { target: { value: "Custom question" } });
  fireEvent.click(screen.getByRole("button", { name: "Copy reviewed draft" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Could not copy");
});
