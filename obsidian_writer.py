import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse
from datetime import datetime
from urllib import request as urllib_request, error as urllib_error
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
#
def load_dotenv(path: str = ".env") -> None:
  """
  Very small .env loader: KEY=VALUE per line, # for comments.
  Does not overwrite existing environment variables.
  """
  env_path = Path(path)
  if not env_path.is_file():
    return

  for raw_line in env_path.read_text(encoding="utf-8").splitlines():
    line = raw_line.strip()
    if not line or line.startswith("#"):
      continue
    if "=" not in line:
      continue
    key, value = line.split("=", 1)
    key = key.strip()
    value = value.strip().strip('"').strip("'")
    if key and key not in os.environ:
      os.environ[key] = value


# Load environment variables from .env (if present) before reading config.
load_dotenv()

# ---------------------------------------------------------------------------
# Configuration values (driven by environment / .env)
# ---------------------------------------------------------------------------

# Required: full path of the markdown file inside your Obsidian vault.
VAULT_MARKDOWN_PATH = os.environ.get("VAULT_MARKDOWN_PATH", "")

# Gemini configuration: set GEMINI_API_KEY / GEMINI_MODEL in your environment or .env.
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-1.5-flash")


def ensure_file_exists():
  if not VAULT_MARKDOWN_PATH:
    raise RuntimeError("VAULT_MARKDOWN_PATH is not set. Define it in your environment or .env file.")
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


def classify_tags_rule_based(title: str, url: str) -> list[str]:
  """
  Lightweight auto-tagging based on title/URL.
  This is intentionally simple and rules-based but structured so you can
  replace it with a real AI model call later if you want to.
  """
  text = f"{title} {url}".lower()
  tags: list[str] = []

  if any(word in text for word in ("youtube.com", "vimeo.com", "watch?v=", "playlist?")):
    tags.append("video")
  if any(word in text for word in ("paper", "arxiv.org", "researchgate.net", "whitepaper")):
    tags.append("deep_read")
  if any(word in text for word in ("blog", "dev.to", "medium.com", "hashnode.com")):
    tags.append("article")
  if any(word in text for word in ("docs", "documentation", "manual", "reference")):
    tags.append("docs")
  if any(word in text for word in ("course", "tutorial", "learn", "guide")):
    tags.append("learning")
  if any(word in text for word in ("github.com", "gitlab.com", "bitbucket.org")):
    tags.append("code")

  # De-duplicate while preserving order.
  seen = set()
  unique_tags = []
  for t in tags:
    if t not in seen:
      seen.add(t)
      unique_tags.append(t)
  return unique_tags


def classify_tags_ai(title: str, url: str) -> list[str]:
  """
  Classify using Gemini if GEMINI_API_KEY is set; otherwise fall back to rule-based tags.
  The model is expected to return a single line of space-separated tags, no '#'.
  """
  if not GEMINI_API_KEY:
    return classify_tags_rule_based(title, url)

  prompt = (
    "You are a short tag generator for a personal knowledge base.\n"
    "Given a web page title and URL, return 3-6 short, lowercase tags that describe its topic or type.\n"
    "Rules:\n"
    "- Only output the tags, space-separated, on a single line.\n"
    "- Do NOT include '#' characters.\n"
    "- Prefer generic topics like ai, frontend, philosophy, productivity, health, video, deep_read, article, docs, code.\n\n"
    f"Title: {title}\n"
    f"URL: {url}\n\n"
    "Tags:"
  )

  body = {
    "contents": [
      {
        "parts": [
          {
            "text": prompt
          }
        ]
      }
    ]
  }

  url_endpoint = (
    f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
    f"?key={GEMINI_API_KEY}"
  )

  try:
    data = json.dumps(body).encode("utf-8")
    req = urllib_request.Request(
      url_endpoint,
      data=data,
      headers={"Content-Type": "application/json"},
      method="POST"
    )
    with urllib_request.urlopen(req, timeout=10) as resp:
      resp_body = resp.read()
    parsed = json.loads(resp_body.decode("utf-8"))
    candidates = parsed.get("candidates") or []
    if not candidates:
      return classify_tags_rule_based(title, url)
    content = candidates[0].get("content") or {}
    parts = content.get("parts") or []
    if not parts:
      return classify_tags_rule_based(title, url)
    text = parts[0].get("text") or ""
    # Split on whitespace and normalise.
    tags = [t.strip().lower().lstrip("#") for t in text.split() if t.strip()]
    # Deduplicate.
    seen = set()
    result = []
    for t in tags:
      if t and t not in seen:
        seen.add(t)
        result.append(t)
    if not result:
      return classify_tags_rule_based(title, url)
    return result
  except (urllib_error.URLError, urllib_error.HTTPError, TimeoutError, json.JSONDecodeError, KeyError):
    # On any failure, silently fall back to simple rules.
    return classify_tags_rule_based(title, url)


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
      tags = classify_tags_ai(title, url)
      tags_suffix = ""
      if tags:
        tags_suffix = " " + " ".join(f"#{t}" for t in tags)

      new_lines.append(f"- [ ] [{safe_title}]({url}){tags_suffix}  ")
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
  if not VAULT_MARKDOWN_PATH:
    print(
      "VAULT_MARKDOWN_PATH is not set.\n"
      "Create a .env file next to obsidian_writer.py or set the environment variable, for example:\n"
      '  echo \'VAULT_MARKDOWN_PATH="/full/path/to/your/Obsidian/vault/Watch Later.md"\' > .env'
    )
  else:
    run_server()

