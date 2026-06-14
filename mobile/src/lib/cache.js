import AsyncStorage from "@react-native-async-storage/async-storage";

const TTL_MS = 5 * 60 * 1000; // 5 minutes

export async function getCached(key) {
  try {
    const raw = await AsyncStorage.getItem(`cache:${key}`);
    if (!raw) return null;
    const { data, ts } = JSON.parse(raw);
    if (Date.now() - ts > TTL_MS) return null;
    return data;
  } catch {
    return null;
  }
}

export async function setCached(key, data) {
  try {
    await AsyncStorage.setItem(`cache:${key}`, JSON.stringify({ data, ts: Date.now() }));
  } catch {}
}

export async function clearCache() {
  const keys = await AsyncStorage.getAllKeys();
  const cacheKeys = keys.filter((k) => k.startsWith("cache:"));
  if (cacheKeys.length) await AsyncStorage.multiRemove(cacheKeys);
}
