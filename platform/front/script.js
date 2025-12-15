// script.js
const HOST = window.location.hostname === "localhost" ? "http://localhost" : window.location.origin;
const CREATE_PORT = "5001";
const READ_PORT = "5002";

const registerForm = document.getElementById("registerForm");
const loginForm = document.getElementById("loginForm");
const regMsg = document.getElementById("reg_msg");
const loginMsg = document.getElementById("login_msg");
const userInfo = document.getElementById("userInfo");
const userDetails = document.getElementById("userDetails");
const logoutBtn = document.getElementById("logoutBtn");

// ---------------------- INSCRIPTION ----------------------
registerForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  regMsg.textContent = "";

  const username = document.getElementById("reg_username").value.trim();
  const email = document.getElementById("reg_email").value.trim();
  const password = document.getElementById("reg_password").value;

  try {
    const res = await fetch(`${HOST}:${CREATE_PORT}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, email, password })
    });

    const data = await res.json();

    if (!res.ok) {
      regMsg.textContent = data.error || data.message || "Erreur";
    } else {
      regMsg.style.color = "green";
      regMsg.textContent = "Inscription réussie — connecte-toi.";
      registerForm.reset();

      setTimeout(() => {
        regMsg.textContent = "";
        regMsg.style.color = "red";
      }, 4000);
    }
  } catch (err) {
    regMsg.textContent = "Impossible de joindre le serveur (create).";
  }
});


// ---------------------- CONNEXION ----------------------
loginForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  loginMsg.textContent = "";

  const identifier = document.getElementById("login_identifier").value.trim();
  const password = document.getElementById("login_password").value;

  try {
    const res = await fetch(`${HOST}:${READ_PORT}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ identifier, password })
    });

    const data = await res.json();

    if (!res.ok) {
      loginMsg.textContent = data.error || "Erreur";
    } else {
      // Stocker token + user
      localStorage.setItem("token", data.token);
      localStorage.setItem("user", JSON.stringify(data.user));

      // 🔥 REDIRECTION IMMÉDIATE
      window.location.href = "accueil.html";
      return;
    }

  } catch (err) {
    loginMsg.textContent = "Impossible de joindre le serveur (read).";
  }
});


// ---------------------- AFFICHER USER ----------------------
function showUser(user) {
  userInfo.style.display = "block";
  userDetails.textContent = `#${user.id} — ${user.username} (${user.email})`;
}


// ---------------------- DÉCONNEXION ----------------------
logoutBtn.addEventListener("click", () => {
  localStorage.removeItem("token");
  localStorage.removeItem("user");
  userInfo.style.display = "none";
});


// ---------------------- AUTO-REDIRECTION SI DÉJÀ CONNECTÉ ----------------------
window.addEventListener("load", () => {
  const token = localStorage.getItem("token");
  const user = localStorage.getItem("user");

  if (token && user) {
    window.location.href = "accueil.html";
    return;
  }
});
