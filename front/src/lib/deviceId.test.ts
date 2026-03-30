import { describe, expect, it, vi } from "vitest";

import { resolveDeviceId } from "./deviceId";

describe("resolveDeviceId", () => {
  it("prioritizes env device id and persists it", () => {
    const storage = {
      getItem: vi.fn(() => null),
      setItem: vi.fn(),
    };

    const value = resolveDeviceId({
      envDeviceId: "raspberry-cart-01",
      search: "?deviceId=query-cart",
      storage,
    });

    expect(value).toBe("raspberry-cart-01");
    expect(storage.setItem).toHaveBeenCalledWith("smart-cart-device-id", "raspberry-cart-01");
  });

  it("uses query param when env is absent", () => {
    const storage = {
      getItem: vi.fn(() => null),
      setItem: vi.fn(),
    };

    const value = resolveDeviceId({
      search: "?deviceId=cart-touch-22",
      storage,
    });

    expect(value).toBe("cart-touch-22");
  });

  it("falls back to persisted value", () => {
    const storage = {
      getItem: vi.fn(() => "cart-saved"),
      setItem: vi.fn(),
    };

    const value = resolveDeviceId({
      search: "",
      storage,
    });

    expect(value).toBe("cart-saved");
  });
});
