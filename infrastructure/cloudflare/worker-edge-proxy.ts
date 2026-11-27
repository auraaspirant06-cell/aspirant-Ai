export interface Env {
  ORIGIN_API_URL: string;
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    const upstream = `${env.ORIGIN_API_URL.replace(/\/$/, "")}${url.pathname}${url.search}`;
    const headers = new Headers(request.headers);
    headers.set("X-Forwarded-Proto", "https");
    const response = await fetch(upstream, {
      method: request.method,
      headers,
      body: request.method === "GET" || request.method === "HEAD" ? undefined : request.body,
    });
    const secured = new Response(response.body, response);
    secured.headers.set("Strict-Transport-Security", "max-age=31536000; includeSubDomains");
    secured.headers.set("X-Content-Type-Options", "nosniff");
    return secured;
  },
};
