import { describe, it, expect } from "vitest";
import { getAgent, AGENTS } from "@/lib/agents";

describe("getAgent", () => {
  it("returns config for known agent keys", () => {
    const engineer = getAgent("engineer");
    expect(engineer.displayName).toBe("Engineer");
    expect(engineer.avatar).toBeTruthy();
    expect(engineer.colorClass).toContain("bg-green");
  });

  it("returns config for hyphenated keys", () => {
    const techLead = getAgent("tech-lead");
    expect(techLead.displayName).toBe("Tech Lead");
  });

  it("returns fallback for unknown keys", () => {
    const unknown = getAgent("unknown-agent");
    expect(unknown.displayName).toBe("unknown-agent");
    expect(unknown.avatar).toBe("");
    expect(unknown.colorClass).toContain("bg-zinc");
  });

  it("has entries for all expected agents", () => {
    const expectedKeys = [
      "po",
      "engineer",
      "reviewer",
      "tech-lead",
      "sre",
      "human",
    ];
    for (const key of expectedKeys) {
      expect(AGENTS[key]).toBeDefined();
    }
  });
});
