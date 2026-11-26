
"use strict";

const TICKER_MAP = {
  bitcoin: "t-btc", ethereum: "t-eth", solana: "t-sol",
  binancecoin: "t-bnb", cardano: "t-ada", ripple: "t-xrp"
};
const COIN_NAMES = Object.keys(TICKER_MAP);

async function loadTicker() {
  try {
    const ids = COIN_NAMES.join(",");
    const url = `https://api.coingecko.com/api/v3/simple/price?ids=${ids}&vs_currencies=usd&include_24hr_change=true`;
    const r   = await fetch(url);
    const d   = await r.json();
    Object.entries(TICKER_MAP).forEach(([cid, elId]) => {
      const el = document.getElementById(elId);
      if (!el || !d[cid]) return;
      const price = d[cid].usd;
      const chg   = d[cid].usd_24h_change || 0;
      el.textContent = `$${price.toLocaleString("en", {maximumFractionDigits: 2})}`;
      el.style.color = chg >= 0 ? "var(--green)" : "var(--red)";
    });
  } catch (_) {}
}
loadTicker();
setInterval(loadTicker, 30000);

document.getElementById("eyeBtn")?.addEventListener("click", e => {
  const btn = e.currentTarget;
  const pw  = document.getElementById("password");
  const ic  = document.getElementById("eyeIcon");
  const show = pw.type === "password";
  pw.type = show ? "text" : "password";
  btn.setAttribute("aria-pressed", String(show));
  btn.setAttribute("aria-label", show ? "Hide password" : "Show password");
  ic.innerHTML = show
    ? `<path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/>`
    : `<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>`;
});

// ── Enter key ─────────────────────────────────────────────────────────────────
function submitOnEnter(ids, action) {
  ids.forEach(id => {
    document.getElementById(id)?.addEventListener("keydown", e => {
      if (e.key === "Enter") action();
    });
  });
}
submitOnEnter(["username", "password"], submitLogin);
submitOnEnter(["regUser", "regPass", "regPass2"], submitRegister);

document.getElementById("loginBtn")?.addEventListener("click", submitLogin);

async function submitLogin() {
  const btn  = document.getElementById("loginBtn");
  const err  = document.getElementById("errorBox");
  const user = document.getElementById("username").value.trim();
  const pass = document.getElementById("password").value;

  if (!user || !pass) {
    showError(err, "Please enter your username and password.");
    return;
  }

  btn.classList.add("loading");
  err.style.display = "none";

  try {
    const res  = await fetch("/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: user, password: pass })
    });
    let data;
    const text = await res.text();
    try { data = JSON.parse(text); } catch(_) {
      btn.classList.remove("loading");
      showError(err, "Unexpected server response (status " + res.status + ")");
      return;
    }
    if (data.ok) {
      document.getElementById("successOverlay").classList.add("show");
      requestAnimationFrame(() => { document.getElementById("progressBar").style.width = "100%"; });
      setTimeout(() => { window.location.href = data.redirect; }, 700);
    } else {
      btn.classList.remove("loading");
      showError(err, data.error || "Sign-in failed.");
    }
  } catch (e) {
    btn.classList.remove("loading");
    showError(err, "Request failed: " + e.message);
  }
}

function showError(el, msg) {
  el.classList.remove("success");
  el.textContent = msg;
  el.style.display = "block";
}

function showForm(name) {
  document.getElementById("formLogin").style.display    = name === "login" ? "block" : "none";
  document.getElementById("formRegister").style.display = name === "register" ? "block" : "none";
}
document.getElementById("showRegBtn")?.addEventListener("click", () => showForm("register"));
document.getElementById("backBtn")?.addEventListener("click", () => showForm("login"));

function checkStrength(val) {
  const fill = document.getElementById("strengthFill");
  const text = document.getElementById("strengthText");
  if (!fill) return;
  let score = 0;
  if (val.length >= 8)                    score++;
  if (/[A-Z]/.test(val))                  score++;
  if (/[0-9]/.test(val))                  score++;
  if (/[^A-Za-z0-9]/.test(val))          score++;
  const levels = [
    { pct: 0,   color: "var(--text2)", label: "Password strength" },
    { pct: 25,  color: "var(--red)",   label: "Weak" },
    { pct: 50,  color: "var(--amber)", label: "Fair" },
    { pct: 75,  color: "var(--cyan)",  label: "Good" },
    { pct: 100, color: "var(--green)", label: "Strong" },
  ];
  const lvl = levels[score] || levels[0];
  fill.style.width      = lvl.pct + "%";
  fill.style.background = lvl.color;
  text.textContent      = lvl.label;
  text.style.color      = lvl.color;
}

document.getElementById("registerBtn")?.addEventListener("click", submitRegister);

async function submitRegister() {
  const err   = document.getElementById("regErrorBox");
  const user  = document.getElementById("regUser").value.trim();
  const pass  = document.getElementById("regPass").value;
  const pass2 = document.getElementById("regPass2").value;

  if (!user || !pass) return showError(err, "Username and password are required.");
  if (pass !== pass2) return showError(err, "Passwords do not match.");

  try {
    const res  = await fetch("/register", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({username: user, password: pass})
    });
    const data = await res.json();
    if (data.ok) {
      err.style.display = "none";
      ["regUser", "regPass", "regPass2"].forEach(id => { document.getElementById(id).value = ""; });
      checkStrength("");
      showForm("login");
      document.getElementById("username").value = user;
      const info = document.getElementById("errorBox");
      info.classList.add("success");
      info.textContent   = `Account '${user}' created. You can now sign in.`;
      info.style.display = "block";
    } else {
      showError(err, data.error || "Registration failed.");
    }
  } catch(_) {
    showError(err, "Connection error. Make sure the server is running.");
  }
}
