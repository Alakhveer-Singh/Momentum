// Shared client helpers for the Quibus LMS server-rendered UI.
// Mutations go through the existing DRF /api (session auth + CSRF). No SPA framework.

const meta = (n) => document.querySelector(`meta[name="${n}"]`)?.getAttribute("content");
const CSRF = meta("csrf-token");
const WS_TOKEN = meta("ws-token");
const USER_ROLE = meta("user-role");

window.inr = (n) => "₹" + Number(n || 0).toLocaleString("en-IN");

// fetch wrapper against /api
window.api = async function (path, { method = "GET", body, raw = false } = {}) {
  const opts = { method, headers: { Accept: "application/json", "X-CSRFToken": CSRF } };
  if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const res = await fetch("/api/" + path, opts);
  if (res.status === 401) { window.location.href = "/login"; throw new Error("unauthorized"); }
  if (raw) return res;
  const data = res.status === 204 ? null : await res.json().catch(() => null);
  if (!res.ok) throw Object.assign(new Error("api error"), { status: res.status, data });
  return data;
};

// download a blob endpoint
window.download = async function (path, filename) {
  const res = await api(path, { raw: true });
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
};

// --- Sidebar (mobile) -------------------------------------------------------
const sidebar = document.getElementById("sidebar");
const overlay = document.getElementById("overlay");
document.getElementById("menuBtn")?.addEventListener("click", () => {
  sidebar.classList.remove("-translate-x-full");
  overlay.classList.remove("hidden");
});
overlay?.addEventListener("click", () => {
  sidebar.classList.add("-translate-x-full");
  overlay.classList.add("hidden");
});

// --- Notifications ----------------------------------------------------------
const bell = document.getElementById("bellBtn");
const panel = document.getElementById("notifPanel");
bell?.addEventListener("click", (e) => { e.stopPropagation(); panel.classList.toggle("hidden"); });
document.addEventListener("click", (e) => {
  if (panel && !panel.contains(e.target) && !bell.contains(e.target)) panel.classList.add("hidden");
});
document.getElementById("markRead")?.addEventListener("click", async () => {
  await api("notifications/read", { method: "POST", body: {} });
  refreshNotifs();
});

async function refreshNotifs() {
  const data = await api("notifications");
  const badge = document.getElementById("unreadBadge");
  if (data.unread_count > 0) { badge.textContent = data.unread_count; badge.classList.remove("hidden"); }
  else badge.classList.add("hidden");
  const list = document.getElementById("notifList");
  if (!data.notifications.length) { list.innerHTML = '<div class="p-4 text-sm text-slate-400">No notifications yet.</div>'; return; }
  list.innerHTML = data.notifications.map((n) =>
    `<div class="border-b border-slate-50 px-4 py-2 text-sm ${!n.read_at ? "bg-slate-100" : ""}">
       <div>${n.data.message ?? ""}</div>
       <div class="text-xs text-slate-400">${new Date(n.created_at).toLocaleString()}</div>
     </div>`).join("");
}

// --- Realtime (Channels WebSocket) -----------------------------------------
// Safari ignores the icon option (always shows its own logo); Chrome/Edge/Firefox honour it.
const NOTIF_ICON = "/static/img/momentum-logo-dark.png";
function osNotify(body) {
  if ("Notification" in window && Notification.permission === "granted") {
    new Notification("Momentum", { body, icon: NOTIF_ICON });
  }
}

function connectWS() {
  if (!WS_TOKEN) return;
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const sock = new WebSocket(`${proto}://${location.hostname}:8000/ws/crm?token=${encodeURIComponent(WS_TOKEN)}`);
  sock.onmessage = (e) => {
    let msg; try { msg = JSON.parse(e.data); } catch { return; }
    if (msg.event === "lead.updated") {
      if (msg.action !== "updated") {
        osNotify(`Lead ${msg.lead.full_name} ${msg.action === "created" ? "captured" : msg.action}`);
      }
      window.dispatchEvent(new CustomEvent("lead-updated", { detail: msg }));
    } else if (msg.event === "notification") {
      refreshNotifs();
      osNotify(msg.payload?.message ?? "New notification");
    }
  };
  sock.onclose = () => setTimeout(connectWS, 3000);
}
if ("Notification" in window && Notification.permission === "default") Notification.requestPermission();
connectWS();
// Poll fallback: keep the bell current even if a realtime message is missed or the socket drops.
setInterval(() => { if (document.visibilityState === "visible") refreshNotifs(); }, 60000);
