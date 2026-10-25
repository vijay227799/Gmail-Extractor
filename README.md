# Gmail Email Extractor & Local Backup

A Python-based Gmail backup utility that extracts emails from a Gmail account, including Inbox, Sent, Spam, Trash and other labels, and stores them locally along with their original email files, inline images and attachments.

The application uses the **Gmail API and OAuth 2.0 authentication** to securely access Gmail data.

It does not require hosting, a backend server or cloud storage. All extracted data is stored locally on your computer.

## Features

- **OAuth 2.0 Authentication:** Securely authenticate using your own Google account.
- **Complete Email Retrieval:** Retrieve messages across Gmail labels, including Inbox, Sent, Spam and Trash.
- **Email Metadata Extraction:** Extract sender, recipient, CC, subject, date, labels and snippets.
- **Original Email Preservation:** Save the original email in `.eml` format.
- **Email Body Extraction:** Extract plain-text and HTML email content.
- **Attachment Download:** Download attachments and embedded images as actual files.
- **Inline Image Support:** Save inline images and update their Content-ID (`cid:`) references in the generated HTML.
- **Individual Email Storage:** Organize every email in its own directory using its Gmail message ID.
- **Searchable Dashboard:** Generate an HTML index containing all saved emails, with client-side search functionality.
- **Duplicate Prevention:** Skip emails that have already been completely saved.
- **Resumable Extraction:** Run the script again to continue an interrupted extraction.
- **Automatic Retries:** Retry temporary API and network failures using exponential backoff.

---

# 1. Prerequisites

Before getting started, ensure you have:

- Python 3.10 or later installed.
- A Google account with Gmail enabled.
- An internet connection.
- Access to Google Cloud Console.

Check your Python installation:

```bash
python --version
```

---

# 2. Google Cloud Configuration

The Gmail API requires OAuth 2.0 credentials to access your Gmail account.

Each user must create their own Google Cloud project and OAuth credentials.

Follow the steps below to configure your Google Cloud project.

## Step 2.1: Create a Google Cloud Project

1. Open [Google Cloud Console](https://console.cloud.google.com/).
2. Sign in using your Google account.
3. Click the project selector at the top of the page.
4. Click **New Project**.
5. Enter a project name, for example:

   `Gmail-Local-Backup`

6. Click **Create**.
7. Ensure the newly created project is selected.

## Step 2.2: Enable Gmail API

1. Open the [Gmail API Library](https://console.cloud.google.com/apis/library/gmail.googleapis.com).
2. Ensure your newly created project is selected.
3. Click **Enable**.
4. Wait until the API is enabled.

This allows your Google Cloud project to make requests to the Gmail API.

## Step 2.3: Configure OAuth Consent Screen (Google Auth Platform)

Open [Google Auth Platform](https://console.cloud.google.com/auth/overview).

If the Google Auth Platform has not been configured previously, click **Get Started**.

### A. Branding Configuration

Navigate to:

**Google Auth Platform → Branding**

Configure the following fields:

**App Information**

| Field | Value |
|---|---|
| App name | Gmail Local Backup |
| User support email | Your Gmail address |
| App logo | Leave empty (optional) |

**App Domain**

For this personal desktop application, the following fields can remain empty:

- Application home page
- Application privacy policy link
- Application terms of service link

**Authorized Domains**

Leave this section empty.

You do not need to register `localhost`, `gmail.com` or any other domain for this Desktop OAuth application.

**Developer Contact Information**

Enter your Gmail address.

Save the configuration.

### B. Audience Configuration

Navigate to:

**Google Auth Platform → Audience**

Configure:

1. Select **External** as the user type if you are using a personal Gmail account.
2. Keep the application publishing status as **Testing**.
3. Under **Test users**, click **Add Users**.
4. Enter the Gmail address you intend to back up.
5. Click **Save**.

Important:

- Only users added as test users can authorize the application while it is in Testing mode.
- You do not need to publish the application or undergo verification for this personal-use testing setup.
- Testing mode has a maximum of 100 test users.

### C. Data Access Configuration

Navigate to:

**Google Auth Platform → Data Access**

Add the following OAuth scope:

```text
https://www.googleapis.com/auth/gmail.readonly
```

This scope allows your application to:

- Read Gmail messages.
- Access email contents.
- Access message metadata.
- Retrieve attachments and inline images.

It does not grant permission to send, modify or delete emails.

Save your configuration.

## Step 2.4: Create OAuth 2.0 Client Credentials

This is an important step because the Python application requires the downloaded credentials file.

Navigate to:

[Google Auth Platform – Clients](https://console.cloud.google.com/auth/clients)

Follow these steps:

1. Click **Create Client**.
2. Under **Application Type**, select **Desktop app**.
3. Enter a client name, for example:

   `Gmail Local Backup Desktop Client`

4. Click **Create**.
5. Download the generated OAuth credentials JSON file.

Rename the downloaded file to:

```text
credentials.json
```

Place this file in the root directory of the cloned project, alongside the Python script.

**Important:** Never upload `credentials.json` to GitHub or share it publicly.

---

# 3. Clone the Repository

Clone the repository:

```bash
git clone <YOUR_REPOSITORY_URL>
```

Navigate into the project directory:

```bash
cd <PROJECT_DIRECTORY>
```

Ensure the directory contains:

```text
GmailBackup/
│
├── credentials.json
├── gmail_extractor.py
├── README.md
└── requirements.txt
```

Replace `gmail_extractor.py` with the actual name of your Python script if it differs.

---

# 4. Python Environment Setup

It is recommended to use a virtual environment to isolate project dependencies.

### Step 4.1: Create a Virtual Environment

```bash
python -m venv venv
```

### Step 4.2: Activate the Virtual Environment

**Windows:**

```bash
venv\Scripts\activate
```

**Linux / macOS:**

```bash
source venv/bin/activate
```

### Step 4.3: Install Dependencies

Create a `requirements.txt` file containing:

```text
google-api-python-client
google-auth-httplib2
google-auth-oauthlib
```

Install the dependencies:

```bash
pip install -r requirements.txt
```

---

# 5. Run the Application

Once Google Cloud configuration and Python environment setup are complete, execute:

```bash
python gmail_extractor.py
```

### First Execution – Google Authorization

During the first execution:

1. A Google login/authorization page will open in your browser.
2. Select the Gmail account you want to back up.
3. Review the requested permissions.
4. Grant read-only access to your Gmail account.
5. Google redirects the authorization response to your local application.
6. Authentication credentials are saved locally in `token.json`.

You may encounter an unverified-app warning because the application is in Testing mode. Proceed only if you recognize the application and have configured it yourself.

### Subsequent Executions

The application reuses the saved authentication token.

You generally do not need to authorize again unless the token expires, is revoked or otherwise becomes invalid.

---

# 6. Generated Output

After successful execution, the application creates an `extracted_emails` directory.

The expected directory structure is:

```text
extracted_emails/
│
├── index.html
│
├── labels.json
│
├── failed_ids.txt
│   (Created only if some emails fail to save)
│
└── emails/
    │
    ├── MESSAGE_ID_1/
    │   │
    │   ├── original.eml
    │   ├── message.html
    │   ├── meta.json
    │   │
    │   └── attachments/
    │       ├── document.pdf
    │       ├── image.jpg
    │       └── spreadsheet.xlsx
    │
    ├── MESSAGE_ID_2/
    │   │
    │   ├── original.eml
    │   ├── message.html
    │   ├── meta.json
    │   │
    │   └── attachments/
    │       └── attachment.png
    │
    └── ...
```

### Understanding the Output

| File / Directory | Purpose |
|---|---|
| `index.html` | Searchable dashboard containing all successfully saved emails |
| `labels.json` | Mapping of Gmail label IDs to their corresponding names |
| `failed_ids.txt` | Message IDs that could not be saved during the latest run |
| `original.eml` | Original email downloaded from Gmail in RFC 2822 format |
| `message.html` | Readable HTML representation of the email |
| `meta.json` | Structured email metadata and information about downloaded files |
| `attachments/` | Actual attachment and inline image files belonging to that email |

### Viewing Your Backup

After extraction completes, open:

```text
extracted_emails/index.html
```

in your browser.

The index page provides:

- Total number of saved emails.
- Total number of downloaded files.
- Email date.
- Sender.
- Subject.
- Gmail labels.
- Number of associated files.
- Search functionality.

Click an email subject to open its individual HTML representation.

### Accessing Original Emails

If you want the original email rather than the generated HTML representation, open:

```text
emails/<MESSAGE_ID>/original.eml
```

Compatible email clients can open `.eml` files.

---

# 7. Resuming an Interrupted Extraction

The application includes basic resume functionality.

It uses the presence of `meta.json` to determine whether an email has been completely saved.

### How It Works

**Scenario 1: Email already saved**

If the following file exists:

```text
emails/<MESSAGE_ID>/meta.json
```

The application skips that email.

**Scenario 2: Extraction interrupted**

If an email was only partially downloaded and `meta.json` was not created, its incomplete directory is removed when the application attempts that email again.

The email is then downloaded again.

**Scenario 3: Some emails failed**

If an email cannot be downloaded after the available retries, its message ID is recorded in:

```text
extracted_emails/failed_ids.txt
```

Run the script again to retry failed or incomplete emails.

Previously completed emails are skipped.

This prevents the entire extraction from having to start over after an interruption.

---

# 8. Important Implementation Details

### Email Retrieval

The application uses:

```python
PAGE_SIZE = 500
```

Gmail API supports retrieving up to 500 messages per listing request.

Pagination is used to retrieve the remaining messages.

The application also uses:

```python
includeSpamTrash=True
```

This ensures that Spam and Trash messages are included in the listing.

### Original Email Preservation

Each email is retrieved using:

```python
format="raw"
```

The returned raw email data is decoded and saved as:

```text
original.eml
```

This preserves the original email representation instead of storing only extracted body text.

### Attachment and Inline Image Handling

The application traverses the email's MIME parts.

It extracts:

- Plain-text content.
- HTML content.
- Regular attachments.
- Inline images and other MIME resources.

Inline images containing Content-ID references are downloaded, and their `cid:` references are replaced with local relative file paths in the generated HTML.

### Retry Mechanism

Temporary Gmail API errors and network-related `OSError` exceptions are retried.

The application uses exponential backoff, with a maximum of eight attempts.

### Duplicate Prevention

Each Gmail message is stored in a directory identified by its unique message ID.

A successfully saved email is identified by the presence of `meta.json`.

This prevents completed emails from being downloaded again when the script is rerun.

---

# 9. OAuth Testing Mode Expiration

Google OAuth applications configured as External and kept in Testing mode generally receive refresh tokens that expire after seven days when Gmail scopes are requested.

If authorization stops working after this period, you may need to authorize the application again.

Refer to [Google OAuth 2.0 Documentation](https://developers.google.com/identity/protocols/oauth2) for details.

---

# 10. Security Best Practices

Never commit authentication credentials or extracted personal data to GitHub.

Add the following entries to your `.gitignore`:

```gitignore
# Google OAuth credentials
credentials.json
token.json
token.pickle

# Extracted Gmail data
extracted_emails/

# Python virtual environment
venv/

# Python cache
__pycache__/
*.pyc
```

Keep your credentials and extracted emails on secure local storage.

The application uses Gmail read-only authorization. It cannot delete or modify Gmail messages.

**Important:** Downloading a backup does not automatically free up Gmail storage. Emails and attachments remain in Gmail until you separately decide to delete them.

Always verify your local backup before deleting anything from Gmail.

Also remember that `.eml` files and extracted attachments can contain sensitive personal information. Protect your backup accordingly.

---

# 11. Troubleshooting

| Problem | Possible Solution |
|---|---|
| `credentials.json not found` | Ensure the downloaded credentials file is in the project root directory. |
| `Access blocked` | Check that your Gmail address is added under Audience → Test users. |
| `invalid_scope` | Verify that the Gmail read-only OAuth scope is correct. |
| `API has not been used or is disabled` | Ensure Gmail API is enabled in the selected Google Cloud project. |
| `invalid_grant` | Your refresh token may have expired or been revoked. Reauthorize the application. |
| `ModuleNotFoundError` | Activate your virtual environment and install the required dependencies. |
| Attachment download failures | Check your internet connection and review the error associated with the affected message. |
| Extraction interrupted | Execute the script again. Previously completed emails will be skipped. |

---

# 12. Official Documentation

For additional information, refer to:

- [Google Cloud Console](https://console.cloud.google.com/)
- [Gmail API Documentation](https://developers.google.com/workspace/gmail/api)
- [Gmail API Python Quickstart](https://developers.google.com/workspace/gmail/api/quickstart/python)
- [Gmail API Authorization Scopes](https://developers.google.com/workspace/gmail/api/auth/scopes)
- [Google OAuth 2.0 Documentation](https://developers.google.com/identity/protocols/oauth2)

---

# 13. Execution Summary

Once the Google Cloud configuration is complete, dependencies are installed and `credentials.json` is placed in the project directory, simply execute:

```bash
python gmail_extractor.py
```

Authorize your Gmail account when prompted.

After extraction, open:

```text
extracted_emails/index.html
```

Your Gmail messages, original email files, metadata, inline images and attachments will be available locally.

**That's it! Your Gmail backup is ready.**
