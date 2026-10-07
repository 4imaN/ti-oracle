import type { NextRequest } from "next/server";

const API_ORIGIN = process.env.TI_ORACLE_API_ORIGIN ?? "http://127.0.0.1:8000";
const METHODS_WITHOUT_BODY = new Set(["GET", "HEAD"]);

type RouteContext = { params: Promise<{ path: string[] }> };

async function proxy(request: NextRequest, context: RouteContext): Promise<Response> {
  const { path } = await context.params;
  const target = new URL(`/api/${path.join("/")}`, API_ORIGIN);
  target.search = request.nextUrl.search;

  const headers = new Headers(request.headers);
  headers.delete("host");
  headers.delete("connection");

  try {
    const upstream = await fetch(target, {
      method: request.method,
      headers,
      body: METHODS_WITHOUT_BODY.has(request.method) ? undefined : await request.arrayBuffer(),
      cache: "no-store",
    });
    const responseHeaders = new Headers(upstream.headers);
    responseHeaders.delete("content-encoding");
    responseHeaders.delete("content-length");
    responseHeaders.delete("transfer-encoding");
    return new Response(upstream.body, { status: upstream.status, headers: responseHeaders });
  } catch {
    return Response.json(
      {
        code: "API_UNAVAILABLE",
        detail: "Live predictions cannot connect to the local data engine. Run npm run dev to launch both Next.js and FastAPI.",
      },
      { status: 503 },
    );
  }
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
export const OPTIONS = proxy;
