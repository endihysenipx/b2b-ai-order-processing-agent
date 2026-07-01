import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { StatusBadge } from "../src/components/common/StatusBadge";

describe("StatusBadge", () => {
  it("renders the status text", () => {
    render(<StatusBadge status="Human in the Loop" />);

    expect(screen.getByText("Human in the Loop")).toHaveClass("status-review");
  });
});
