const DEVICE_ID_STORAGE_KEY = "smart-cart-device-id";

interface ResolveDeviceIdParams {
  envDeviceId?: string;
  search?: string;
  storage?: Pick<Storage, "getItem" | "setItem">;
}

function generateDeviceId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return `device-${crypto.randomUUID()}`;
  }

  return `device-${Date.now()}`;
}

export function resolveDeviceId({
  envDeviceId,
  search = "",
  storage,
}: ResolveDeviceIdParams): string {
  const trimmedEnv = envDeviceId?.trim();
  if (trimmedEnv) {
    storage?.setItem(DEVICE_ID_STORAGE_KEY, trimmedEnv);
    return trimmedEnv;
  }

  const queryDeviceId = new URLSearchParams(search).get("deviceId")?.trim();
  if (queryDeviceId) {
    storage?.setItem(DEVICE_ID_STORAGE_KEY, queryDeviceId);
    return queryDeviceId;
  }

  const persistedDeviceId = storage?.getItem(DEVICE_ID_STORAGE_KEY)?.trim();
  if (persistedDeviceId) {
    return persistedDeviceId;
  }

  const generatedDeviceId = generateDeviceId();
  storage?.setItem(DEVICE_ID_STORAGE_KEY, generatedDeviceId);
  return generatedDeviceId;
}

export function getResolvedDeviceId(): string {
  return resolveDeviceId({
    envDeviceId: import.meta.env.VITE_DEVICE_ID,
    search: window.location.search,
    storage: window.localStorage,
  });
}
