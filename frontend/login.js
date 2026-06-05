const form = document.querySelector("#loginForm");
const username = document.querySelector("#username");
const password = document.querySelector("#password");
const button = document.querySelector("#loginButton");
const message = document.querySelector("#loginMessage");

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  button.disabled = true;
  button.textContent = "登录中";
  message.textContent = "";

  try {
    const response = await fetch("/agent/v1/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username: username.value.trim(),
        password: password.value,
      }),
    });
    const payload = await response.json();
    if (!response.ok || payload.result?.code !== 0) {
      throw new Error(payload.result?.des || "登录失败");
    }
    window.location.href = "/";
  } catch (error) {
    message.textContent = error.message || "登录失败";
    button.textContent = "登录";
    button.disabled = false;
  }
});
