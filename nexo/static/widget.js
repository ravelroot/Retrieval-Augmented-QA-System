(function () {
  "use strict";
  var script = document.currentScript || document.querySelector("script[data-nexo]");
  if (!script) return;
  var key = script.getAttribute("data-nexo");
  if (!key || window["__nexo_" + key]) return;
  window["__nexo_" + key] = true;
  var base = script.src.replace(/\/widget\.js(\?.*)?$/, "");
  var api = base + "/api/public/widget/" + encodeURIComponent(key);
  var storeKey = "nexo-widget:" + key;
  var state = { config: null, items: [], busy: false, open: false };

  function load() {
    try {
      var raw = window.sessionStorage.getItem(storeKey);
      var data = raw ? JSON.parse(raw) : null;
      if (data && Array.isArray(data.items)) state.items = data.items.slice(-30);
      if (data && data.open) state.open = true;
    } catch (e) {
      state.items = [];
    }
  }

  function save() {
    try {
      window.sessionStorage.setItem(storeKey, JSON.stringify({ items: state.items.slice(-30), open: state.open }));
    } catch (e) {
      return;
    }
  }

  function escape(text) {
    return String(text).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function format(text) {
    var lines = escape(text).split(/\n/);
    var html = "";
    var list = false;
    lines.forEach(function (line) {
      var item = /^\s*[-*•]\s+(.*)$/.exec(line);
      var body = (item ? item[1] : line)
        .replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>")
        .replace(/\[(\d{1,2})\]/g, "<sup>$1</sup>");
      if (item) {
        if (!list) { html += "<ul>"; list = true; }
        html += "<li>" + body + "</li>";
        return;
      }
      if (list) { html += "</ul>"; list = false; }
      html += body ? "<p>" + body + "</p>" : "";
    });
    if (list) html += "</ul>";
    return html;
  }

  function contrast(hex) {
    var m = /^#?([0-9a-f]{6})$/i.exec(hex || "");
    if (!m) return "#ffffff";
    var n = parseInt(m[1], 16);
    var r = (n >> 16) & 255, g = (n >> 8) & 255, b = n & 255;
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255 > 0.62 ? "#111111" : "#ffffff";
  }

  var ICON_CHAT = '<svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 5h16v11H9l-5 4z"/></svg>';
  var ICON_CLOSE = '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg>';
  var ICON_SEND = '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12h13M13 6l6 6-6 6"/></svg>';

  var CSS = [
    ":host{all:initial}",
    ".nx{--c:#000;--t:#fff;position:fixed;bottom:20px;z-index:2147483000;font:15px/1.45 system-ui,-apple-system,'Segoe UI',Roboto,Arial,sans-serif;color:#1c1b1b}",
    ".nx[data-pos=right]{right:20px}.nx[data-pos=left]{left:20px}",
    ".launch{width:56px;height:56px;border-radius:50%;border:0;background:var(--c);color:var(--t);cursor:pointer;display:grid;place-items:center;box-shadow:0 6px 24px rgba(0,0,0,.22)}",
    ".launch:focus-visible,.close:focus-visible,.send:focus-visible,.sug:focus-visible{outline:2px solid #4d4b4b;outline-offset:2px}",
    ".panel{position:absolute;bottom:72px;width:370px;max-width:calc(100vw - 40px);height:560px;max-height:calc(100vh - 110px);background:#fff;border:1px solid #bab7b6;border-radius:14px;box-shadow:0 18px 50px rgba(0,0,0,.2);display:flex;flex-direction:column;overflow:hidden}",
    ".nx[data-pos=right] .panel{right:0}.nx[data-pos=left] .panel{left:0}",
    ".panel[hidden]{display:none}",
    ".head{background:var(--c);color:var(--t);padding:14px 14px 12px 16px;display:flex;align-items:flex-start;gap:10px}",
    ".head div{flex:1;min-width:0}.head strong{display:block;font-size:16px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}",
    ".head span{display:block;font-size:12px;opacity:.8}",
    ".close{background:transparent;border:0;color:inherit;cursor:pointer;padding:4px;border-radius:6px;display:grid;place-items:center}",
    ".log{flex:1;overflow-y:auto;padding:14px;display:flex;flex-direction:column;gap:10px;background:#f5f4f4}",
    ".msg{max-width:86%;padding:9px 12px;border-radius:12px;word-wrap:break-word}",
    ".msg p{margin:0 0 6px}.msg p:last-child{margin:0}.msg ul{margin:4px 0;padding-left:18px}.msg sup{font-size:10px;font-weight:600;margin-left:1px}",
    ".bot{align-self:flex-start;background:#fff;border:1px solid #e3e1e0}",
    ".me{align-self:flex-end;background:var(--c);color:var(--t)}",
    ".err{align-self:flex-start;background:#fff4f2;border:1px solid #f0c9c2;color:#7a2617}",
    ".src{margin-top:8px;padding-top:6px;border-top:1px solid #ecebea;font-size:12px;color:#4d4b4b}",
    ".src b{display:block;font-weight:600;margin-bottom:2px}.src span{display:block}",
    ".typing{display:inline-flex;gap:4px}.typing i{width:6px;height:6px;border-radius:50%;background:#8c8988;animation:nxb 1s infinite ease-in-out}",
    ".typing i:nth-child(2){animation-delay:.15s}.typing i:nth-child(3){animation-delay:.3s}",
    "@keyframes nxb{0%,80%,100%{opacity:.25}40%{opacity:1}}",
    ".sugs{display:flex;flex-wrap:wrap;gap:6px;padding:0 14px 10px;background:#f5f4f4}.sugs:empty{display:none}",
    ".sug{border:1px solid #bab7b6;background:#fff;border-radius:999px;padding:6px 11px;font:inherit;font-size:13px;cursor:pointer;color:#1c1b1b;text-align:left}",
    ".form{display:flex;gap:8px;padding:10px;border-top:1px solid #e3e1e0;background:#fff}",
    ".form textarea{flex:1;resize:none;border:1px solid #bab7b6;border-radius:10px;padding:9px 11px;font:inherit;min-height:22px;max-height:120px;outline:none;color:#1c1b1b;background:#fff}",
    ".form textarea:focus{border-color:#4d4b4b}",
    ".send{width:42px;border:0;border-radius:10px;background:var(--c);color:var(--t);cursor:pointer;display:grid;place-items:center}",
    ".send:disabled{opacity:.45;cursor:default}",
    ".foot{font-size:11px;color:#8c8988;text-align:center;padding:0 10px 8px;background:#fff}",
    "@media (max-width:480px){.panel{position:fixed;inset:0;width:auto;max-width:none;height:auto;max-height:none;border-radius:0;bottom:0}}",
    "@media (prefers-reduced-motion:reduce){.typing i{animation:none}}"
  ].join("");

  var host, root, panel, log, sugs, input, send, launch;

  function el(tag, cls, html) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (html !== undefined) node.innerHTML = html;
    return node;
  }

  function sourceBlock(sources) {
    if (!sources || !sources.length) return "";
    var rows = sources.map(function (s) {
      return "<span>" + s.rank + " · " + escape(s.title) + (s.page ? ", p. " + s.page : "") + "</span>";
    }).join("");
    return '<div class="src"><b>Fontes</b>' + rows + "</div>";
  }

  function render() {
    log.innerHTML = "";
    if (state.config.welcome) log.appendChild(el("div", "msg bot", format(state.config.welcome)));
    state.items.forEach(function (item) {
      var cls = item.role === "user" ? "msg me" : item.error ? "msg err" : "msg bot";
      var node = el("div", cls, item.role === "user" ? format(item.content) : format(item.content) + sourceBlock(item.sources));
      log.appendChild(node);
    });
    if (state.busy) {
      var typing = el("div", "msg bot", '<span class="typing" aria-label="Escrevendo"><i></i><i></i><i></i></span>');
      log.appendChild(typing);
    }
    sugs.innerHTML = "";
    if (!state.items.length && !state.busy) {
      (state.config.suggestions || []).forEach(function (text) {
        var b = el("button", "sug");
        b.type = "button";
        b.textContent = text;
        b.addEventListener("click", function () { ask(text); });
        sugs.appendChild(b);
      });
    }
    send.disabled = state.busy || !input.value.trim();
    log.scrollTop = log.scrollHeight;
  }

  function history() {
    return state.items.filter(function (i) { return !i.error; }).slice(-12).map(function (i) {
      return { role: i.role, content: String(i.content).slice(0, 3000) };
    });
  }

  function ask(text) {
    var question = String(text || "").trim().slice(0, 2000);
    if (!question || state.busy) return;
    var previous = history();
    state.items.push({ role: "user", content: question });
    state.busy = true;
    input.value = "";
    resize();
    render();
    save();
    fetch(api + "/ask", {
      method: "POST",
      mode: "cors",
      credentials: "omit",
      headers: { "Content-Type": "text/plain;charset=UTF-8" },
      body: JSON.stringify({ question: question, history: previous })
    }).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (data) { return { ok: r.ok, data: data }; });
    }).then(function (res) {
      if (res.ok) {
        state.items.push({ role: "assistant", content: res.data.answer || "", sources: res.data.sources || [] });
      } else {
        state.items.push({ role: "assistant", error: true, content: res.data.message || "Não foi possível responder agora." });
      }
    }).catch(function () {
      state.items.push({ role: "assistant", error: true, content: "Sem conexão com o assistente. Confira a internet e tente de novo." });
    }).then(function () {
      state.busy = false;
      render();
      save();
      if (state.open) input.focus();
    });
  }

  function resize() {
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 120) + "px";
  }

  function setOpen(open) {
    state.open = open;
    panel.hidden = !open;
    launch.setAttribute("aria-expanded", open ? "true" : "false");
    launch.innerHTML = open ? ICON_CLOSE : ICON_CHAT;
    launch.setAttribute("aria-label", open ? "Fechar assistente" : "Abrir assistente");
    save();
    if (open) {
      render();
      window.setTimeout(function () { input.focus(); }, 30);
    }
  }

  function build(config) {
    state.config = config;
    host = document.createElement("div");
    host.setAttribute("data-nexo-widget", "");
    root = host.attachShadow ? host.attachShadow({ mode: "open" }) : host;
    var style = document.createElement("style");
    style.textContent = CSS;
    root.appendChild(style);
    var wrap = el("div", "nx");
    wrap.setAttribute("data-pos", config.position === "left" ? "left" : "right");
    wrap.style.setProperty("--c", config.color || "#000000");
    wrap.style.setProperty("--t", contrast(config.color));
    panel = el("section", "panel");
    panel.setAttribute("role", "dialog");
    panel.setAttribute("aria-label", config.title);
    panel.hidden = true;
    var head = el("header", "head");
    var titles = el("div");
    var strong = el("strong");
    strong.textContent = config.title;
    var sub = el("span");
    sub.textContent = "Responde com base nos documentos";
    titles.appendChild(strong);
    titles.appendChild(sub);
    var close = el("button", "close", ICON_CLOSE);
    close.type = "button";
    close.setAttribute("aria-label", "Fechar assistente");
    close.addEventListener("click", function () { setOpen(false); launch.focus(); });
    head.appendChild(titles);
    head.appendChild(close);
    log = el("div", "log");
    log.setAttribute("role", "log");
    log.setAttribute("aria-live", "polite");
    sugs = el("div", "sugs");
    var form = el("form", "form");
    input = el("textarea");
    input.rows = 1;
    input.maxLength = 2000;
    input.placeholder = "Escreva sua pergunta";
    input.setAttribute("aria-label", "Sua pergunta");
    send = el("button", "send", ICON_SEND);
    send.type = "submit";
    send.setAttribute("aria-label", "Enviar pergunta");
    form.appendChild(input);
    form.appendChild(send);
    form.addEventListener("submit", function (e) { e.preventDefault(); ask(input.value); });
    input.addEventListener("input", function () { resize(); send.disabled = state.busy || !input.value.trim(); });
    input.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); ask(input.value); }
    });
    var foot = el("div", "foot");
    foot.textContent = "Respostas a partir de documentos, com o Nexo";
    panel.appendChild(head);
    panel.appendChild(log);
    panel.appendChild(sugs);
    panel.appendChild(form);
    panel.appendChild(foot);
    launch = el("button", "launch", ICON_CHAT);
    launch.type = "button";
    launch.setAttribute("aria-haspopup", "dialog");
    launch.addEventListener("click", function () { setOpen(!state.open); });
    wrap.appendChild(panel);
    wrap.appendChild(launch);
    wrap.addEventListener("keydown", function (e) { if (e.key === "Escape" && state.open) { setOpen(false); launch.focus(); } });
    root.appendChild(wrap);
    document.body.appendChild(host);
    render();
    setOpen(state.open || script.getAttribute("data-open") === "true");
    window.NexoWidget = {
      open: function () { setOpen(true); },
      close: function () { setOpen(false); },
      toggle: function () { setOpen(!state.open); },
      ask: function (text) { setOpen(true); ask(text); },
      reset: function () { state.items = []; save(); render(); }
    };
  }

  function start() {
    load();
    fetch(api + "/config", { mode: "cors", credentials: "omit" })
      .then(function (r) { return r.ok ? r.json() : Promise.reject(r.status); })
      .then(build)
      .catch(function (status) {
        if (window.console) window.console.warn("Nexo: o widget não foi carregado (" + status + "). Confira a chave e os sites autorizados.");
      });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})();
