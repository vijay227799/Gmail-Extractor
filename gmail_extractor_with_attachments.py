#!/usr/bin/env python3
"""
Gmail Email Extractor with Attachments (fixed version)

Saves every email (Inbox, Sent, Spam, Trash, all labels) with its body,
inline images and attachments into a local folder that opens in any browser.

Output:
  extracted_emails/
    index.html                   <- open this: searchable list of all emails
    labels.json
    failed_ids.txt               <- only if something could not be saved
    emails/<message_id>/
        message.html             <- readable email (body, images, attachment links)
        original.eml             <- exact copy of the email
        meta.json                <- headers, labels, list of files
        attachments/             <- every attachment as a real file

Safe to re-run: finished emails are skipped, failed ones are retried.
"""

import os
import re
import json
import html
import time
import base64
import shutil
import mimetypes
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

import email
import email.policy

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If you change these scopes, delete token.json.
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

CREDENTIALS_FILE = "credentials.json"
TOKEN_FILE = "token.json"

PAGE_SIZE = 500              # emails per list request (Gmail maximum is 500)
PAUSE_BETWEEN_EMAILS = 0.1   # seconds, keeps us under Gmail's per-minute quota
MAX_RETRIES = 8

INVALID_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
RESERVED_NAMES = ({"CON", "PRN", "AUX", "NUL"}
                  | {f"COM{i}" for i in range(1, 10)}
                  | {f"LPT{i}" for i in range(1, 10)})

PAGE_CSS = """
body{font-family:Arial,Helvetica,sans-serif;margin:0;background:#f4f5f7;color:#222}
.wrap{max-width:960px;margin:20px auto;background:#fff;border-radius:8px;
      box-shadow:0 1px 4px rgba(0,0,0,.1);overflow:hidden}
.head{background:#f0f4f8;padding:16px 20px;border-bottom:1px solid #ddd}
.head h1{font-size:20px;margin:0 0 8px;word-break:break-word}
.meta{font-size:13px;color:#555;margin:3px 0;word-break:break-word}
.body{padding:20px;line-height:1.5;overflow-wrap:anywhere}
.body img{max-width:100%;height:auto}
pre.plain{white-space:pre-wrap;font-family:inherit}
.atts{padding:14px 20px;background:#fafafa;border-top:1px solid #ddd}
.atts h3{margin:0 0 8px;font-size:15px}
.atts a{display:block;padding:4px 0;color:#1a56db;text-decoration:none}
.atts a:hover{text-decoration:underline}
.atts span{color:#888;font-size:12px}
input{width:100%;box-sizing:border-box;padding:10px;font-size:15px;margin-top:10px;
      border:1px solid #bbb;border-radius:6px}
table{width:100%;border-collapse:collapse;font-size:14px}
th,td{padding:8px 10px;border-bottom:1px solid #eee;text-align:left;vertical-align:top}
th{background:#f0f4f8}
td a{color:#1a56db;text-decoration:none}
"""


def safe_name(text, maxlen=80):
    """Make text safe to use as a file or folder name on Windows, Mac and Linux."""
    text = INVALID_CHARS.sub("_", text or "")
    text = re.sub(r"\s+", " ", text).strip().rstrip(". ")
    return text[:maxlen].rstrip(". ") or "untitled"


def safe_filename(name):
    stem, ext = os.path.splitext(name or "")
    ext = INVALID_CHARS.sub("_", ext)[:12]
    stem = safe_name(stem, 120)
    if stem.upper() in RESERVED_NAMES:
        stem = "_" + stem
    return stem + ext


def unique_path(path):
    """Add (2), (3)... if a file with the same name already exists."""
    if not path.exists():
        return path
    i = 2
    while True:
        candidate = path.with_name(f"{path.stem} ({i}){path.suffix}")
        if not candidate.exists():
            return candidate
        i += 1


class GmailExtractorWithAttachments:
    def __init__(self, credentials_file=CREDENTIALS_FILE):
        self.credentials_file = credentials_file
        self.output_dir = Path("extracted_emails")
        self.emails_dir = self.output_dir / "emails"
        self.labels = {}
        self.saved = 0
        self.skipped = 0
        self.attachment_count = 0
        self.failed = []
        self.service = None
        self.authenticate()

    # ------------------------------------------------------------ setup

    def authenticate(self):
        """Log in to Gmail. The first run opens a browser; later runs reuse token.json."""
        creds = None
        if os.path.exists(TOKEN_FILE):
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(self.credentials_file, SCOPES)
                creds = flow.run_local_server(port=0)
            with open(TOKEN_FILE, "w") as token:
                token.write(creds.to_json())

        self.service = build("gmail", "v1", credentials=creds, cache_discovery=False)
        print("✓ Successfully authenticated with Gmail")

    def create_output_directory(self):
        self.emails_dir.mkdir(parents=True, exist_ok=True)
        print(f"✓ Output folder: {self.output_dir.resolve()}")

    # ------------------------------------------------------------ gmail calls

    def api(self, fn):
        """Run a Gmail API call, retrying when Gmail says 'slow down' or has a temporary error."""
        delay = 2
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                return fn()
            except HttpError as e:
                reason = str(e).lower()
                retryable = e.resp.status in (429, 500, 502, 503, 504) or (
                    e.resp.status == 403 and ("rate" in reason or "quota" in reason))
                if not retryable or attempt == MAX_RETRIES:
                    raise
            except OSError:
                if attempt == MAX_RETRIES:
                    raise
            time.sleep(delay)
            delay = min(delay * 2, 120)

    def save_labels(self):
        resp = self.api(lambda: self.service.users().labels().list(userId="me").execute())
        self.labels = {l["id"]: l["name"] for l in resp.get("labels", [])}
        (self.output_dir / "labels.json").write_text(
            json.dumps(self.labels, indent=2), encoding="utf-8")

    def get_all_messages(self):
        """Return the IDs of every email in the account, including Spam and Trash."""
        ids, page_token = [], None
        while True:
            resp = self.api(lambda: self.service.users().messages().list(
                userId="me", maxResults=PAGE_SIZE, pageToken=page_token,
                includeSpamTrash=True).execute())
            ids += [m["id"] for m in resp.get("messages", [])]
            print(f"  listed {len(ids)} emails...", end="\r")
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
        print()
        print(f"✓ Found {len(ids)} total emails")
        return ids

    # ------------------------------------------------------------ saving one email

    def save_message(self, message_id):
        """Download one email completely and save it. Skips it if already saved."""
        folder = self.emails_dir / message_id
        if (folder / "meta.json").exists():
            self.skipped += 1
            return

        if folder.exists():
            shutil.rmtree(folder)          # leftover from an interrupted run
        folder.mkdir(parents=True)

        api_msg = self.api(lambda: self.service.users().messages().get(
            userId="me", id=message_id, format="raw").execute())
        raw = base64.urlsafe_b64decode(api_msg["raw"])
        (folder / "original.eml").write_bytes(raw)

        msg = email.message_from_bytes(raw, policy=email.policy.default)
        att_dir = folder / "attachments"
        texts, htmls, files, cid_map = [], [], [], {}

        for part in msg.walk():
            if part.is_multipart():
                continue

            ctype = part.get_content_type()
            disposition = part.get_content_disposition()   # "inline", "attachment" or None
            filename = part.get_filename()
            content_id = (part.get("Content-ID") or "").strip().strip("<>")

            # The email body (plain text or HTML)
            if ctype in ("text/plain", "text/html") and not filename and disposition != "attachment":
                try:
                    content = part.get_content()
                except Exception:
                    content = (part.get_payload(decode=True) or b"").decode("utf-8", "replace")
                (htmls if ctype == "text/html" else texts).append(content)
                continue

            # Attachment or inline image
            payload = part.get_payload(decode=True) or b""
            if not filename:
                filename = "attachment" + (mimetypes.guess_extension(ctype) or ".bin")
            att_dir.mkdir(exist_ok=True)
            path = unique_path(att_dir / safe_filename(filename))
            path.write_bytes(payload)
            self.attachment_count += 1

            rel = "attachments/" + urllib.parse.quote(path.name)
            if content_id:
                cid_map[content_id] = rel
            files.append({
                "name": path.name,
                "path": rel,
                "size": len(payload),
                "type": ctype,
                "inline": bool(content_id),
            })

        # Build the body and point inline images (cid:) at the saved files
        if htmls:
            body = "\n<hr>\n".join(htmls)
            for cid, rel in cid_map.items():
                body = body.replace("cid:" + cid, rel)
        else:
            body = '<pre class="plain">' + html.escape("\n".join(texts)) + "</pre>"

        subject = str(msg.get("subject", "") or "(no subject)")
        sender = str(msg.get("from", "") or "")
        to = str(msg.get("to", "") or "")
        cc = str(msg.get("cc", "") or "")
        internal_date = int(api_msg.get("internalDate", 0))
        date_str = datetime.fromtimestamp(internal_date / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        labels = [self.labels.get(l, l) for l in api_msg.get("labelIds", [])]

        cc_html = f'<div class="meta"><b>Cc:</b> {html.escape(cc)}</div>' if cc else ""
        att_html = ""
        if files:
            links = "".join(
                f'<a href="{f["path"]}">&#128206; {html.escape(f["name"])} '
                f'<span>({max(1, f["size"] // 1024)} KB)</span></a>' for f in files)
            att_html = f'<div class="atts"><h3>Attachments ({len(files)})</h3>{links}</div>'

        page = (
            '<!DOCTYPE html><html><head><meta charset="utf-8">'
            f"<title>{html.escape(subject)}</title><style>{PAGE_CSS}</style></head><body>"
            '<div class="wrap">'
            f'<div class="head"><h1>{html.escape(subject)}</h1>'
            f'<div class="meta"><b>From:</b> {html.escape(sender)}</div>'
            f'<div class="meta"><b>To:</b> {html.escape(to)}</div>'
            f"{cc_html}"
            f'<div class="meta"><b>Date:</b> {html.escape(date_str)}</div>'
            f'<div class="meta"><b>Labels:</b> {html.escape(", ".join(labels))}</div></div>'
            f'<div class="body">{body}</div>'
            f"{att_html}"
            "</div></body></html>"
        )
        (folder / "message.html").write_text(page, encoding="utf-8")

        meta = {
            "id": message_id,
            "subject": subject,
            "from": sender,
            "to": to,
            "cc": cc,
            "date": date_str,
            "internal_date": internal_date,
            "labels": labels,
            "snippet": api_msg.get("snippet", ""),
            "files": files,
        }
        # meta.json is written last. Its presence means the email is complete.
        (folder / "meta.json").write_text(
            json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
        self.saved += 1

    # ------------------------------------------------------------ index page

    def build_index(self):
        """Create index.html: a searchable list of every saved email."""
        rows = [json.loads(p.read_text(encoding="utf-8"))
                for p in self.emails_dir.glob("*/meta.json")]
        rows.sort(key=lambda r: r["internal_date"], reverse=True)

        trs = []
        for r in rows:
            search = " ".join([r["subject"], r["from"], r["to"], r["date"],
                               " ".join(r["labels"])]).lower()
            labels_txt = ", ".join(r["labels"])
            trs.append(
                f'<tr data-q="{html.escape(search, quote=True)}">'
                f'<td>{html.escape(r["date"])}</td>'
                f'<td>{html.escape(r["from"])}</td>'
                f'<td><a href="emails/{r["id"]}/message.html">{html.escape(r["subject"])}</a></td>'
                f'<td>{html.escape(labels_txt)}</td>'
                f'<td>{len(r["files"])}</td></tr>'
            )

        total_att = sum(len(r["files"]) for r in rows)
        page = (
            '<!DOCTYPE html><html><head><meta charset="utf-8"><title>Gmail Backup</title>'
            f"<style>{PAGE_CSS}</style></head><body><div class=\"wrap\">"
            '<div class="head"><h1>Gmail Backup</h1>'
            f'<div class="meta">{len(rows)} emails &middot; {total_att} attachments</div>'
            '<input id="q" placeholder="Search subject, sender, label, date..." oninput="filt()"></div>'
            "<table><thead><tr><th>Date</th><th>From</th><th>Subject</th>"
            "<th>Labels</th><th>Files</th></tr></thead><tbody>"
            + "\n".join(trs) +
            "</tbody></table></div>"
            '<script>function filt(){var q=document.getElementById("q").value.toLowerCase();'
            'document.querySelectorAll("tbody tr").forEach(function(r){'
            'r.style.display=r.dataset.q.indexOf(q)>=0?"":"none";});}</script>'
            "</body></html>"
        )
        (self.output_dir / "index.html").write_text(page, encoding="utf-8")
        print(f"✓ Index created: {(self.output_dir / 'index.html').resolve()}")

    # ------------------------------------------------------------ main loop

    def extract_all_emails(self):
        self.create_output_directory()
        self.save_labels()

        ids = self.get_all_messages()
        if not ids:
            print("No emails found.")
            return

        total = len(ids)
        print("\nSaving emails (this can take a while for large accounts)...\n")
        for i, message_id in enumerate(ids, 1):
            try:
                self.save_message(message_id)
            except Exception as e:
                self.failed.append(message_id)
                print(f"  ! could not save {message_id}: {e}")

            if i % 25 == 0 or i == total:
                print(f"[{i}/{total}] saved={self.saved} already_had={self.skipped} "
                      f"failed={len(self.failed)} attachments={self.attachment_count}")
            time.sleep(PAUSE_BETWEEN_EMAILS)

        if self.failed:
            (self.output_dir / "failed_ids.txt").write_text(
                "\n".join(self.failed), encoding="utf-8")
            print(f"\n{len(self.failed)} emails failed. Run the script again to retry them.")

        self.build_index()

        print("\n" + "=" * 60)
        print("✓ EXTRACTION COMPLETE")
        print("=" * 60)
        print(f"Emails saved now:      {self.saved}")
        print(f"Emails already saved:  {self.skipped}")
        print(f"Attachments saved:     {self.attachment_count}")
        print(f"Open this file:        {(self.output_dir / 'index.html').resolve()}")
        print("=" * 60)


def main():
    print("=" * 60)
    print("Gmail Email Extractor with Attachments")
    print("=" * 60)

    if not os.path.exists(CREDENTIALS_FILE):
        print(f"\n✗ {CREDENTIALS_FILE} not found in this folder.")
        print("Download the OAuth Desktop credentials from Google Cloud Console")
        print("and save the file as credentials.json next to this script.")
        return

    try:
        extractor = GmailExtractorWithAttachments()
        extractor.extract_all_emails()
    except KeyboardInterrupt:
        print("\n\nStopped. Run the script again to continue where it stopped.")
    except Exception as e:
        print(f"\n✗ Error: {e}")


if __name__ == "__main__":
    main()


#In Coming Days you may find this useful but make sure you test this the below change before blindly using.
#Replace this : 

    # if self.failed:
    # (self.output_dir / "failed_ids.txt").write_text(
    #     "\n".join(self.failed), encoding="utf-8"
    # )
    # print(f"\n{len(self.failed)} emails failed. Run the script again to retry them.")

# with : 

    # failed_file = self.output_dir / "failed_ids.txt"

    # if self.failed:
    #     failed_file.write_text(
    #         "\n".join(self.failed), encoding="utf-8"
    #     )
    #     print(f"\n{len(self.failed)} emails failed. Run the script again to retry them.")

    # elif failed_file.exists():
    #     failed_file.unlink()
    #     print("\n✓ All previously failed emails have been recovered.")