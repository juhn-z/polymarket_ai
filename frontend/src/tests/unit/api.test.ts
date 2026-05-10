import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { api, ApiError } from "@/lib/api";

describe("api", () => {
  const realFetch = global.fetch;
  beforeEach(() => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000/api/v1");
  });
  afterEach(() => {
    vi.unstubAllEnvs();
    global.fetch = realFetch;
  });

  it("GET prepends base URL and parses JSON", async () => {
    global.fetch = vi.fn(async (url) => {
      expect(url).toBe("http://localhost:8000/api/v1/markets/today");
      return new Response(JSON.stringify({ id: 1 }), { status: 200, headers: { "content-type": "application/json" } });
    }) as any;
    const result = await api.get<{ id: number }>("/markets/today");
    expect(result).toEqual({ id: 1 });
  });

  it("returns null on 404 by default", async () => {
    global.fetch = vi.fn(async () => new Response("not found", { status: 404 })) as any;
    const result = await api.get("/markets/today");
    expect(result).toBeNull();
  });

  it("throws ApiError on 500", async () => {
    global.fetch = vi.fn(async () => new Response("kaboom", { status: 500 })) as any;
    await expect(api.get("/markets/today")).rejects.toBeInstanceOf(ApiError);
  });

  it("POST attaches admin token when provided", async () => {
    let captured: any = null;
    global.fetch = vi.fn(async (_url, init) => {
      captured = init;
      return new Response(JSON.stringify({ ok: true }), { status: 200, headers: { "content-type": "application/json" } });
    }) as any;
    await api.post("/markets/scan", undefined, { adminToken: "secret" });
    expect(captured.headers.Authorization).toBe("Bearer secret");
    expect(captured.method).toBe("POST");
  });
});
