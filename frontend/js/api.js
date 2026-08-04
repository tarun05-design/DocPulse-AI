// ================================================================
// DocPulse AI — Central API Client
// ================================================================

const API_BASE = (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1")
  ? "http://localhost:5000/api"
  : (window.DOCPULSE_API_URL || "https://docpulse-ai-backend.onrender.com/api");

// ─── Session helpers ───

function getToken() {
  return localStorage.getItem("docpulse_token");
}

function setSession(token, user) {
  localStorage.setItem("docpulse_token", token);
  localStorage.setItem("docpulse_user", JSON.stringify(user));
}

function clearSession() {
  localStorage.removeItem("docpulse_token");
  localStorage.removeItem("docpulse_user");
}

function getUser() {
  const raw = localStorage.getItem("docpulse_user");
  return raw ? JSON.parse(raw) : null;
}

function requireAuth() {
  if (!getToken()) {
    const current = encodeURIComponent(window.location.pathname.split("/").pop() + window.location.search);
    window.location.href = `login.html?reason=auth_required&redirect=${current}`;
    return false;
  }
  return true;
}

async function confirmLogout(e) {
  if (e) e.preventDefault();
  const confirmed = await showConfirm(
    "Log Out of DocPulse AI?",
    "Are you sure you want to end your session?"
  );
  if (confirmed) {
    clearSession();
    showToast("Logged out successfully.", "info");
    setTimeout(() => {
      window.location.href = "login.html";
    }, 400);
  }
}

function renderNavbar() {
  const nav = document.querySelector(".topbar nav");
  if (!nav) return;

  const user = getUser();
  const currentPath = window.location.pathname.split("/").pop() || "index.html";

  if (user) {
    const initial = (user.name || user.email || "U").charAt(0).toUpperCase();
    nav.innerHTML = `
      <a href="index.html" class="${currentPath === "index.html" ? "active" : ""}">Home</a>
      <a href="upload.html" class="${currentPath === "upload.html" ? "active" : ""}">Workspace</a>
      <div class="profile-dropdown-wrap">
        <button class="profile-trigger" id="profileDropdownBtn" aria-label="User profile menu">
          <div class="profile-avatar">${initial}</div>
          <span>Profile</span>
          <span style="font-size:0.68rem;opacity:0.75;">▼</span>
        </button>
        <div class="profile-menu" id="profileDropdownMenu">
          <div class="profile-menu-header">
            <div class="name">${user.name || "User"}</div>
            <div class="email" title="${user.email || ''}">${user.email || ""}</div>
          </div>
          <a href="dashboard.html" class="profile-item">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="9" rx="1"/><rect x="14" y="3" width="7" height="5" rx="1"/><rect x="14" y="12" width="7" height="9" rx="1"/><rect x="3" y="16" width="7" height="5" rx="1"/></svg>
            Dashboard
          </a>
          <div class="profile-menu-divider"></div>
          <button class="logout-item" id="navLogoutBtn">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
            Log Out
          </button>
        </div>
      </div>
    `;

    const btn = document.getElementById("profileDropdownBtn");
    const menu = document.getElementById("profileDropdownMenu");
    if (btn && menu) {
      btn.onclick = (e) => {
        e.stopPropagation();
        menu.classList.toggle("show");
      };
      document.addEventListener("click", () => menu.classList.remove("show"));
    }

    const logoutBtn = document.getElementById("navLogoutBtn");
    if (logoutBtn) {
      logoutBtn.onclick = (e) => {
        menu.classList.remove("show");
        confirmLogout(e);
      };
    }
  } else {
    nav.innerHTML = `
      <a href="index.html" class="${currentPath === "index.html" ? "active" : ""}">Home</a>
      <a href="login.html" class="${currentPath === "login.html" ? "active" : ""}">Sign In</a>
      <a href="login.html" class="nav-cta">Get Started</a>
    `;
  }
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", renderNavbar);
} else {
  renderNavbar();
}

// ─── Toast Notifications ───

function _ensureToastContainer() {
  let container = document.getElementById("toastContainer");
  if (!container) {
    container = document.createElement("div");
    container.id = "toastContainer";
    container.className = "toast-container";
    document.body.appendChild(container);
  }
  return container;
}

function showToast(message, type = "info", duration = 4000) {
  const container = _ensureToastContainer();
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;

  const icons = { success: "✓", error: "✕", info: "ℹ" };
  toast.innerHTML = `<span>${icons[type] || "ℹ"}</span><span>${message}</span>`;

  container.appendChild(toast);

  setTimeout(() => {
    toast.classList.add("hiding");
    setTimeout(() => toast.remove(), 300);
  }, duration);
}

// ─── Confirm Dialog ───

function showConfirm(title, message) {
  return new Promise((resolve) => {
    const overlay = document.createElement("div");
    overlay.className = "dialog-overlay";
    overlay.innerHTML = `
      <div class="dialog-box">
        <h3>${title}</h3>
        <p>${message}</p>
        <div class="dialog-actions">
          <button class="secondary" id="dialogCancel">Cancel</button>
          <button class="danger" id="dialogConfirm">Delete</button>
        </div>
      </div>
    `;
    document.body.appendChild(overlay);

    overlay.querySelector("#dialogCancel").onclick = () => {
      overlay.remove();
      resolve(false);
    };
    overlay.querySelector("#dialogConfirm").onclick = () => {
      overlay.remove();
      resolve(true);
    };
    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) {
        overlay.remove();
        resolve(false);
      }
    });
  });
}

// ─── Core Request ───

async function apiRequest(path, { method = "GET", body, isForm = false, timeout = 180000 } = {}) {
  const headers = {};
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (!isForm && body) headers["Content-Type"] = "application/json";

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);

  try {
    const res = await fetch(`${API_BASE}${path}`, {
      method,
      headers,
      body: isForm ? body : body ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });

    clearTimeout(timer);
    const data = await res.json().catch(() => ({}));

    // Auto-redirect on expired/invalid JWT
    if (res.status === 401 && path !== "/auth/login" && path !== "/auth/register") {
      clearSession();
      showToast("Session expired. Please sign in again.", "error");
      setTimeout(() => (window.location.href = "login.html"), 1500);
      throw new Error("Session expired");
    }

    if (!res.ok) {
      throw new Error(data.error || `Request failed (${res.status})`);
    }
    return data;
  } catch (err) {
    clearTimeout(timer);
    if (err.name === "AbortError") {
      throw new Error("Request timed out. The server may be processing a large document.");
    }
    throw err;
  }
}

// ─── API Methods ───

const Api = {
  register: (name, email, password) =>
    apiRequest("/auth/register", { method: "POST", body: { name, email, password } }),
  login: (email, password) =>
    apiRequest("/auth/login", { method: "POST", body: { email, password } }),
  me: () => apiRequest("/auth/me"),

  updateProfile: (name) =>
    apiRequest("/auth/profile", { method: "PUT", body: { name } }),
  changePassword: (currentPassword, newPassword) =>
    apiRequest("/auth/password", { method: "PUT", body: { current_password: currentPassword, new_password: newPassword } }),

  listDocuments: (page = 1, perPage = 20) =>
    apiRequest(`/documents?page=${page}&per_page=${perPage}`),
  getDocument: (id) => apiRequest(`/documents/${id}`),
  uploadDocument: (file) => {
    const form = new FormData();
    form.append("file", file);
    return apiRequest("/documents/upload", { method: "POST", body: form, isForm: true });
  },
  deleteDocument: (id) =>
    apiRequest(`/documents/${id}`, { method: "DELETE" }),
  reprocessDocument: (id) =>
    apiRequest(`/documents/${id}/reprocess`, { method: "POST" }),
  downloadDocument: (id, filename) => {
    const token = getToken();
    fetch(`${API_BASE}/documents/${id}/download`, {
      headers: token ? { "Authorization": `Bearer ${token}` } : {}
    })
    .then(res => {
      if (!res.ok) throw new Error("Download failed");
      return res.blob();
    })
    .then(blob => {
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename || "document";
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    })
    .catch(err => showToast(err.message, "error"));
  },

  askQuestion: (docId, question) =>
    apiRequest(`/chat/${docId}`, { method: "POST", body: { question } }),
  chatHistory: (docId) => apiRequest(`/chat/${docId}/history`),

  dashboardSummary: () => apiRequest("/dashboard/summary"),
};

// ─── Utility ───

function formatFileSize(bytes) {
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / (1024 * 1024)).toFixed(1) + " MB";
}

function timeAgo(dateStr) {
  if (!dateStr) return "";
  let iso = dateStr;
  if (!iso.endsWith("Z") && !iso.includes("+")) {
    iso += "Z";
  }
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days < 7) return `${days}d ago`;
  return new Date(iso).toLocaleDateString();
}
