import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import OsintInvestigate from "./OsintInvestigate.jsx";

// Mock the API client: /osint/investigate returns capability-tagged tools, and for
// enrichable kinds /osint/enrich returns live facts.
const get = vi.fn();
vi.mock("../lib/api.js", () => ({ api: { get: (...a) => get(...a) } }));

beforeEach(() => {
  get.mockReset();
  get.mockImplementation((url) => {
    if (url.startsWith("/osint/investigate")) {
      return Promise.resolve({
        value: "8.8.8.8", kind: "ip", enrichable: true,
        capabilities: { live: 1, pivot: 2, launch: 0 },
        tools: [
          { name: "Shodan", url: "https://www.shodan.io/host/8.8.8.8", capability: "pivot", native: true, templated: true },
          { name: "Obscure", url: "https://google.com/search?q=site:x+8.8.8.8", capability: "pivot", native: false, templated: true },
        ],
      });
    }
    if (url.startsWith("/osint/enrich")) {
      return Promise.resolve({ value: "8.8.8.8", kind: "ip", sources: ["ip-api.com"],
        facts: [{ label: "Location", value: "Mountain View, US", source: "ip-api.com", url: null }] });
    }
    return Promise.resolve({});
  });
});

describe("OsintInvestigate", () => {
  it("renders catalog tools and live facts for an enrichable entity", async () => {
    render(<OsintInvestigate value="8.8.8.8" kind="ip" />);
    await waitFor(() => expect(screen.getByText("Shodan")).toBeInTheDocument());
    expect(screen.getByText("Obscure")).toBeInTheDocument();
    // capability summary line
    expect(screen.getByText(/1 live/)).toBeInTheDocument();
    // live fact fetched + rendered
    await waitFor(() => expect(screen.getByText("Mountain View, US")).toBeInTheDocument());
    expect(get).toHaveBeenCalledWith(expect.stringContaining("/osint/enrich"));
  });

  it("does not fetch enrich for a non-enrichable kind", async () => {
    get.mockImplementation((url) => {
      if (url.startsWith("/osint/investigate")) {
        return Promise.resolve({ value: "Jane", kind: "name", enrichable: false,
          capabilities: { live: 0, pivot: 1, launch: 0 },
          tools: [{ name: "LinkedIn", url: "https://linkedin.com/?q=Jane", capability: "pivot", native: true, templated: true }] });
      }
      return Promise.resolve({});
    });
    render(<OsintInvestigate value="Jane" kind="name" />);
    await waitFor(() => expect(screen.getByText("LinkedIn")).toBeInTheDocument());
    expect(get).not.toHaveBeenCalledWith(expect.stringContaining("/osint/enrich"));
  });
});
