/**
 * Self-contained ATH gateway + upstream for Python SDK E2E tests.
 *
 * - Real @ath-protocol/server handlers (register, authorize, callback, token, revoke, proxy)
 * - Real upstream HTTP API
 * - Mock OAuth2 IdP only (minimal authorize + token + PKCE S256)
 *
 * Usage: node scripts/e2e_gateway_stack.mjs
 * Env:   OAUTH_PORT (default 18000), GATEWAY_PORT (18001), UPSTREAM_PORT (18002)
 */

import http from "node:http";
import crypto from "node:crypto";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const serverRoot = join(__dirname, "../typescript-sdk/packages/server/dist/index.js");
const ath = await import(serverRoot);

const OAUTH_PORT = Number(process.env.OAUTH_PORT || 18100);
const GATEWAY_PORT = Number(process.env.GATEWAY_PORT || 18101);
const UPSTREAM_PORT = Number(process.env.UPSTREAM_PORT || 18102);

const OAUTH_URL = `http://127.0.0.1:${OAUTH_PORT}`;
const GATEWAY_URL = `http://127.0.0.1:${GATEWAY_PORT}`;
const UPSTREAM_URL = `http://127.0.0.1:${UPSTREAM_PORT}`;

const CLIENT_ID = "ath-e2e-client";
const CLIENT_SECRET = "ath-e2e-secret";

const registry = new ath.InMemoryAgentRegistry();
const tokenStore = new ath.InMemoryTokenStore();
const sessionStore = new ath.InMemorySessionStore();
const providerTokenStore = new ath.InMemoryProviderTokenStore();

const handlers = ath.createATHHandlers({
  registry,
  tokenStore,
  sessionStore,
  providerTokenStore,
  config: {
    audience: GATEWAY_URL,
    callbackUrl: `${GATEWAY_URL}/ath/callback`,
    availableScopes: ["repo", "read:user", "user:email", "read:org"],
    appId: "github",
    skipAttestationVerification: true,
    oauth: {
      authorize_endpoint: `${OAUTH_URL}/authorize`,
      token_endpoint: `${OAUTH_URL}/token`,
      client_id: CLIENT_ID,
      client_secret: CLIENT_SECRET,
    },
  },
});

const proxy = ath.createProxyHandler({
  tokenStore,
  providerTokenStore,
  upstreams: { github: UPSTREAM_URL },
});

/** @type {Map<string, object>} */
const authCodes = new Map();

function parseQuery(search) {
  const q = new URLSearchParams(search || "");
  const o = {};
  for (const [k, v] of q) o[k] = v;
  return o;
}

async function readJsonBody(req) {
  const chunks = [];
  for await (const c of req) chunks.push(c);
  const raw = Buffer.concat(chunks).toString("utf8");
  if (!raw) return {};
  try {
    return JSON.parse(raw);
  } catch {
    return {};
  }
}

async function readFormBody(req) {
  const chunks = [];
  for await (const c of req) chunks.push(c);
  const raw = Buffer.concat(chunks).toString("utf8");
  const params = new URLSearchParams(raw);
  const o = {};
  for (const [k, v] of params) o[k] = v;
  return o;
}

function oauthServer() {
  return http.createServer((req, res) => {
    const u = new URL(req.url || "/", `http://127.0.0.1:${OAUTH_PORT}`);

    if (req.method === "GET" && u.pathname === "/health") {
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ status: "ok", provider: "mock-oauth" }));
      return;
    }

    if (req.method === "GET" && u.pathname === "/authorize") {
      const q = parseQuery(u.search);
      if (q.response_type !== "code") {
        res.writeHead(400, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ error: "unsupported_response_type" }));
        return;
      }
      if (q.client_id !== CLIENT_ID) {
        res.writeHead(400, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ error: "invalid_client" }));
        return;
      }
      if (q.auto_approve !== "true") {
        res.writeHead(400, { "Content-Type": "application/json" });
        res.end(
          JSON.stringify({
            error: "interaction_required",
            message: "Set auto_approve=true for automated E2E",
          }),
        );
        return;
      }
      const code = crypto.randomBytes(16).toString("hex");
      authCodes.set(code, {
        client_id: q.client_id,
        redirect_uri: q.redirect_uri || "",
        scope: q.scope || "",
        code_challenge: q.code_challenge,
        code_challenge_method: q.code_challenge_method,
        resource: q.resource,
        expires_at: Date.now() + 600_000,
      });
      const redir = new URL(q.redirect_uri);
      redir.searchParams.set("code", code);
      if (q.state) redir.searchParams.set("state", q.state);
      res.writeHead(302, { Location: redir.toString() });
      res.end();
      return;
    }

    if (req.method === "POST" && u.pathname === "/token") {
      const ct = req.headers["content-type"] || "";
      void (async () => {
        let body;
        if (ct.includes("application/json")) {
          body = await readJsonBody(req);
        } else {
          body = await readFormBody(req);
        }
        if (body.grant_type !== "authorization_code") {
          res.writeHead(400, { "Content-Type": "application/json" });
          res.end(JSON.stringify({ error: "unsupported_grant_type" }));
          return;
        }
        if (body.client_id !== CLIENT_ID || body.client_secret !== CLIENT_SECRET) {
          res.writeHead(401, { "Content-Type": "application/json" });
          res.end(JSON.stringify({ error: "invalid_client" }));
          return;
        }
        const row = authCodes.get(body.code);
        if (!row || row.client_id !== body.client_id) {
          res.writeHead(400, { "Content-Type": "application/json" });
          res.end(JSON.stringify({ error: "invalid_grant" }));
          return;
        }
        if (row.expires_at < Date.now()) {
          authCodes.delete(body.code);
          res.writeHead(400, { "Content-Type": "application/json" });
          res.end(JSON.stringify({ error: "invalid_grant" }));
          return;
        }
        if (row.code_challenge) {
          const verifier = body.code_verifier;
          if (!verifier) {
            res.writeHead(400, { "Content-Type": "application/json" });
            res.end(JSON.stringify({ error: "invalid_grant", message: "Missing code_verifier" }));
            return;
          }
          const computed =
            row.code_challenge_method === "S256"
              ? crypto.createHash("sha256").update(verifier).digest("base64url")
              : verifier;
          if (computed !== row.code_challenge) {
            authCodes.delete(body.code);
            res.writeHead(400, { "Content-Type": "application/json" });
            res.end(JSON.stringify({ error: "invalid_grant", message: "PKCE failed" }));
            return;
          }
        }
        authCodes.delete(body.code);
        const accessToken = `mock_at_${crypto.randomBytes(24).toString("hex")}`;
        res.writeHead(200, { "Content-Type": "application/json" });
        res.end(
          JSON.stringify({
            access_token: accessToken,
            token_type: "Bearer",
            expires_in: 3600,
            scope: row.scope,
          }),
        );
      })();
      return;
    }

    res.writeHead(404);
    res.end();
  });
}

function upstreamServer() {
  return http.createServer((req, res) => {
    const u = new URL(req.url || "/", UPSTREAM_URL);
    if (req.method === "GET" && u.pathname === "/health") {
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ status: "ok" }));
      return;
    }
    if (req.method === "GET" && u.pathname === "/userinfo") {
      const auth = req.headers.authorization;
      if (!auth?.startsWith("Bearer ")) {
        res.writeHead(401, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ error: "unauthorized" }));
        return;
      }
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ login: "test-user", name: "Test User", email: "test@example.com" }));
      return;
    }
    res.writeHead(404);
    res.end();
  });
}

async function handleGateway(req, res) {
  const u = new URL(req.url || "/", GATEWAY_URL);
  const path = u.pathname + u.search;

  const headers = {};
  for (const [k, v] of Object.entries(req.headers)) {
    if (typeof v === "string") headers[k] = v;
    else if (Array.isArray(v) && v[0]) headers[k] = v[0];
  }

  const sendHandler = async (name, method, p, body) => {
    const fn = handlers[name];
    if (!fn) throw new Error(`Unknown handler: ${name}`);
    const r = await fn({ method, path: p, headers, body });
    if (r.status === 302 && r.headers?.Location) {
      res.writeHead(302, { Location: r.headers.Location });
      res.end();
      return;
    }
    res.writeHead(r.status, { "Content-Type": "application/json" });
    res.end(typeof r.body === "string" ? r.body : JSON.stringify(r.body));
  };

  if (req.method === "GET" && u.pathname === "/.well-known/ath.json") {
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(
      JSON.stringify({
        ath_version: "0.1",
        gateway_id: GATEWAY_URL,
        agent_registration_endpoint: `${GATEWAY_URL}/ath/agents/register`,
        supported_providers: [
          {
            provider_id: "github",
            display_name: "GitHub",
            categories: [],
            available_scopes: ["repo", "read:user", "user:email", "read:org"],
            auth_mode: "OAUTH2",
            agent_approval_required: true,
          },
        ],
      }),
    );
    return;
  }

  if (req.method === "GET" && u.pathname === "/health") {
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ status: "ok" }));
    return;
  }

  if (req.method === "POST" && u.pathname === "/ath/agents/register") {
    const body = await readJsonBody(req);
    await sendHandler("register", "POST", "/ath/agents/register", body);
    return;
  }

  if (req.method === "POST" && u.pathname === "/ath/authorize") {
    const body = await readJsonBody(req);
    await sendHandler("authorize", "POST", "/ath/authorize", body);
    return;
  }

  if (req.method === "GET" && u.pathname === "/ath/callback") {
    const query = parseQuery(u.search);
    const r = await handlers.callback({
      method: "GET",
      path: "/ath/callback",
      headers,
      query,
      url: u.toString(),
    });
    if (r.status === 302 && r.headers?.Location) {
      res.writeHead(302, { Location: r.headers.Location });
      res.end();
      return;
    }
    res.writeHead(r.status, { "Content-Type": "application/json" });
    res.end(JSON.stringify(r.body));
    return;
  }

  if (req.method === "POST" && u.pathname === "/ath/token") {
    const body = await readJsonBody(req);
    await sendHandler("token", "POST", "/ath/token", body);
    return;
  }

  if (req.method === "POST" && u.pathname === "/ath/revoke") {
    const body = await readJsonBody(req);
    await sendHandler("revoke", "POST", "/ath/revoke", body);
    return;
  }

  if (u.pathname.startsWith("/ath/proxy/")) {
    let body;
    if (req.method !== "GET" && req.method !== "HEAD") {
      try {
        body = await readJsonBody(req);
      } catch {
        body = undefined;
      }
    }
    const pr = await proxy({
      method: req.method,
      path: u.pathname,
      headers,
      query: parseQuery(u.search),
      body,
    });
    const bodyStr =
      typeof pr.body === "string" || pr.body instanceof Buffer
        ? String(pr.body)
        : JSON.stringify(pr.body);
    const h = { ...pr.headers };
    if (!h["content-type"]) h["content-type"] = "application/json";
    res.writeHead(pr.status, h);
    res.end(bodyStr);
    return;
  }

  res.writeHead(404, { "Content-Type": "application/json" });
  res.end(JSON.stringify({ code: "NOT_FOUND", message: path }));
}

function gatewayServer() {
  return http.createServer((req, res) => {
    void handleGateway(req, res).catch((err) => {
      console.error(err);
      res.writeHead(500, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ error: String(err) }));
    });
  });
}

const oauth = oauthServer();
const upstream = upstreamServer();
const gateway = gatewayServer();

function listen(srv, port) {
  return new Promise((resolve, reject) => {
    srv.listen(port, "127.0.0.1", () => resolve());
    srv.on("error", reject);
  });
}

await Promise.all([
  listen(oauth, OAUTH_PORT),
  listen(upstream, UPSTREAM_PORT),
  listen(gateway, GATEWAY_PORT),
]);

console.error(
  JSON.stringify({
    ready: true,
    oauth: OAUTH_URL,
    gateway: GATEWAY_URL,
    upstream: UPSTREAM_URL,
  }),
);

function shutdown() {
  oauth.close();
  upstream.close();
  gateway.close();
  process.exit(0);
}

process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);
