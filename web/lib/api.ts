export class ApiError extends Error {
  status: number;
  code?: string;

  constructor(message: string, status: number, code?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

export async function getJSON<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    let code: string | undefined;
    try {
      const payload = (await response.json()) as { detail?: string; code?: string };
      message = payload.detail ?? message;
      code = payload.code;
    } catch {
      // Keep the concise status message when the response is not JSON.
    }
    throw new ApiError(message, response.status, code);
  }
  return response.json() as Promise<T>;
}

export const percent = (value: number, digits = 1) => `${(value * 100).toFixed(digits)}%`;
export const integer = new Intl.NumberFormat("en", { maximumFractionDigits: 0 });
