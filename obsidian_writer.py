import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse
from datetime import datetime

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
#
# Set this to the full path of the markdown file inside your Obsidian vault
# where you want closed tabs to be recorded. If the file does not exist, it
# will be created automatically.
#
# Example:
#   VAULT_MARKDOWN_PATH = "/home/youruser/Documents/Obsidian/MyVault/Watch Later.md"
#

VAULT_MARKDOWN_PATH = "/home/rickaurs/Desktop/playground/theVault/Watch Later.md"


def ensure_file_exists():
  directory = os.path.dirname(VAULT_MARKDOWN_PATH)
  if directory and not os.path.isdir(directory):
    os.makedirs(directory, exist_ok=True)
  if not os.path.isfile(VAULT_MARKDOWN_PATH):
    with open(VAULT_MARKDOWN_PATH, "w", encoding="utf-8") as f:
      f.write("# Watch Later\n\n")


def format_date_iso(ms: int) -> str:
  dt = datetime.fromtimestamp(ms / 1000.0)
  return dt.strftime("%Y-%m-%d")


def format_time_hm(ms: int) -> str:
  dt = datetime.fromtimestamp(ms / 1000.0)
  return dt.strftime("%H:%M")


def escape_markdown_link_text(text: str) -> str:
  return text.replace("[", "\\[").replace("]", "\\]")


def append_items_to_markdown(items):
  if not items:
    return

  ensure_file_exists()

  # Read current file content.
  with open(VAULT_MARKDOWN_PATH, "r", encoding="utf-8") as f:
    existing = f.read()

  lines = existing.splitlines()

  # Group by closed date.
  grouped = {}
  for item in items:
    closed_at = item.get("closedAt") or item.get("closed_at") or 0
    day = format_date_iso(closed_at) if closed_at else format_date_iso(int(datetime.now().timestamp() * 1000))
    grouped.setdefault(day, []).append(item)

  for day, day_items in grouped.items():
    heading = f"## {day}"
    try:
      idx = next(i for i, line in enumerate(lines) if line.strip() == heading)
    except StopIteration:
      # Add new day section at end.
      if lines and lines[-1].strip() != "":
        lines.append("")
      lines.append(heading)
      lines.append("")
      idx = len(lines) - 2

    insert_at = idx + 1
    while insert_at < len(lines) and (lines[insert_at].startswith("- [") or lines[insert_at].strip() == ""):
      insert_at += 1

    new_lines = []
    for item in day_items:
      url = item.get("url") or ""
      title = item.get("title") or url or "Untitled"
      closed_at = item.get("closedAt") or item.get("closed_at") or 0
      closed_time = format_time_hm(closed_at) if closed_at else ""
      safe_title = escape_markdown_link_text(title)

      new_lines.append(f"- [ ] [{safe_title}]({url})  ")
      if closed_time:
        new_lines.append(f"  Closed at: {closed_time}")
      new_lines.append("")

    lines[insert_at:insert_at] = new_lines

  new_content = "\n".join(lines) + ("\n" if not existing.endswith("\n") else "")

  with open(VAULT_MARKDOWN_PATH, "w", encoding="utf-8") as f:
    f.write(new_content)


class RequestHandler(BaseHTTPRequestHandler):
  def _send_json(self, status_code, payload):
    body = json.dumps(payload).encode("utf-8")
    self.send_response(status_code)
    self.send_header("Content-Type", "application/json")
    self.send_header("Content-Length", str(len(body)))
    self.end_headers()
    self.wfile.write(body)

  def do_POST(self):
    parsed = urlparse(self.path)
    if parsed.path != "/append":
      self._send_json(404, {"error": "Not found"})
      return

    content_length = int(self.headers.get("Content-Length", "0") or "0")
    raw_body = self.rfile.read(content_length)
    try:
      payload = json.loads(raw_body.decode("utf-8"))
      items = payload.get("items") or []
      if not isinstance(items, list):
        raise ValueError("items must be a list")
    except Exception as exc:
      self._send_json(400, {"error": f"Invalid JSON: {exc}"})
      return

    try:
      append_items_to_markdown(items)
    except Exception as exc:
      self._send_json(500, {"error": f"Failed to append items: {exc}"})
      return

    self._send_json(200, {"status": "ok", "count": len(items)})

  def log_message(self, format, *args):
    # Quieter logging; print to stdout only.
    print("%s - - [%s] %s" % (self.client_address[0], self.log_date_time_string(), format % args))


def run_server(port: int = 8787):
  ensure_file_exists()
  server_address = ("127.0.0.1", port)
  httpd = HTTPServer(server_address, RequestHandler)
  print(f"Obsidian writer server listening on http://{server_address[0]}:{server_address[1]}/append")
  print(f"Writing to: {VAULT_MARKDOWN_PATH}")
  httpd.serve_forever()


if __name__ == "__main__":
  if VAULT_MARKDOWN_PATH == "/path/to/your/Obsidian/vault/Watch Later.md":
    print("Please edit obsidian_writer.py and set VAULT_MARKDOWN_PATH to your Obsidian markdown file path.")
  else:
    run_server()

