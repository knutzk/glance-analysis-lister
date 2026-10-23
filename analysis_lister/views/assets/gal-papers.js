/* SPDX-FileCopyrightText: 2024-2026 Knut Zoch
 * SPDX-License-Identifier: GPL-3.0-only */
(() => {
  "use strict";
  const common = window.GALCommon;
  if (!common) return;
  if (window.GALPapers) {
    window.GALPapers.initialize();
    return;
  }
  const initialized = new WeakSet();
  function initialize() {
    document.querySelectorAll("[data-gal-archive]").forEach((root) => {
      if (initialized.has(root)) return;
      const controls = root.querySelector("[data-gal-controls]");
      const search = root.querySelector("[data-gal-search]");
      const counter = root.querySelector("[data-gal-count]");
      const empty = root.querySelector("[data-gal-empty]");
      if (!controls || !search || !counter || !empty) return;
      let items;
      try {
        items = Array.from(root.querySelectorAll("[data-gal-item]"), (element) => ({
          element, metadata: JSON.parse(element.dataset.galMetadata),
          toggle: element.querySelector("[data-gal-paper-toggle]"),
          panel: element.nextElementSibling, expanded: false,
        }));
      } catch (_) {
        return; // Keep the complete static collection if metadata is unreadable.
      }
      const categories = Array.from(controls.querySelectorAll("[data-gal-filter]"));
      const after = controls.querySelector("[data-gal-date-after]");
      const before = controls.querySelector("[data-gal-date-before]");
      const expandAll = controls.querySelector("[data-gal-archive-expand-all]");
      const urlKeys = {publication_status: "status"};
      function readURL() {
        const params = new URLSearchParams(location.search);
        search.value = params.get("q") || "";
        after.value = params.get("after") || "";
        before.value = params.get("before") || "";
        categories.forEach(category => {
          const values = params.getAll(urlKeys[category.dataset.galFilter] || category.dataset.galFilter);
          category.querySelectorAll("[data-gal-value]").forEach(button => button.setAttribute("aria-pressed", String(values.includes(button.dataset.galValue))));
        });
      }
      function writeURL(selections) {
        const url = new URL(location.href);
        for (const [key, value] of [["q", search.value.trim()], ["after", after.value], ["before", before.value]]) {
          url.searchParams.delete(key);
          if (value) url.searchParams.set(key, value);
        }
        selections.forEach(({key, values}) => {
          const param = urlKeys[key] || key;
          url.searchParams.delete(param);
          values.forEach(value => url.searchParams.append(param, value));
        });
        common.replaceURL(url);
      }
      function syncExpandAll() {
        if (!expandAll) return;
        const visible = items.filter(item => !item.element.hidden);
        const expanded = visible.length > 0 && visible.every(item => item.expanded);
        common.updateExpandButton(expandAll, visible.length, expanded);
      }
      function update() {
        const query = search.value.trim().toLowerCase();
        const selections = categories.map((category) => ({
          key: category.dataset.galFilter,
          values: [
            ...Array.from(category.querySelectorAll('[aria-pressed="true"]'), (button) => button.dataset.galValue),
          ],
        }));
        const matched = items.filter(({metadata, element}) => {
          const dateMatches = common.monthMatches(element.dataset.galDate, after.value, before.value);
          const matches = dateMatches && (!query || (metadata.text || "").toLowerCase().includes(query)) &&
            selections.every(({key, values}) => {
              const available = Array.isArray(metadata[key]) ? metadata[key] : [metadata[key]];
              return !values.length || values.some((value) => available.includes(value));
            });
          return matches;
        });
        const count = matched.length;
        const shown = new Set(matched);
        let stripe = 0;
        items.forEach(item => {
          item.element.hidden = !shown.has(item);
          item.panel.hidden = item.element.hidden || !item.expanded;
          item.element.classList.toggle("gal-paper--stripe", shown.has(item) && stripe++ % 2 === 1);
        });
        counter.textContent = `${count} of ${items.length} ${root.dataset.galNoun || "results"}`;
        empty.hidden = count !== 0;
        writeURL(selections);
        syncExpandAll();
      }
      controls.addEventListener("click", (event) => {
        const button = event.target.closest("button");
        if (!button || !controls.contains(button)) return;
        if (button.hasAttribute("data-gal-archive-expand-all")) {
          const expanded = button.getAttribute("aria-pressed") !== "true";
          items.filter(item => !item.element.hidden).forEach(item => item.setExpanded(expanded));
          syncExpandAll();
          return;
        }
        if (button.hasAttribute("data-gal-reset")) {
          after.value = "";
          before.value = "";
          search.value = "";
          controls.querySelectorAll("[data-gal-value]").forEach((option) => option.setAttribute("aria-pressed", "false"));
        } else if (button.hasAttribute("data-gal-value")) {
          button.setAttribute("aria-pressed", button.getAttribute("aria-pressed") === "true" ? "false" : "true");
        } else return;
        update();
      });
      search.addEventListener("input", update);
      controls.addEventListener("change", update);
      root.classList.add("gal-papers--interactive");
      items.forEach(item => {
        const {element, toggle, panel} = item;
        if (!toggle || !panel) return;
        const collapse = panel.querySelector("[data-gal-paper-collapse]");
        function setExpanded(value) {
          item.expanded = value;
          panel.hidden = !value || element.hidden;
          toggle.setAttribute("aria-expanded", String(value));
          syncExpandAll();
        }
        item.setExpanded = setExpanded;
        toggle.setAttribute("role", "button");
        toggle.tabIndex = 0;
        setExpanded(false);
        collapse.hidden = false;
        element.addEventListener("click", event => {
          if (event.target.closest("a, button, input, select")) return;
          setExpanded(!item.expanded);
        });
        toggle.addEventListener("keydown", event => {
          if (event.key !== "Enter" && event.key !== " ") return;
          event.preventDefault();
          setExpanded(!item.expanded);
        });
        collapse.addEventListener("click", () => {
          setExpanded(false);
          toggle.focus();
        });
      });
      window.addEventListener("popstate", () => { if (root.isConnected) { readURL(); update(); } });
      readURL();
      initialized.add(root);
      controls.hidden = false;
      update();
    });
  }
  window.GALPapers = {initialize};
  common.observeCollections('[data-gal-archive]', initialize);
})();
