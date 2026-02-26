## Tab Watch Later → Obsidian

Automatically close old tabs in Chrome and send them into a **Watch Later** markdown file inside your Obsidian vault, so your browser stays focused while nothing gets lost.

### What it does

- **Watches all tabs** in your Chrome/Chromium browser.
- If a tab has not been **active (focused) for more than 1 day**, it is:
  - **Closed automatically** (unpinned, normal HTTP/HTTPS pages only).
  - **Logged into a queue** with its title, URL, and timestamps.
- From the extension’s **options page**, you can:
  - **Generate markdown** for all queued closed tabs.
  - **Copy that markdown to your clipboard** and paste it into any note inside your Obsidian vault (for example `Watch Later.md`).
  - Entries are emitted as tasks like:
    - `- [ ] [Great article](https://example.com)  `
      `Closed at: 18:42`

Think of it as a YouTube **Watch Later** playlist, but for the entire web, and saved straight into Obsidian.

### Folder layout

- `manifest.json` – Chrome extension manifest (MV3).
- `background.js` – Service worker that tracks tabs, detects stale ones, closes them, and logs into a queue, and forwards new items to the local Obsidian helper when available.
- `options.html` – Minimal dark UI for seeing activity and manually generating markdown from queued items.
- `options.js` – Frontend logic for generating/copying markdown from queued entries.
- `obsidian_writer.py` – Optional local helper server that writes closed tabs directly into your Obsidian vault markdown file.

### Installing the extension (Chrome / Chromium)

1. Open Chrome and go to `chrome://extensions/`.
2. Enable **Developer mode** (toggle in the top-right).
3. Click **Load unpacked**.
4. Select this folder:
   - `/home/rickaurs/Desktop/playground/vibe-coded-ai-projects/tab handler`
5. You should now see **Tab Watch Later to Obsidian** in your extensions list.

### Initial setup (extension only)

1. Click the extension icon in the toolbar and choose **Options**, or use the **Details → Extension options** link from `chrome://extensions/`.
2. In the options page:
   - Create or open a note in Obsidian where you want your Watch Later links to live (for example `Watch Later.md`).
   - Keep that Obsidian note handy; we’ll paste markdown into it from the extension.

### Daily usage

- As you browse and open lots of tabs:
  - The background script notes when each tab was first seen and when it was last active (focused).
  - Every ~30 minutes it checks for tabs that have been **inactive for more than 1 day** (24 hours) and:
    - Skips pinned tabs.
    - Skips internal pages like `chrome://` and `chrome-extension://`.
    - Closes the tab and adds it to the **closed-items queue**.
- In your **Watch Later** markdown file:
  - Entries are grouped by **date** with headings like `## 2026-02-26`.
  - Each entry is a checkbox task:
    - `- [ ] [Deep learning talk](https://example.com/…)  `
      `Closed at: 09:15`
  - When you finish something, you can tick it off in Obsidian by changing `[ ]` to `[x]`.

### Automatic writing via local helper (more automatic)

To have closed tabs written straight into a markdown file inside your Obsidian vault (no copy–paste), you can run the bundled helper server.

1. Open `obsidian_writer.py` in an editor.
2. Set **`VAULT_MARKDOWN_PATH`** near the top to the full path of your target note, for example:

   ```python
   VAULT_MARKDOWN_PATH = "/home/youruser/Documents/Obsidian/MyVault/Watch Later.md"
   ```

3. In a terminal, from this folder, run:

   ```bash
   python obsidian_writer.py
   ```

   You should see a message like:

   ```text
   Obsidian writer server listening on http://127.0.0.1:8787/append
   Writing to: /.../Watch Later.md
   ```

4. Leave this terminal running in the background.

Now, whenever the extension auto-closes a stale tab:

- It still adds the item to its internal **queue** (for safety).
- It also sends the item to `http://127.0.0.1:8787/append`, and the helper appends it directly into your Obsidian note, grouped by date, as checkbox tasks.

If the helper is not running, nothing breaks; items remain queued and you can still use the manual markdown generation flow below.

### Manual syncing from the extension (fallback / no helper)

1. Open the extension’s **options** page.
2. Click **“Generate markdown from queued tabs”**:
   - This turns all queued closed tabs into grouped markdown (by day) in the textarea.
3. Click **“Copy markdown to clipboard”**.
4. Switch to your chosen Obsidian note (for example `Watch Later.md`) and **paste**.
5. Optionally, clear or archive pasted sections in Obsidian as you work through them.

### Customisation ideas (future improvements)

- Make the **age threshold** configurable (e.g. 3 hours, 2 days, 1 week).
- Allow multiple queues / files, such as:
  - `Videos – Watch Later.md`
  - `Deep Reads – Watch Later.md`
  - `Quick Skims.md`
- Add basic **topic tags** (e.g. `#ai`, `#frontend`, `#philosophy`) either manually or via an AI model.
- Build an Obsidian plugin or dataview that surfaces these tasks in a dedicated “Watch Later” dashboard.

***
This project is totaly vibe coded using cursor ###.
