from __future__ import annotations

import re

from bs4 import BeautifulSoup, Tag

from archiveinator import console
from archiveinator.pipeline import ArchiveContext

STEP = "js_strip"

# Inline event-handler attributes to strip from all elements.
_EVENT_ATTRS: frozenset[str] = frozenset(
    [
        "onabort",
        "onanimationend",
        "onanimationiteration",
        "onanimationstart",
        "onblur",
        "oncanplay",
        "oncanplaythrough",
        "onchange",
        "onclick",
        "oncontextmenu",
        "ondblclick",
        "ondrag",
        "ondragend",
        "ondragenter",
        "ondragleave",
        "ondragover",
        "ondragstart",
        "ondrop",
        "ondurationchange",
        "onemptied",
        "onended",
        "onerror",
        "onfocus",
        "onformdata",
        "oninput",
        "oninvalid",
        "onkeydown",
        "onkeypress",
        "onkeyup",
        "onload",
        "onloadeddata",
        "onloadedmetadata",
        "onloadstart",
        "onmousedown",
        "onmouseenter",
        "onmouseleave",
        "onmousemove",
        "onmouseout",
        "onmouseover",
        "onmouseup",
        "onpause",
        "onplay",
        "onplaying",
        "onprogress",
        "onratechange",
        "onreset",
        "onresize",
        "onscroll",
        "onseeked",
        "onseeking",
        "onselect",
        "onstalled",
        "onsubmit",
        "onsuspend",
        "ontimeupdate",
        "ontoggle",
        "ontransitionend",
        "onunload",
        "onvolumechange",
        "onwaiting",
        "onwheel",
    ]
)

# Pattern matching javascript: pseudo-protocol in href/src/action attributes.
_JS_PROTOCOL_RE = re.compile(r"^\s*javascript\s*:", re.IGNORECASE)


async def run(ctx: ArchiveContext) -> None:
    """Strip all JavaScript from the archived HTML.

    Removes:
    - <script> tags (inline and external)
    - Inline event-handler attributes (onclick, onload, etc.)
    - href/src/action attributes using the javascript: pseudo-protocol
    - <noscript> tags (their content is only relevant when JS is active)
    """
    if ctx.page_html is None:
        return

    soup = BeautifulSoup(ctx.page_html, "html.parser")

    scripts_removed = 0
    noscripts_removed = 0
    attrs_removed = 0
    js_hrefs_removed = 0

    # Remove <script> tags
    for tag in soup.find_all("script"):
        tag.decompose()
        scripts_removed += 1

    # Remove <noscript> tags (fallback content only relevant when JS is on)
    for tag in soup.find_all("noscript"):
        tag.decompose()
        noscripts_removed += 1

    # Strip inline event handlers and javascript: pseudo-protocol hrefs
    for tag in soup.find_all(True):
        if not isinstance(tag, Tag):
            continue
        attrs_to_delete = []
        for attr, value in list(tag.attrs.items()):
            attr_lower = attr.lower()
            # Inline event handlers
            if attr_lower in _EVENT_ATTRS:
                attrs_to_delete.append(attr)
                attrs_removed += 1
            # javascript: pseudo-protocol in href/src/action
            elif attr_lower in ("href", "src", "action") and isinstance(value, str):
                if _JS_PROTOCOL_RE.match(value):
                    attrs_to_delete.append(attr)
                    js_hrefs_removed += 1
        for attr in attrs_to_delete:
            del tag[attr]

    ctx.page_html = str(soup)

    console.step(
        f"JS strip: removed {scripts_removed} script(s), "
        f"{noscripts_removed} noscript(s), "
        f"{attrs_removed} event handler(s), "
        f"{js_hrefs_removed} javascript: href(s)"
    )
