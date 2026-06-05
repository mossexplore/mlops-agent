const logoutButton = document.querySelector("#logoutButton");

async function syncSessionState() {
  if (!logoutButton) return;
  try {
    const response = await fetch("/agent/v1/auth/me");
    if (response.status === 401) {
      window.location.href = "/login";
      return;
    }
    const payload = await response.json();
    logoutButton.hidden = !payload.result?.data?.authEnabled;
  } catch (_error) {
    logoutButton.hidden = true;
  }
}

async function logout() {
  await fetch("/agent/v1/auth/logout", { method: "POST" });
  window.location.href = "/login";
}

logoutButton?.addEventListener("click", () => {
  logout().catch(() => {
    window.location.href = "/login";
  });
});

syncSessionState();
