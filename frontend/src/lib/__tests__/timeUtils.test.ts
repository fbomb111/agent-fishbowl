import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { timeAgo, isFresh } from "@/lib/timeUtils";

describe("timeAgo", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-02-20T12:00:00Z"));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("returns 'just now' for timestamps less than 60 seconds ago", () => {
    expect(timeAgo("2026-02-20T11:59:30Z")).toBe("just now");
  });

  it("returns minutes in short form", () => {
    expect(timeAgo("2026-02-20T11:55:00Z")).toBe("5m ago");
  });

  it("returns minutes in verbose form", () => {
    expect(timeAgo("2026-02-20T11:55:00Z", true)).toBe("5 minutes ago");
  });

  it("returns singular minute in verbose form", () => {
    expect(timeAgo("2026-02-20T11:59:00Z", true)).toBe("1 minute ago");
  });

  it("returns hours in short form", () => {
    expect(timeAgo("2026-02-20T09:00:00Z")).toBe("3h ago");
  });

  it("returns hours in verbose form", () => {
    expect(timeAgo("2026-02-20T09:00:00Z", true)).toBe("3 hours ago");
  });

  it("returns singular hour in verbose form", () => {
    expect(timeAgo("2026-02-20T11:00:00Z", true)).toBe("1 hour ago");
  });

  it("returns days in short form", () => {
    expect(timeAgo("2026-02-18T12:00:00Z")).toBe("2d ago");
  });

  it("returns days in verbose form", () => {
    expect(timeAgo("2026-02-18T12:00:00Z", true)).toBe("2 days ago");
  });

  it("returns singular day in verbose form", () => {
    expect(timeAgo("2026-02-19T12:00:00Z", true)).toBe("1 day ago");
  });
});

describe("isFresh", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-02-20T12:00:00Z"));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("returns true for timestamps within default 6-hour threshold", () => {
    expect(isFresh("2026-02-20T08:00:00Z")).toBe(true);
  });

  it("returns false for timestamps beyond default threshold", () => {
    expect(isFresh("2026-02-20T05:00:00Z")).toBe(false);
  });

  it("returns false for future timestamps", () => {
    expect(isFresh("2026-02-20T13:00:00Z")).toBe(false);
  });

  it("respects custom threshold", () => {
    expect(isFresh("2026-02-20T11:00:00Z", 2)).toBe(true);
    expect(isFresh("2026-02-20T09:00:00Z", 2)).toBe(false);
  });
});
