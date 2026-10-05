"use strict";

document.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-copy-id]");
  if (!button) return;
  const field = document.getElementById(button.dataset.copyId);
  const status = button.parentElement.querySelector("[data-copy-status]");
  if (!field || !status) return;
  const english = document.documentElement.lang === "en";
  const copiedMessage = english
    ? "Copied. You can now paste the brief into your chosen platform."
    : "已复制，可粘贴到你选择的平台。";
  const manualMessage = english
    ? "Select the brief above and press Ctrl+C to copy."
    : "请选中上方简报并使用 Ctrl+C 复制。";

  try {
    await navigator.clipboard.writeText(field.value);
    status.textContent = copiedMessage;
  } catch (_error) {
    field.focus();
    field.select();
    const copied = document.execCommand("copy");
    status.textContent = copied ? copiedMessage : manualMessage;
  }
});
