#!/usr/bin/env python3
"""
Convert browser cookie exports to Playwright format for archiveinator.

Common export formats:
1. Cookie-Editor extension: { "cookies": [...], "origins": [...] }
2. EditThisCookie extension: [{ ... }, { ... }] (array of cookies)
3. Playwright's browser_context.cookies(): [{ ... }]

Usage:
    python3 convert_cookies.py input.json output.json
"""

import json
import sys
from pathlib import Path


# Fields that Playwright's SetCookieParam accepts
# https://playwright.dev/python/docs/api/class-browsercontext#browser-context-add-cookies
ALLOWED_FIELDS = {
    "name",
    "value",
    "url",
    "domain",
    "path",
    "expires",
    "httpOnly",
    "secure",
    "sameSite",
}


def _clean_cookie(cookie: dict) -> dict:
    """Keep only fields Playwright understands."""
    return {k: v for k, v in cookie.items() if k in ALLOWED_FIELDS}


def convert_cookie_editor(data: dict) -> list[dict]:
    """Convert Cookie-Editor format to Playwright format."""
    cookies = data.get("cookies", [])
    result = []
    for cookie in cookies:
        # Required fields
        if "name" not in cookie or "value" not in cookie:
            continue

        pc = {
            "name": cookie["name"],
            "value": cookie["value"],
        }

        # Domain/path (required for Playwright if not using 'url')
        if "domain" in cookie:
            pc["domain"] = cookie["domain"]
        if "path" in cookie:
            pc["path"] = cookie.get("path", "/")

        # Optional fields Playwright accepts
        for field in ["expires", "httpOnly", "secure", "sameSite"]:
            if field in cookie:
                pc[field] = cookie[field]

        pc = _clean_cookie(pc)
        result.append(pc)
    return result


def convert_edit_this_cookie(data: list) -> list[dict]:
    """Convert EditThisCookie format to Playwright format."""
    result = []
    for cookie in data:
        if not isinstance(cookie, dict):
            continue

        pc = {
            "name": cookie.get("name", ""),
            "value": cookie.get("value", ""),
        }

        if "domain" in cookie:
            pc["domain"] = cookie["domain"]
        if "path" in cookie:
            pc["path"] = cookie.get("path", "/")

        for field in ["expires", "httpOnly", "secure", "sameSite"]:
            if field in cookie:
                pc[field] = cookie[field]

        pc = _clean_cookie(pc)
        result.append(pc)
    return result


def main() -> None:
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <input.json> <output.json>")
        print("\nExamples:")
        print("  # Convert Cookie-Editor export")
        print("  python3 convert_cookies.py auth.json cookies_playwright.json")
        print("\n  # Use with archiveinator")
        print("  archiveinator archive https://example.com --cookies-file cookies_playwright.json")
        sys.exit(1)

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])

    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}")
        sys.exit(1)

    try:
        with open(input_path) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in {input_path}: {e}")
        sys.exit(1)

    # Detect format and convert
    if isinstance(data, dict) and "cookies" in data:
        print("Detected Cookie-Editor format")
        converted = convert_cookie_editor(data)
    elif isinstance(data, list):
        print("Detected array format (EditThisCookie or Playwright)")
        # Check if first element looks like a cookie
        if data and isinstance(data[0], dict) and "name" in data[0] and "value" in data[0]:
            converted = convert_edit_this_cookie(data)
        else:
            print("Warning: Array doesn't look like cookies. Attempting conversion anyway.")
            converted = convert_edit_this_cookie(data)
    else:
        print("Error: Unknown format. Expected object with 'cookies' key or array of cookies.")
        sys.exit(1)

    print(f"Converted {len(converted)} cookies")

    # Write output
    with open(output_path, "w") as f:
        json.dump(converted, f, indent=2)

    print(f"Saved to {output_path}")
    print("\nUse with archiveinator:")
    print(f"  archiveinator archive <URL> --cookies-file {output_path}")


if __name__ == "__main__":
    main()