/**
 * CMYGO Capture — Popup Script
 * Loads and displays capture statistics.
 */

document.addEventListener("DOMContentLoaded", async () => {
  try {
    const stats = await chrome.runtime.sendMessage({ action: "getStats" });
    document.getElementById("todayCount").textContent = stats.today || 0;
    document.getElementById("totalCount").textContent = stats.total || 0;
  } catch (err) {
    console.error("[CMYGO] Failed to load stats:", err);
  }
});
