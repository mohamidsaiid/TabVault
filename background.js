const STALE_THRESHOLD_MS = 24 * 60 * 60 * 1000; // 1 day
const ALARM_NAME = "check-stale-tabs";
const ALARM_PERIOD_MINUTES = 30;

// Keys in chrome.storage.local
const TAB_METADATA_KEY = "tabMetadata";
const CLOSED_ITEMS_KEY = "closedItems";

/**
 * Load tab metadata map from storage.
 * Shape: {
 *   [tabId: string]: {
 *     openedAt: number,
 *     lastActiveAt: number,
 *     firstUrl: string,
 *     currentUrl: string,
 *     title: string
 *   }
 * }
 */
async function loadTabMetadata() {
  const result = await chrome.storage.local.get(TAB_METADATA_KEY);
  return result[TAB_METADATA_KEY] || {};
}

async function saveTabMetadata(map) {
  await chrome.storage.local.set({ [TAB_METADATA_KEY]: map });
}

/**
 * Load closed items array from storage.
 * Each item: { openedAt, closedAt, url, title }
 */
async function loadClosedItems() {
  const result = await chrome.storage.local.get(CLOSED_ITEMS_KEY);
  return result[CLOSED_ITEMS_KEY] || [];
}

async function saveClosedItems(items) {
  await chrome.storage.local.set({ [CLOSED_ITEMS_KEY]: items });
}

function isSupportedHttpUrl(url) {
  if (!url) return false;
  try {
    const u = new URL(url);
    return u.protocol === "http:" || u.protocol === "https:";
  } catch {
    return false;
  }
}

async function ensureAlarm() {
  const existing = await chrome.alarms.get(ALARM_NAME);
  if (!existing) {
    await chrome.alarms.create(ALARM_NAME, {
      periodInMinutes: ALARM_PERIOD_MINUTES,
      delayInMinutes: 1
    });
  }
}

async function initialiseExistingTabs() {
  const [tabs, metadata] = await Promise.all([
    chrome.tabs.query({}),
    loadTabMetadata()
  ]);

  const now = Date.now();
  let changed = false;

  for (const tab of tabs) {
    if (!isSupportedHttpUrl(tab.url)) continue;
    const key = String(tab.id);
    if (!metadata[key]) {
      metadata[key] = {
        openedAt: now,
        lastActiveAt: now,
        firstUrl: tab.url || "",
        currentUrl: tab.url || "",
        title: tab.title || ""
      };
      changed = true;
    }
  }

  if (changed) {
    await saveTabMetadata(metadata);
  }
}

async function handleTabCreated(tab) {
  if (!isSupportedHttpUrl(tab.url)) return;
  const metadata = await loadTabMetadata();
  const now = Date.now();
  metadata[String(tab.id)] = {
    openedAt: now,
    lastActiveAt: now,
    firstUrl: tab.url || "",
    currentUrl: tab.url || "",
    title: tab.title || ""
  };
  await saveTabMetadata(metadata);
}

async function handleTabUpdated(tabId, changeInfo, tab) {
  if (!changeInfo.url && !changeInfo.title && changeInfo.status !== "complete") {
    return;
  }

  const metadata = await loadTabMetadata();
  const key = String(tabId);
  const entry = metadata[key];

  if (!entry) {
    // Initialise if we didn't know about this tab yet.
    if (!isSupportedHttpUrl(tab.url)) return;
    const now = Date.now();
    metadata[key] = {
      openedAt: now,
      lastActiveAt: now,
      firstUrl: tab.url || "",
      currentUrl: tab.url || "",
      title: tab.title || changeInfo.title || ""
    };
  } else {
    if (isSupportedHttpUrl(tab.url)) {
      entry.currentUrl = tab.url || entry.currentUrl;
    }
    if (tab.title || changeInfo.title) {
      entry.title = tab.title || changeInfo.title || entry.title;
    }
  }

  await saveTabMetadata(metadata);
}

async function handleTabRemoved(tabId) {
  const metadata = await loadTabMetadata();
  const key = String(tabId);
  if (metadata[key]) {
    delete metadata[key];
    await saveTabMetadata(metadata);
  }
}

async function closeAndLogTab(tab, metaEntry) {
  if (!metaEntry) return;

  const now = Date.now();
  const closedItem = {
    openedAt: metaEntry.openedAt,
    closedAt: now,
    url: metaEntry.currentUrl || metaEntry.firstUrl,
    title: metaEntry.title || metaEntry.currentUrl || metaEntry.firstUrl
  };

  // Close the tab first (ignore errors if already closed).
  try {
    await chrome.tabs.remove(tab.id);
  } catch (e) {
    // Tab might already be gone.
  }

  // Append to closed-items queue.
  const items = await loadClosedItems();
  items.push(closedItem);
  await saveClosedItems(items);

  // Try to send directly to local Obsidian writer helper (if running).
  try {
    await fetch("http://127.0.0.1:8787/append", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ items: [closedItem] })
    });
  } catch (e) {
    // Helper not running or unreachable; queued items remain for manual export.
  }

  // Notify any open logger/options pages so they can write to Obsidian if configured.
  chrome.runtime.sendMessage({ type: "tab-closed-logged", item: closedItem }).catch(() => {
    // No listeners, that's fine.
  });
}

async function checkForStaleTabs() {
  const [tabs, metadata] = await Promise.all([
    chrome.tabs.query({}),
    loadTabMetadata()
  ]);
  const now = Date.now();

  for (const tab of tabs) {
    // Never touch pinned or special/internal pages.
    if (tab.pinned) continue;
    if (!isSupportedHttpUrl(tab.url)) continue;

    const key = String(tab.id);
    let entry = metadata[key];
    if (!entry) {
      // If we don't know this tab yet, treat it as just seen now.
      entry = {
        openedAt: now,
        lastActiveAt: now,
        firstUrl: tab.url || "",
        currentUrl: tab.url || "",
        title: tab.title || ""
      };
      metadata[key] = entry;
    }

    // Close based on time since the tab was last active (focused), not since opened.
    const lastActiveAt = entry.lastActiveAt || entry.openedAt || now;
    const inactiveDuration = now - lastActiveAt;
    if (inactiveDuration >= STALE_THRESHOLD_MS) {
      await closeAndLogTab(tab, entry);
      delete metadata[key];
    }
  }

  await saveTabMetadata(metadata);
}

// Setup alarms and initial state.
chrome.runtime.onInstalled.addListener(async () => {
  await ensureAlarm();
  await initialiseExistingTabs();
});

chrome.runtime.onStartup.addListener(async () => {
  await ensureAlarm();
  await initialiseExistingTabs();
});

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === ALARM_NAME) {
    checkForStaleTabs();
  }
});

chrome.tabs.onCreated.addListener((tab) => {
  handleTabCreated(tab);
});

// Update lastActiveAt whenever the user focuses a tab.
chrome.tabs.onActivated.addListener(async (activeInfo) => {
  const metadata = await loadTabMetadata();
  const key = String(activeInfo.tabId);
  const now = Date.now();

  if (!metadata[key]) {
    try {
      const tab = await chrome.tabs.get(activeInfo.tabId);
      if (!isSupportedHttpUrl(tab.url)) return;
      metadata[key] = {
        openedAt: now,
        lastActiveAt: now,
        firstUrl: tab.url || "",
        currentUrl: tab.url || "",
        title: tab.title || ""
      };
    } catch {
      return;
    }
  } else {
    metadata[key].lastActiveAt = now;
  }

  await saveTabMetadata(metadata);
});

chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  handleTabUpdated(tabId, changeInfo, tab);
});

chrome.tabs.onRemoved.addListener((tabId) => {
  handleTabRemoved(tabId);
});

