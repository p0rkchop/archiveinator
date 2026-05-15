---
layout: default
title: Site Profiles
parent: Web UI
nav_order: 2
---

# Site Profiles

Site profiles define per-domain settings for archiving — cookies for authenticated access, custom user agents, timeout overrides, and pipeline step overrides.

When you archive a URL, archiveinator automatically matches the domain against your profiles and applies the matching profile's settings.

---

## Creating a Profile

1. Go to **Profiles** in the navigation bar
2. Click **New Profile**
3. Fill in the details:

### Fields

| Field | Required | Description |
|:------|:---------|:------------|
| **Domain** | Yes | The domain this profile applies to (e.g. `example.com`) |
| **Label** | No | Human-readable name for the profile |
| **Cookies** | No | Authentication cookies (see formats below) |
| **User Agent** | No | Custom UA override for this domain |
| **Timeout** | No | Per-domain page load timeout in seconds |
| **Stealth Mode** | No | Force anti-fingerprinting stealth browser |
| **Pipeline Overrides** | No | Enable/disable specific pipeline steps for this domain |

---

## Cookie File Formats

Upload a cookie export file — the format is auto-detected:

### Cookie-Editor

```json
{
  "cookies": [
    {
      "name": "session",
      "value": "abc123",
      "domain": ".example.com",
      "path": "/",
      "secure": true,
      "httpOnly": true
    }
  ]
}
```

### EditThisCookie

```json
[
  {
    "name": "session",
    "value": "abc123",
    "domain": ".example.com",
    "path": "/",
    "secure": true,
    "httpOnly": true
  }
]
```

### Playwright Storage State

Full Playwright storage state JSON — includes cookies and localStorage. Exportable from Playwright scripts or the `archiveinator login --full-storage` command.

---

## Profile Matching

When you submit a URL to archive:

1. The domain is extracted from the URL
2. A database query looks for a profile with that exact domain for your user
3. If found, the profile's cookies, UA, timeout, stealth, and pipeline overrides are applied
4. If not found, global config defaults are used

{: .note }
One profile per user per domain. Creating a new profile for a domain that already has one will be rejected.

---

## Testing Cookies

From the profile edit page, click **Test Cookies** to do a quick headless page load against the domain. This reports the HTTP response status so you can verify the cookies are valid without running a full archive.

---

## Headless Login

For capturing cookies without a browser extension, use the CLI's `login` command:

```bash
archiveinator login https://example.com
```

This launches an interactive browser where you log in manually. When you close the browser, cookies are saved to `cookies.json`, which you can upload to a site profile.

See the [CLI Reference](../cli-reference#archiveinator-login) for login command options.
