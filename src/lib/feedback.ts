export function extractApiErrorMessage(error: unknown, fallback: string): string {
  if (!(error instanceof Error)) return fallback;
  const raw = error.message?.trim();
  if (!raw) return fallback;

  try {
    const parsed = JSON.parse(raw) as { detail?: string | { msg?: string }[] };
    if (typeof parsed.detail === 'string' && parsed.detail.trim()) {
      return parsed.detail.trim();
    }
    if (Array.isArray(parsed.detail) && parsed.detail.length > 0) {
      const first = parsed.detail[0];
      if (first && typeof first.msg === 'string' && first.msg.trim()) {
        return first.msg.trim();
      }
    }
  } catch {
    // fall through to raw string.
  }

  const match = raw.match(/"detail"\s*:\s*"([^"]+)"/i);
  if (match?.[1]) {
    return match[1];
  }
  return raw;
}

export function parseMoneyInput(raw: string): number | null {
  if (!raw) return null;
  const normalized = raw.replaceAll(',', '').trim();
  if (!normalized) return null;
  const value = Number(normalized);
  if (!Number.isFinite(value)) return null;
  return value;
}
