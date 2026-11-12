/* SPDX-FileCopyrightText: 2024-2026 Knut Zoch
 * SPDX-License-Identifier: GPL-3.0-only */
(() => {
  "use strict";
  if (window.GALCommon) return;
  function observeCollections(selector, initialize) {
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", initialize, {once: true});
    else initialize();
    if (typeof document$ !== "undefined" && document$.subscribe) document$.subscribe(initialize);
    new MutationObserver(changes => {
      if (changes.some(change => Array.from(change.addedNodes).some(node => node.nodeType === 1 && (node.matches(selector) || node.querySelector(selector))))) initialize();
    }).observe(document.documentElement, {childList: true, subtree: true});
  }
  function replaceURL(url) {
    if (url.href === location.href) return;
    try { history.replaceState(history.state, "", url); }
    catch (_) { /* Filtering remains usable without history access. */ }
  }
  function readURLFields(fields) {
    const params = new URLSearchParams(location.search);
    for (const [key, input] of Object.entries(fields)) {
      if (input) input.value = params.get(key) || "";
    }
    return params;
  }
  function writeURLParams(values) {
    const url = new URL(location.href);
    for (const [key, value] of Object.entries(values)) {
      url.searchParams.delete(key);
      for (const item of Array.isArray(value) ? value : [value]) {
        if (item) url.searchParams.append(key, item);
      }
    }
    replaceURL(url);
  }
  function monthMatches(date, after, before) {
    const month = (date || "").slice(0, 7);
    return (!after || !month || month >= after) && (!before || (month && month <= before));
  }
  function updateExpandButton(button, total, expanded) {
    if (!button) return;
    button.disabled = total === 0;
    button.textContent = expanded ? "Collapse all" : "Expand all";
    button.setAttribute("aria-pressed", String(expanded));
  }
  window.GALCommon = {observeCollections, readURLFields, writeURLParams, monthMatches, updateExpandButton};
})();
