/* SPDX-FileCopyrightText: 2024-2026 Knut Zoch
 * SPDX-License-Identifier: GPL-3.0-only */
(() => {
  "use strict";
  const common = window.GALCommon;
  if (!common) return;
  if (window.GALOngoing) {
    window.GALOngoing.initialize();
    return;
  }
  const initialized = new WeakSet();
  function initialize() {
    document.querySelectorAll(".gal-ongoing[data-gal-collection]").forEach((root) => {
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
      function readURL() {
        const params = common.readURLFields({q: search});
        if (sorter) {
          const value = params.get("sort");
          sorter.value = Array.from(sorter.options).some(option => option.value === value)
            ? value : sorter.options[0].value;
        }
        const values = params.getAll("subgroup");
        subgroupButtons.forEach(button => button.setAttribute("aria-pressed", String(values.includes(button.dataset.galValue))));
      }
      function writeURL() {
        common.writeURLParams({
          q: search.value.trim(),
          subgroup: subgroupButtons.filter(button => button.getAttribute("aria-pressed") === "true")
            .map(button => button.dataset.galValue),
          sort: sorter && sorter.value !== sorter.options[0].value ? sorter.value : "",
        });
      }
      readURL();
      const cardControllers = [];
      const expandAll = controls.querySelector("[data-gal-expand-all]");
      function updateExpandAll() {
        if (!expandAll) return;
        const visible = cardControllers.filter(({card}) => !card.hidden);
        const expanded = visible.length > 0 && visible.every(({panel}) => !panel.hidden);
        common.updateExpandButton(expandAll, visible.length, expanded);
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
        counter.textContent = `${count} of ${items.length} ${root.dataset.galNoun || "results"}`;
        empty.hidden = count !== 0;
        writeURL();
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
        readURL();
        update();
      });
      initialized.add(root);
      controls.hidden = false;
      update();
      openAnchoredCard();
    });
  }
  window.GALOngoing = {initialize};
  common.observeCollections('.gal-ongoing[data-gal-collection]', initialize);
})();
