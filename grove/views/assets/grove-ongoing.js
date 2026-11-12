/* SPDX-FileCopyrightText: 2024-2026 Knut Zoch
 * SPDX-License-Identifier: GPL-3.0-only */
(() => {
  "use strict";
  const common = window.GROVECommon;
  if (!common) return;
  if (window.GROVEOngoing) {
    window.GROVEOngoing.initialize();
    return;
  }
  const initialized = new WeakSet();
  function initialize() {
    document.querySelectorAll(".grove-ongoing[data-grove-collection]").forEach((root) => {
      if (initialized.has(root)) return;
      const controls = root.querySelector("[data-grove-controls]");
      const search = root.querySelector("[data-grove-search]");
      const counter = root.querySelector("[data-grove-count]");
      const empty = root.querySelector("[data-grove-empty]");
      if (!controls || !search || !counter || !empty) return;
      let items;
      try {
        items = Array.from(root.querySelectorAll("[data-grove-item]"), (element) => ({
          element, metadata: JSON.parse(element.dataset.groveMetadata),
        }));
      } catch (_) {
        return; // Keep the complete static collection if metadata is unreadable.
      }
      const categories = Array.from(controls.querySelectorAll("[data-grove-filter]"));
      const sorter = controls.querySelector("[data-grove-sort]");
      const cardContainer = root.querySelector(".grove-cards");
      const subgroupButtons = Array.from(controls.querySelectorAll('[data-grove-filter="subgroups"] button'));
      function readURL() {
        const params = common.readURLFields({q: search});
        if (sorter) {
          const value = params.get("sort");
          sorter.value = Array.from(sorter.options).some(option => option.value === value)
            ? value : sorter.options[0].value;
        }
        const values = params.getAll("subgroup");
        subgroupButtons.forEach(button => button.setAttribute("aria-pressed", String(values.includes(button.dataset.groveValue))));
      }
      function writeURL() {
        common.writeURLParams({
          q: search.value.trim(),
          subgroup: subgroupButtons.filter(button => button.getAttribute("aria-pressed") === "true")
            .map(button => button.dataset.groveValue),
          sort: sorter && sorter.value !== sorter.options[0].value ? sorter.value : "",
        });
      }
      readURL();
      const cardControllers = [];
      const expandAll = controls.querySelector("[data-grove-expand-all]");
      function updateExpandAll() {
        if (!expandAll) return;
        const visible = cardControllers.filter(({card}) => !card.hidden);
        const expanded = visible.length > 0 && visible.every(({panel}) => !panel.hidden);
        common.updateExpandButton(expandAll, visible.length, expanded);
      }
      let appliedSort;
      function update() {
        // Filtering does not change order. Moving every card also discards focus
        // and makes the browser lay out otherwise unchanged cards again.
        if (sorter && cardContainer && sorter.value !== appliedSort) {
          const ordered = [...items].sort((a, b) => {
            const stage = a.metadata.stage_order - b.metadata.stage_order;
            return (sorter.value === "reference" ? 0 : sorter.value === "stage-desc" ? -stage : stage) || a.metadata.reference.localeCompare(b.metadata.reference);
          });
          ordered.forEach(item => cardContainer.appendChild(item.element));
          appliedSort = sorter.value;
        }
        const query = search.value.trim().toLowerCase();
        const selections = categories.map((category) => ({
          key: category.dataset.groveFilter,
          values: [
            ...Array.from(category.querySelectorAll('[aria-pressed="true"]'), (button) => button.dataset.groveValue),
          ],
        }));
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
        counter.textContent = `${count} of ${items.length} ${root.dataset.groveNoun || "results"}`;
        empty.hidden = count !== 0;
        writeURL();
        updateExpandAll();
      }
      controls.addEventListener("click", (event) => {
        const button = event.target.closest("button");
        if (!button || !controls.contains(button)) return;
        if (button.hasAttribute("data-grove-expand-all")) {
          const expand = button.getAttribute("aria-pressed") !== "true";
          cardControllers.filter(({card}) => !card.hidden).forEach(controller => controller.setExpanded(expand));
          return;
        }
        if (button.hasAttribute("data-grove-reset")) {
          search.value = "";
          if (sorter) sorter.selectedIndex = 0;
          controls.querySelectorAll("[data-grove-value]").forEach((option) => option.setAttribute("aria-pressed", "false"));
        } else if (button.hasAttribute("data-grove-value")) {
          button.setAttribute("aria-pressed", button.getAttribute("aria-pressed") === "true" ? "false" : "true");
        } else return;
        update();
      });
      search.addEventListener("input", update);
      controls.addEventListener("change", update);
      root.querySelectorAll(".grove-card").forEach(card => {
        const toggle = card.querySelector("[data-grove-card-toggle]");
        const panel = card.querySelector(".grove-card__details");
        if (!toggle || !panel) return;
        const collapse = card.querySelector("[data-grove-card-collapse]");
        if (collapse) collapse.hidden = false;
        toggle.setAttribute("role", "button");
        toggle.tabIndex = 0;
        toggle.setAttribute("aria-expanded", "false");
        panel.hidden = true;
        card.classList.add("grove-card--expandable");
        function setExpanded(expanded) {
          panel.hidden = !expanded;
          card.classList.toggle("grove-card--open", expanded);
          toggle.setAttribute("aria-expanded", String(expanded));
          updateExpandAll();
        }
        function expand() { setExpanded(true); }
        cardControllers.push({card, panel, setExpanded});
        card.querySelector(".grove-card__permalink")?.addEventListener("click", () => setExpanded(true));
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
        if (controller.card.hidden) controls.querySelector("[data-grove-reset]").click();
        controller.setExpanded(true);
        requestAnimationFrame(() => controller.card.scrollIntoView({block: "start"}));
      }
      window.addEventListener("hashchange", openAnchoredCard);
      window.addEventListener("popstate", () => {
        if (!root.isConnected) return;
        readURL();
        update();
      });
      initialized.add(root);
      controls.hidden = false;
      update();
      openAnchoredCard();
    });
  }
  window.GROVEOngoing = {initialize};
  common.observeCollections('.grove-ongoing[data-grove-collection]', initialize);
})();
