"use strict";

document.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-copy-id]");
  if (!button) return;
  const field = document.getElementById(button.dataset.copyId);
  const status = button.parentElement.querySelector("[data-copy-status]");
  if (!field || !status) return;

  try {
    await navigator.clipboard.writeText(field.value);
    status.textContent = "已复制，可粘贴到你选择的平台。";
  } catch (_error) {
    field.focus();
    field.select();
    const copied = document.execCommand("copy");
    status.textContent = copied
      ? "已复制，可粘贴到你选择的平台。"
      : "请选中上方简报并使用 Ctrl+C 复制。";
  }
});
