/* archiveinator — profile form: cookie file drag-and-drop, JSON parse, preview */

(function () {
  const dropZone = document.getElementById("file-drop-zone");
  const fileInput = document.getElementById("cookies_file");
  const hiddenInput = document.getElementById("cookies_json");
  const preview = document.getElementById("cookie-preview");
  const cookieCount = document.getElementById("cookie-count");
  const cookieSource = document.getElementById("cookie-source");

  if (!dropZone || !fileInput || !hiddenInput) return;

  /* ---- Drag-and-drop visual feedback ---- */
  dropZone.addEventListener("dragover", function (e) {
    e.preventDefault();
    dropZone.classList.add("drag-over");
  });

  dropZone.addEventListener("dragleave", function () {
    dropZone.classList.remove("drag-over");
  });

  dropZone.addEventListener("drop", function (e) {
    e.preventDefault();
    dropZone.classList.remove("drag-over");
    if (e.dataTransfer.files.length > 0) {
      fileInput.files = e.dataTransfer.files;
      handleFile(e.dataTransfer.files[0]);
    }
  });

  /* ---- Click-to-browse ---- */
  dropZone.addEventListener("click", function () {
    fileInput.click();
  });

  fileInput.addEventListener("change", function () {
    if (fileInput.files.length > 0) {
      handleFile(fileInput.files[0]);
    }
  });

  /* ---- File handler: read, parse, preview ---- */
  function handleFile(file) {
    if (!file.name.endsWith(".json")) {
      showError("Please select a .json file.");
      return;
    }

    const reader = new FileReader();
    reader.onload = function (e) {
      try {
        const data = parseCookiesJson(e.target.result);
        if (data.cookies.length === 0) {
          showError("No cookies found in the file.");
          return;
        }
        hiddenInput.value = JSON.stringify(data.cookies);
        showPreview(data.cookies.length, data.source, data.domain);
      } catch (err) {
        showError("Invalid JSON: " + err.message);
      }
    };
    reader.readAsText(file);
  }

  /* ---- Parse supported cookie formats ---- */
  function parseCookiesJson(raw) {
    var parsed = JSON.parse(raw);

    // Playwright storage state: {"cookies": [...]}
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      if (Array.isArray(parsed.cookies) && parsed.cookies.length > 0) {
        return {
          cookies: parsed.cookies,
          source: "Playwright storage state",
          domain: extractDomain(parsed.cookies),
        };
      }
      // Cookie-Editor object format: {"cookies": [...], "domain": "..."}
      if (parsed.cookies && Array.isArray(parsed.cookies)) {
        return {
          cookies: parsed.cookies,
          source: "Cookie-Editor",
          domain: parsed.domain || extractDomain(parsed.cookies),
        };
      }
      throw new Error(
        "Unrecognised format: expected an array of cookies or {cookies: [...]}"
      );
    }

    // Array format — could be EditThisCookie or Cookie-Editor export
    if (Array.isArray(parsed)) {
      // Cookie-Editor exports array of {domain, name, value, ...}
      // EditThisCookie exports array of {domain, name, value, ...}
      var cookies = parsed.filter(function (c) {
        return c.name && c.value && c.domain;
      });
      if (cookies.length > 0) {
        return {
          cookies: cookies,
          source: "Cookie export",
          domain: extractDomain(cookies),
        };
      }
      throw new Error("No valid cookie entries found in the array.");
    }

    throw new Error("Unrecognised cookie file format.");
  }

  function extractDomain(cookies) {
    // Find the most common domain among cookies
    var counts = {};
    cookies.forEach(function (c) {
      var d = c.domain || "";
      // Strip leading dot
      if (d.charAt(0) === ".") d = d.slice(1);
      if (d) counts[d] = (counts[d] || 0) + 1;
    });
    var best = "";
    var bestCount = 0;
    for (var d in counts) {
      if (counts[d] > bestCount) {
        bestCount = counts[d];
        best = d;
      }
    }
    return best;
  }

  /* ---- Preview & error display ---- */
  function showPreview(count, source, domain) {
    if (!preview) return;
    cookieCount.textContent = count;
    cookieSource.textContent = source + (domain ? " (" + domain + ")" : "");
    preview.style.display = "block";
    preview.className = "cookie-preview cookie-preview-ok";
  }

  function showError(msg) {
    hiddenInput.value = "";
    if (!preview) return;
    cookieCount.textContent = "Error";
    cookieSource.textContent = msg;
    preview.style.display = "block";
    preview.className = "cookie-preview cookie-preview-error";
  }

  /* ---- Clear cookies checkbox ---- */
  var clearCheckbox = document.querySelector(
    'input[name="clear_cookies"][type="checkbox"]'
  );
  if (clearCheckbox) {
    clearCheckbox.addEventListener("change", function () {
      if (this.checked) {
        hiddenInput.value = "";
        if (preview) preview.style.display = "none";
        fileInput.value = "";
      }
    });
  }
})();
