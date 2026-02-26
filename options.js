const CLOSED_ITEMS_KEY = "closedItems";

const generateButton = document.getElementById("generate-markdown");
const copyButton = document.getElementById("copy-markdown");
const syncStatusEl = document.getElementById("sync-status");
const markdownOutputEl = document.getElementById("markdown-output");
const activityLogEl = document.getElementById("activity-log");

function logActivity(message) {
  const div = document.createElement("div");
  div.className = "log-entry";
  const ts = new Date().toLocaleTimeString();
  div.textContent = `[${ts}] ${message}`;
  activityLogEl.prepend(div);
}

function setSyncStatus(text, ok = true) {
  syncStatusEl.textContent = text;
  syncStatusEl.className = "status " + (ok ? "ok" : "error");
}

function formatDateISO(dateMs) {
  const d = new Date(dateMs);
  return d.toISOString().slice(0, 10);
}

function formatTime(dateMs) {
  const d = new Date(dateMs);
  return d.toTimeString().slice(0, 5);
}

function escapeMarkdownLinkText(text) {
  // Very light escaping to keep titles safe in [].
  return (text || "").replace(/\[/g, "\\[").replace(/\]/g, "\\]");
}

function groupByDate(items) {
  const map = new Map();
  for (const item of items) {
    const day = formatDateISO(item.closedAt || Date.now());
    if (!map.has(day)) {
      map.set(day, []);
    }
    map.get(day).push(item);
  }
  return map;
}

function buildMarkdownFromItems(items) {
  if (!items.length) return "";

  const grouped = groupByDate(items);
  const sections = [];

  for (const [day, dayItems] of grouped.entries()) {
    sections.push(`## ${day}`, "");
    for (const item of dayItems) {
      const title = escapeMarkdownLinkText(item.title || item.url || "Untitled");
      const url = item.url || "";
      const closedTime = formatTime(item.closedAt || Date.now());
      sections.push(`- [ ] [${title}](${url})  `);
      sections.push(`  Closed at: ${closedTime}`, "");
    }
  }

  return sections.join("\n");
}

async function generateMarkdownFromQueue() {
  try {
    const result = await chrome.storage.local.get(CLOSED_ITEMS_KEY);
    const items = result[CLOSED_ITEMS_KEY] || [];
    if (!items.length) {
      setSyncStatus("No queued items to write.", true);
      markdownOutputEl.value = "";
      copyButton.disabled = true;
      return;
    }

    const markdown = buildMarkdownFromItems(items);
    markdownOutputEl.value = markdown;
    copyButton.disabled = !markdown;
    setSyncStatus(`Generated markdown for ${items.length} queued tab(s).`, true);
    logActivity(`Generated markdown for ${items.length} queued tab(s).`);
  } catch (e) {
    console.error(e);
    setSyncStatus("Failed to generate markdown. Check console for details.", false);
    logActivity("Error during markdown generation: " + e.message);
  }
}

async function copyMarkdownToClipboard() {
  const text = markdownOutputEl.value;
  if (!text) {
    setSyncStatus("Nothing to copy. Generate markdown first.", false);
    return;
  }

  try {
    await navigator.clipboard.writeText(text);
    setSyncStatus("Markdown copied to clipboard. Paste it into your Obsidian note.", true);
    logActivity("Copied markdown to clipboard.");
  } catch (e) {
    console.error(e);
    setSyncStatus("Failed to copy to clipboard.", false);
    logActivity("Error copying markdown to clipboard: " + e.message);
  }
}

generateButton.addEventListener("click", () => {
  generateMarkdownFromQueue();
});

copyButton.addEventListener("click", () => {
  copyMarkdownToClipboard();
});

// Listen for new closed items while this page is open.
chrome.runtime.onMessage.addListener((message) => {
  if (message && message.type === "tab-closed-logged") {
    const item = message.item;
    logActivity(`Closed & queued: ${item.title || item.url}`);
  }
});

// On initial load, check if there are any queued items.
(async () => {
  try {
    const result = await chrome.storage.local.get(CLOSED_ITEMS_KEY);
    const items = result[CLOSED_ITEMS_KEY] || [];
    if (items.length) {
      logActivity(`There are currently ${items.length} queued closed tab(s) ready to sync.`);
      setSyncStatus("Queued items detected. Click Generate to turn them into markdown.", true);
      copyButton.disabled = true;
    } else {
      setSyncStatus("No queued items yet. As tabs are auto-closed, they will appear here.", true);
      copyButton.disabled = true;
    }
  } catch (e) {
    console.error(e);
  }
})(); 

