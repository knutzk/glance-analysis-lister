/* SPDX-FileCopyrightText: 2024-2026 Knut Zoch
 * SPDX-License-Identifier: GPL-3.0-only */
(() => {
  "use strict";
  if (window.GALConfNotes) { window.GALConfNotes.initialize(); return; }
  const initialized = new WeakSet();
  function initialize() {
    document.querySelectorAll("[data-gal-confnotes]").forEach(root => {
      if (initialized.has(root)) return;
      const controls = root.querySelector("[data-gal-confnote-controls]");
      const search = controls?.querySelector("[data-gal-search]");
      const statusButtons = Array.from(controls?.querySelectorAll("[data-gal-confnote-supersession]") || []);
      const counter = root.querySelector("[data-gal-confnote-count]");
      const empty = root.querySelector("[data-gal-confnotes-empty]");
      let rows;
      try {
        rows = Array.from(root.querySelectorAll("[data-gal-confnote]"), element => {
          const toggle = element.querySelector("[data-gal-confnote-toggle]");
          const panel = document.getElementById(toggle.getAttribute("aria-controls"));
          if (!panel || !root.contains(panel)) throw new Error("Missing note details");
          return {element, toggle, panel, expanded: false, superseded: element.dataset.galSuperseded === "true", text: (element.dataset.galSearchText || "").toLowerCase()};
        });
      } catch (_) { return; }
      const after = controls?.querySelector("[data-gal-date-after]");
      const before = controls?.querySelector("[data-gal-date-before]");
      const expandAll = controls?.querySelector("[data-gal-archive-expand-all]");
      function syncExpandAll() {
        if (!expandAll) return;
        const visible = rows.filter(row => !row.element.hidden);
        const expanded = visible.length > 0 && visible.every(row => row.expanded);
        expandAll.disabled = visible.length === 0;
        expandAll.textContent = expanded ? "Collapse all" : "Expand all";
        expandAll.setAttribute("aria-pressed", String(expanded));
      }
      function setExpanded(row, expanded) {
        row.expanded = expanded;
        row.panel.hidden = row.element.hidden || !expanded;
        row.toggle.setAttribute("aria-expanded", String(expanded));
        row.element.classList.toggle("gal-confnote--expanded", expanded);
        syncExpandAll();
      }
      rows.forEach(row => {
        row.toggle.setAttribute("role", "button");
        row.toggle.tabIndex = 0;
        setExpanded(row, false);
        row.element.addEventListener("click", event => {
          if (event.target.closest("a, button, input, select, textarea") || window.getSelection()?.toString()) return;
          setExpanded(row, !row.expanded);
        });
        row.toggle.addEventListener("keydown", event => {
          if (!["Enter", " "].includes(event.key)) return;
          event.preventDefault();
          setExpanded(row, !row.expanded);
        });
        const collapse = row.panel.querySelector("[data-gal-confnote-collapse]");
        collapse.hidden = false;
        collapse.addEventListener("click", () => {
          setExpanded(row, false);
          row.toggle.focus({preventScroll: true});
          row.element.scrollIntoView({block: "nearest"});
        });
      });
      function readURL() {
        const params = new URLSearchParams(location.search);
        if (after) after.value = params.get("after") || "";
        if (before) before.value = params.get("before") || "";
        if (search) search.value = params.get("q") || "";
        const status = new URLSearchParams(location.search).get("supersession");
        statusButtons.forEach(button => button.setAttribute("aria-pressed", String(status === "all" || button.dataset.galConfnoteSupersession === (status === "superseded" ? "superseded" : "non-superseded"))));
      }
      function update() {
        const query = (search?.value || "").trim().toLowerCase();
        const statuses = statusButtons.filter(button => button.getAttribute("aria-pressed") === "true").map(button => button.dataset.galConfnoteSupersession);
        const visible = rows.filter(row => {
          const month = (row.element.dataset.galDate || "").slice(0, 7);
          return (!after?.value || !month || month >= after.value) && (!before?.value || (month && month <= before.value)) && (!query || row.text.includes(query)) && (!statuses.length || statuses.includes(row.superseded ? "superseded" : "non-superseded"));
        });
        rows.forEach(row => {
          row.element.hidden = !visible.includes(row);
          row.panel.hidden = row.element.hidden || !row.expanded;
        });
        visible.forEach((row, i) => {
          row.element.classList.toggle("gal-confnote--stripe", i % 2 === 1);
        });
        syncExpandAll();
        empty.hidden = visible.length > 0;
        if (counter) counter.textContent = `${visible.length} of ${rows.length} notes`;
        const url = new URL(location.href);
        for (const [key, value] of [["after", after?.value], ["before", before?.value], ["q", search?.value.trim()]]) {
          url.searchParams.delete(key);
          if (value) url.searchParams.set(key, value);
        }
        url.searchParams.delete("subgroup");
        url.searchParams.delete("supersession");
        if (statuses.length === 1 && statuses[0] === "superseded") url.searchParams.set("supersession", "superseded");
        else if (statusButtons.length && statuses.length !== 1) url.searchParams.set("supersession", "all");
        if (url.href !== location.href) {
          try { history.replaceState(history.state, "", url); } catch (_) { /* Keep local filtering usable. */ }
        }
      }
      controls?.addEventListener("click", event => {
        const button = event.target.closest("button");
        if (!button || !controls.contains(button)) return;
        if (button.hasAttribute("data-gal-archive-expand-all")) {
          const expanded = button.getAttribute("aria-pressed") !== "true";
          rows.filter(row => !row.element.hidden).forEach(row => setExpanded(row, expanded));
          return;
        }
        if (button.hasAttribute("data-gal-confnote-reset")) {
          if (after) after.value = "";
          if (before) before.value = "";
          if (search) search.value = "";
          statusButtons.forEach(option => option.setAttribute("aria-pressed", String(option.dataset.galConfnoteSupersession === "non-superseded")));
        }
        else if (button.hasAttribute("data-gal-confnote-supersession")) button.setAttribute("aria-pressed", String(button.getAttribute("aria-pressed") !== "true"));
        else return;
        update();
      });
      controls?.addEventListener("change", update);
      search?.addEventListener("input", update);
      window.addEventListener("popstate", () => { if (root.isConnected) { readURL(); update(); } });
      readURL();
      update();
      initialized.add(root);
      root.classList.add("gal-confnotes--filtered");
      if (controls) controls.hidden = false;
    });
  }
  window.GALConfNotes = {initialize};
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", initialize, {once: true});
  else initialize();
  if (typeof document$ !== "undefined" && document$.subscribe) document$.subscribe(initialize);
  new MutationObserver(changes => {
    if (changes.some(change => Array.from(change.addedNodes).some(node => node.nodeType === 1 && (node.matches("[data-gal-confnotes]") || node.querySelector("[data-gal-confnotes]"))))) initialize();
  }).observe(document.documentElement, {childList: true, subtree: true});
})();
