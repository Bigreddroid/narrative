import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";

// Mock the user hook so we control access without an auth provider.
const canMock = vi.fn();
vi.mock("../hooks/useUser.js", () => ({
  useUser: () => ({ can: canMock }),
}));

import TierGate from "./TierGate.jsx";

describe("TierGate", () => {
  it("renders children when the feature is unlocked", () => {
    canMock.mockReturnValue(true);
    render(
      <TierGate feature="eventGraph">
        <div>secret content</div>
      </TierGate>,
    );
    expect(screen.getByText("secret content")).toBeInTheDocument();
    expect(screen.queryByText(/Upgrade/i)).not.toBeInTheDocument();
  });

  it("renders the upgrade gate (not children) when locked", () => {
    canMock.mockReturnValue(false);
    render(
      <TierGate feature="eventGraph">
        <div>secret content</div>
      </TierGate>,
    );
    expect(screen.queryByText("secret content")).not.toBeInTheDocument();
    // Full gate shows the feature label, its required plan, and an Upgrade link.
    expect(screen.getByText("Consequence Chain Analysis")).toBeInTheDocument();
    expect(screen.getByText("Pro")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Upgrade/i })).toHaveAttribute("href", "/settings");
  });

  it("renders a compact inline lock when inline and locked", () => {
    canMock.mockReturnValue(false);
    render(
      <TierGate feature="apiAccess" inline>
        <div>secret content</div>
      </TierGate>,
    );
    expect(screen.queryByText("secret content")).not.toBeInTheDocument();
    // Inline variant packs name + plan into one span, so match on substrings.
    expect(screen.getByText(/API Access/)).toBeInTheDocument();
    expect(screen.getByText("Intelligence+")).toBeInTheDocument();
    // Inline variant has no upgrade link.
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });

  it("falls back to the raw feature name + Pro for unknown features", () => {
    canMock.mockReturnValue(false);
    render(<TierGate feature="mysteryFeature">x</TierGate>);
    expect(screen.getByText("mysteryFeature")).toBeInTheDocument();
  });
});
