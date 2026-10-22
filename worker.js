const SEED = [
  {
    id: "ku",
    title: "Коэффициент устойчивости",
    description: "КУ-спрос, КУ-узлы и окупаемость. Расчёт остаётся в браузере и никуда не отправляется.",
    href: "/ku",
    builtin: true,
  },
];

const COOKIE = "sadmae_admin";
const DAY = 86400;

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.hostname === "sadmae.app") {
      url.hostname = "www.sadmae.app";
      return Response.redirect(url.toString(), 301);
    }
    if (url.pathname === "/ku" || url.pathname === "/ku/") {
      return env.ASSETS.fetch(new Request(new URL("/ku/index.html", url), request));
    }
    if (url.pathname === "/admin" || url.pathname === "/admin/") return admin(request, env);
    if (url.pathname === "/" || url.pathname === "/index.html") return home(env);
    return env.ASSETS.fetch(request);
  },
};

async function home(env) {
  const projects = await loadProjects(env);
  const cards = projects
    .map(
      (project) => `<article class="card">
        <h2>${esc(project.title)}</h2>
        <p>${esc(project.description)}</p>
        <a class="btn" href="${esc(project.href)}">Открыть</a>
      </article>`,
    )
    .join("");
  return html(`<header>
      <p class="mark">sadmae.app</p>
      <h1>Разработки</h1>
      <p class="lead">Короткий список того, что можно открыть прямо здесь.</p>
    </header>
    <section class="grid">${cards}</section>
    <footer><a href="/admin">Панель</a></footer>`, "sadmae.app");
}

async function admin(request, env) {
  if (!env.ADMIN_PASSWORD || !env.AUTH_SECRET) {
    return html(`<header><p class="mark">sadmae.app</p><h1>Панель</h1></header>
      <p class="lead">Пароль администратора ещё не задан на сервере.</p>
      <p><a href="/">На главную</a></p>`, "Панель", 503);
  }
  if (request.method === "POST") {
    if (!sameOrigin(request)) return new Response("Bad origin", { status: 403 });
    const form = await request.formData();
    const action = String(form.get("action") || "");
    if (action === "login") {
      if (!equal(String(form.get("password") || ""), env.ADMIN_PASSWORD)) {
        return html(loginForm("Неверный пароль."), "Панель", 401);
      }
      return new Response(null, { status: 303, headers: { Location: "/admin", "Set-Cookie": await sessionCookie(env, request) } });
    }
    if (!(await authed(request, env))) return html(loginForm("Сначала войдите."), "Панель", 401);
    if (action === "logout") {
      return new Response(null, { status: 303, headers: { Location: "/admin", "Set-Cookie": clearCookie(request) } });
    }
    const projects = await loadProjects(env);
    if (!env.PROJECTS) {
      return html(panel(projects, "Хранилище проектов ещё не подключено. Ссылки на странице есть, добавить новую пока нельзя."), "Панель", 503);
    }
    if (action === "add") {
      const project = cleanProject(form);
      if (!project) return html(panel(projects, "Нужны название и ссылка. Ссылка должна начинаться с / или https://."), "Панель", 400);
      projects.push(project);
      await saveProjects(env, projects);
    }
    if (action === "delete") {
      const id = String(form.get("id") || "");
      const next = projects.filter((project) => project.builtin || project.id !== id);
      await saveProjects(env, next);
    }
    return new Response(null, { status: 303, headers: { Location: "/admin" } });
  }
  if (!(await authed(request, env))) return html(loginForm(), "Панель");
  return html(panel(await loadProjects(env), ""), "Панель");
}

function loginForm(error = "") {
  return `<header><p class="mark">sadmae.app</p><h1>Панель</h1></header>
    ${error ? `<p class="err">${esc(error)}</p>` : ""}
    <form method="post" action="/admin" class="stack">
      <input type="hidden" name="action" value="login">
      <label>Пароль<input type="password" name="password" autocomplete="current-password" required></label>
      <button type="submit">Войти</button>
    </form>
    <p><a href="/">На главную</a></p>`;
}

function panel(projects, error) {
  const rows = projects
    .map(
      (project) => `<li>
        <strong>${esc(project.title)}</strong>
        <span>${esc(project.href)}</span>
        ${
          project.builtin
            ? `<em>встроенный</em>`
            : `<form method="post" action="/admin"><input type="hidden" name="action" value="delete"><input type="hidden" name="id" value="${esc(project.id)}"><button class="alt" type="submit">Убрать</button></form>`
        }
      </li>`,
    )
    .join("");
  return `<header><p class="mark">sadmae.app</p><h1>Панель</h1>
      <p class="lead">Добавьте ссылку на разработку. Она появится на главной.</p>
    </header>
    ${error ? `<p class="err">${esc(error)}</p>` : ""}
    <ul class="list">${rows}</ul>
    <form method="post" action="/admin" class="stack">
      <input type="hidden" name="action" value="add">
      <label>Название<input name="title" maxlength="80" required></label>
      <label>Коротко<textarea name="description" maxlength="240" rows="3"></textarea></label>
      <label>Ссылка<input name="href" placeholder="/ku/ или https://…" required></label>
      <button type="submit">Добавить</button>
    </form>
    <form method="post" action="/admin"><input type="hidden" name="action" value="logout"><button class="alt" type="submit">Выйти</button></form>
    <p><a href="/">На главную</a></p>`;
}

async function loadProjects(env) {
  if (!env.PROJECTS) return SEED.map((project) => ({ ...project }));
  const stored = await env.PROJECTS.get("list", "json");
  const projects = Array.isArray(stored) ? stored.filter(validStored) : [];
  const withoutKu = projects.filter((project) => project.id !== "ku");
  return [{ ...SEED[0] }, ...withoutKu];
}

async function saveProjects(env, projects) {
  await env.PROJECTS.put("list", JSON.stringify(projects));
}

function cleanProject(form) {
  const title = String(form.get("title") || "").trim();
  const description = String(form.get("description") || "").trim();
  const href = String(form.get("href") || "").trim();
  if (!title || title.length > 80 || description.length > 240 || !safeHref(href)) return null;
  return { id: crypto.randomUUID(), title, description, href, builtin: false };
}

function validStored(project) {
  return project && typeof project.id === "string" && typeof project.title === "string" && safeHref(project.href);
}

function safeHref(href) {
  if (typeof href !== "string" || href.length > 300) return false;
  if (href.startsWith("/") && !href.startsWith("//")) return true;
  try {
    const url = new URL(href);
    return url.protocol === "https:" || url.protocol === "http:";
  } catch {
    return false;
  }
}

function sameOrigin(request) {
  const origin = request.headers.get("Origin");
  if (!origin) return true;
  return origin === new URL(request.url).origin;
}

async function authed(request, env) {
  const cookie = readCookie(request, COOKIE);
  if (!cookie) return false;
  const [exp, sig] = cookie.split(".");
  if (!exp || !sig || Number(exp) < Date.now() / 1000) return false;
  return equal(sig, await sign(env.AUTH_SECRET, exp));
}

function cookieSuffix(request) {
  return new URL(request.url).protocol === "https:" ? "; Secure" : "";
}

async function sessionCookie(env, request) {
  const exp = String(Math.floor(Date.now() / 1000) + 7 * DAY);
  const sig = await sign(env.AUTH_SECRET, exp);
  return `${COOKIE}=${exp}.${sig}; HttpOnly; SameSite=Lax; Path=/; Max-Age=${7 * DAY}${cookieSuffix(request)}`;
}

function clearCookie(request) {
  return `${COOKIE}=; HttpOnly; SameSite=Lax; Path=/; Max-Age=0${cookieSuffix(request)}`;
}

async function sign(secret, value) {
  const key = await crypto.subtle.importKey("raw", new TextEncoder().encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const bytes = new Uint8Array(await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(value)));
  let raw = "";
  for (const byte of bytes) raw += String.fromCharCode(byte);
  return btoa(raw).replaceAll("+", "-").replaceAll("/", "_").replaceAll("=", "");
}

function readCookie(request, name) {
  const header = request.headers.get("Cookie") || "";
  for (const part of header.split(";")) {
    const [key, ...rest] = part.trim().split("=");
    if (key === name) return rest.join("=");
  }
  return "";
}

function equal(a, b) {
  const left = String(a);
  const right = String(b);
  let diff = left.length ^ right.length;
  const length = Math.max(left.length, right.length);
  for (let i = 0; i < length; i += 1) diff |= left.charCodeAt(i) ^ right.charCodeAt(i % right.length || 0);
  return diff === 0 && left.length === right.length;
}

function html(body, title, status = 200) {
  return new Response(`<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${esc(title)}</title>
<style>
  :root { color-scheme: light; }
  * { box-sizing: border-box; }
  body { margin: 0; font-family: system-ui, "Segoe UI", sans-serif; background: #f3efe6; color: #1c1915; }
  main { max-width: 760px; margin: 0 auto; padding: 40px 20px 64px; }
  .mark { letter-spacing: .08em; text-transform: uppercase; font-size: 12px; color: #6d6458; margin: 0; }
  h1 { font-size: 40px; line-height: 1.1; margin: 8px 0 0; }
  .lead { color: #4d463d; font-size: 18px; }
  .grid { display: grid; gap: 14px; }
  .card, .stack, .list { background: #fffdf8; border: 1px solid #e4dccb; border-radius: 16px; }
  .card { padding: 18px; }
  .card h2 { margin: 0 0 8px; font-size: 22px; }
  .card p { margin: 0 0 16px; color: #4d463d; }
  .btn, button { display: inline-block; background: #12263f; color: #fff; text-decoration: none; border: 0; border-radius: 999px; padding: 10px 16px; font-size: 15px; cursor: pointer; }
  button.alt { background: #efe7d8; color: #1c1915; }
  footer { margin-top: 28px; }
  footer a, p a { color: #12263f; }
  .stack { padding: 16px; display: grid; gap: 12px; margin: 16px 0; }
  label { display: grid; gap: 6px; font-size: 14px; font-weight: 650; }
  input, textarea { width: 100%; font: inherit; font-weight: 400; padding: 10px; border-radius: 10px; border: 1px solid #d9d0c0; background: #fff; }
  .list { list-style: none; padding: 8px 16px; margin: 0 0 16px; }
  .list li { display: grid; grid-template-columns: 1fr auto; gap: 4px 12px; padding: 12px 0; border-bottom: 1px solid #efe7d8; }
  .list li span, .list li em { grid-column: 1; color: #6d6458; font-style: normal; font-size: 14px; }
  .err { background: #fbe7e4; padding: 10px 12px; border-radius: 10px; }
  @media (max-width: 640px) { h1 { font-size: 32px; } }
</style>
</head>
<body><main>${body}</main></body></html>`, {
    status,
    headers: { "Content-Type": "text/html; charset=UTF-8", "Cache-Control": "no-store" },
  });
}

function esc(value) {
  return String(value).replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[ch]);
}
