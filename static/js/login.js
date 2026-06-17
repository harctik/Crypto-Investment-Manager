
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
      el.style.color = chg >= 0 ? "#10b981" : "#f43f5e";
    });

    const inner = document.getElementById("tickerInner");
    if (inner && !inner.dataset.duped) {
      inner.innerHTML += inner.innerHTML;
      inner.dataset.duped = "1";
    }
  } catch (_) {}
}
loadTicker();
setInterval(loadTicker, 30000);

document.getElementById("eyeBtn")?.addEventListener("click", () => {
  const pw = document.getElementById("password");
  const ic = document.getElementById("eyeIcon");
  if (pw.type === "password") {
    pw.type = "text";
    ic.innerHTML = `<path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/>`;
  } else {
    pw.type = "password";
    ic.innerHTML = `<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>`;
  }
});

// ── Enter key ─────────────────────────────────────────────────────────────────
["username", "password"].forEach(id => {
  document.getElementById(id)?.addEventListener("keydown", e => {
    if (e.key === "Enter") submitLogin();
  });
});

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
      const overlay = document.getElementById("successOverlay");
      overlay.classList.add("show");
      setTimeout(() => { window.location.href = data.redirect; }, 2200);
    } else {
      btn.classList.remove("loading");
      showError(err, data.error || "Authentication failed.");
      document.getElementById("loginCard").style.animation = "none";
      document.getElementById("loginCard").offsetHeight;
      document.getElementById("loginCard").style.animation = "shake 0.4s ease";
    }
  } catch (e) {
    btn.classList.remove("loading");
    showError(err, "Request failed: " + e.message);
  }
}

function showError(el, msg) {
  el.textContent = msg;
  el.style.display = "block";
}


const style = document.createElement("style");
style.textContent = `
@keyframes shake {
  0%,100%{ transform: translateX(0); }
  20%    { transform: translateX(-8px); }
  40%    { transform: translateX(8px); }
  60%    { transform: translateX(-5px); }
  80%    { transform: translateX(5px); }
}`;
document.head.appendChild(style);


document.getElementById("showRegBtn")?.addEventListener("click", () => {
  document.getElementById("formLogin").style.display    = "none";
  document.getElementById("formRegister").style.display = "block";
});
document.getElementById("backBtn")?.addEventListener("click", () => {
  document.getElementById("formRegister").style.display = "none";
  document.getElementById("formLogin").style.display    = "block";
});

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
    { pct: 0,   bg: "transparent", label: "Password strength" },
    { pct: 25,  bg: "#f43f5e",     label: "Weak" },
    { pct: 50,  bg: "#f59e0b",     label: "Fair" },
    { pct: 75,  bg: "#06b6d4",     label: "Good" },
    { pct: 100, bg: "#10b981",     label: "Strong" },
  ];
  const lvl = levels[score] || levels[0];
  fill.style.width      = lvl.pct + "%";
  fill.style.background = lvl.bg;
  text.textContent      = lvl.label;
  text.style.color      = lvl.bg;
}

document.getElementById("registerBtn")?.addEventListener("click", async () => {
  const err   = document.getElementById("regErrorBox");
  const user  = document.getElementById("regUser").value.trim();
  const pass  = document.getElementById("regPass").value;
  const pass2 = document.getElementById("regPass2").value;
  const agree = document.getElementById("agreeTerms").checked;

  if (!user || !pass) return showError(err, "Username and password are required.");
  if (pass !== pass2) return showError(err, "Passwords do not match.");
  if (!agree)         return showError(err, "Please accept the terms to continue.");

  try {
    const res  = await fetch("/register", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({username: user, password: pass})
    });
    const data = await res.json();
    if (data.ok) {
      err.style.display    = "none";
      document.getElementById("regUser").value  = "";
      document.getElementById("regPass").value  = "";
      document.getElementById("regPass2").value = "";
      document.getElementById("regEmail").value = "";
      document.getElementById("formRegister").style.display = "none";
      document.getElementById("formLogin").style.display    = "block";
      const info = document.getElementById("errorBox");
      info.style.display    = "block";
      info.style.background = "rgba(16,185,129,0.1)";
      info.style.border     = "1px solid rgba(16,185,129,0.2)";
      info.style.color      = "#10b981";
      info.textContent      = `Account '${user}' created! You can now sign in.`;
    } else {
      showError(err, data.error || "Registration failed.");
    }
  } catch(_) {
    showError(err, "Connection error. Make sure the server is running.");
  }
});