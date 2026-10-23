/* SPDX-FileCopyrightText: 2024-2026 Knut Zoch
 * SPDX-License-Identifier: GPL-3.0-only */
(() => {
  "use strict";
  if (window.GALViews) {
    window.GALViews.initialize();
    return;
  }
  const initialized = new WeakSet();
  function initialize() {
    document.querySelectorAll("[data-gal-collection]").forEach((root) => {
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
        }));
      } catch (_) {
        return; // Keep the complete static collection if metadata is unreadable.
      }
      const categories = Array.from(controls.querySelectorAll("[data-gal-filter]"));
      const sorter = controls.querySelector("[data-gal-sort]");
      const cardContainer = root.querySelector(".gal-cards");
      const subgroupButtons = Array.from(controls.querySelectorAll('[data-gal-filter="subgroups"] button'));
      function readSubgroupURL() {
        const values = new URLSearchParams(window.location.search).getAll("subgroup");
        subgroupButtons.forEach(button => button.setAttribute("aria-pressed", String(values.includes(button.dataset.galValue))));
      }
      function writeSubgroupURL() {
        const url = new URL(window.location.href);
        url.searchParams.delete("subgroup");
        subgroupButtons.filter(button => button.getAttribute("aria-pressed") === "true")
          .forEach(button => url.searchParams.append("subgroup", button.dataset.galValue));
        if (url.href !== window.location.href) {
          try { window.history.replaceState(window.history.state, "", url); }
          catch (_) { /* Filtering still works when history updates are unavailable. */ }
        }
      }
      readSubgroupURL();
      const cardControllers = [];
      const expandAll = controls.querySelector("[data-gal-expand-all]");
      function updateExpandAll() {
        if (!expandAll) return;
        const visible = cardControllers.filter(({card}) => !card.hidden);
        const expanded = visible.length > 0 && visible.every(({panel}) => !panel.hidden);
        expandAll.disabled = visible.length === 0;
        expandAll.textContent = expanded ? "Collapse all" : "Expand all";
        expandAll.setAttribute("aria-pressed", String(expanded));
      }
      function update() {
        if (sorter && cardContainer) {
          const ordered = [...items].sort((a, b) => {
            const stage = a.metadata.stage_order - b.metadata.stage_order;
            return (sorter.value === "reference" ? 0 : sorter.value === "stage-desc" ? -stage : stage) || a.metadata.reference.localeCompare(b.metadata.reference);
          });
          ordered.forEach(item => cardContainer.appendChild(item.element));
        }
        const query = search.value.trim().toLowerCase();
        const selections = categories.map((category) => ({
          key: category.dataset.galFilter,
          values: [
            ...Array.from(category.querySelectorAll('[aria-pressed="true"]'), (button) => button.dataset.galValue),
            ...Array.from(category.querySelectorAll("input[data-gal-choice]:checked"), (choice) => choice.value),
            ...Array.from(category.querySelectorAll("select[data-gal-select]"), (select) => select.value).filter(Boolean),
          ],
        }));
        categories.forEach((category) => {
          const summary = category.querySelector("[data-gal-selection-summary]");
          if (!summary) return;
          const chosen = Array.from(category.querySelectorAll("[data-gal-choice]:checked"), (choice) => choice.value);
          summary.textContent = chosen.length === 0 ? summary.dataset.galDefault : chosen.length === 1 ? chosen[0] : `${chosen.length} selected`;
        });
        const matched = items.filter(({metadata}) => {
          const matches = (!query || (metadata.text || "").toLowerCase().includes(query)) &&
            selections.every(({key, values}) => {
              const available = Array.isArray(metadata[key]) ? metadata[key] : [metadata[key]];
              return !values.length || values.some((value) => available.includes(value));
            });
          return matches;
        });
        const count = matched.length;
        const shown = new Set(matched);
        items.forEach(item => { item.element.hidden = !shown.has(item); });
        counter.textContent = `${count} of ${items.length} ${root.dataset.galNoun || "results"}`;
        empty.hidden = count !== 0;
        writeSubgroupURL();
        updateExpandAll();
      }
      controls.addEventListener("click", (event) => {
        const button = event.target.closest("button");
        if (!button || !controls.contains(button)) return;
        if (button.hasAttribute("data-gal-expand-all")) {
          const expand = button.getAttribute("aria-pressed") !== "true";
          cardControllers.filter(({card}) => !card.hidden).forEach(controller => controller.setExpanded(expand));
          return;
        }
        if (button.hasAttribute("data-gal-reset")) {
          search.value = "";
          if (sorter) sorter.selectedIndex = 0;
          controls.querySelectorAll("input[data-gal-choice]").forEach((choice) => { choice.checked = false; });
          controls.querySelectorAll(".gal-multiselect[open]").forEach((menu) => { menu.open = false; });
          controls.querySelectorAll("select[data-gal-select]").forEach((select) => { select.selectedIndex = 0; });
          controls.querySelectorAll("[data-gal-value]").forEach((option) => option.setAttribute("aria-pressed", "false"));
        } else if (button.hasAttribute("data-gal-value")) {
          button.setAttribute("aria-pressed", button.getAttribute("aria-pressed") === "true" ? "false" : "true");
        } else return;
        update();
      });
      search.addEventListener("input", update);
      controls.addEventListener("change", update);
      root.querySelectorAll(".gal-card").forEach(card => {
        const toggle = card.querySelector("[data-gal-card-toggle]");
        const panel = card.querySelector(".gal-card__details");
        if (!toggle || !panel) return;
        const collapse = card.querySelector("[data-gal-card-collapse]");
        if (collapse) collapse.hidden = false;
        toggle.setAttribute("role", "button");
        toggle.tabIndex = 0;
        toggle.setAttribute("aria-expanded", "false");
        panel.hidden = true;
        card.classList.add("gal-card--expandable");
        function setExpanded(expanded) {
          panel.hidden = !expanded;
          card.classList.toggle("gal-card--open", expanded);
          toggle.setAttribute("aria-expanded", String(expanded));
          updateExpandAll();
        }
        function expand() { setExpanded(true); }
        cardControllers.push({card, panel, setExpanded});
        card.querySelector(".gal-card__permalink")?.addEventListener("click", () => setExpanded(true));
        toggle.addEventListener("click", expand);
        toggle.addEventListener("keydown", event => {
          if (!["Enter", " "].includes(event.key)) return;
          event.preventDefault();
          expand();
        });
        card.addEventListener("click", event => {
          if (!panel.hidden || event.target.closest("a, button, input, select, textarea") || window.getSelection()?.toString()) return;
          expand();
        });
        collapse?.addEventListener("click", () => {
          setExpanded(false);
          toggle.focus({preventScroll: true});
          card.scrollIntoView({block: "nearest"});
        });
      });
      function openAnchoredCard() {
        if (!root.isConnected || !window.location.hash) return;
        let id;
        try { id = decodeURIComponent(window.location.hash.slice(1)); }
        catch (_) { return; }
        const controller = cardControllers.find(({card}) => card.id === id);
        if (!controller) return;
        if (controller.card.hidden) controls.querySelector("[data-gal-reset]").click();
        controller.setExpanded(true);
        requestAnimationFrame(() => controller.card.scrollIntoView({block: "start"}));
      }
      window.addEventListener("hashchange", openAnchoredCard);
      window.addEventListener("popstate", () => {
        if (!root.isConnected) return;
        readSubgroupURL();
        update();
      });
      initialized.add(root);
      controls.hidden = false;
      update();
      openAnchoredCard();
    });
  }
  document.addEventListener("click", (event) => {
    document.querySelectorAll(".gal-multiselect[open]").forEach((menu) => {
      if (!menu.contains(event.target)) menu.open = false;
    });
  });
  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    document.querySelectorAll(".gal-multiselect[open]").forEach((menu) => {
      if (menu.contains(document.activeElement)) menu.querySelector("summary").focus();
      menu.open = false;
    });
  });
  window.GALViews = {initialize};
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", initialize, {once: true});
  else initialize();
  // Material/Zensical instant navigation publishes replaced documents here.
  if (typeof document$ !== "undefined" && document$.subscribe) document$.subscribe(initialize);
  // Also handle content inserted after startup or when no document$ is exposed.
  new MutationObserver((changes) => {
    if (changes.some((change) => Array.from(change.addedNodes).some((node) =>
      node.nodeType === 1 && (node.matches("[data-gal-collection]") || node.querySelector("[data-gal-collection]"))))) initialize();
  }).observe(document.documentElement, {childList: true, subtree: true});
})();
