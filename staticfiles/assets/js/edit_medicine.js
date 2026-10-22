const variantsContainer = document.getElementById('variantsContainer');
const addVariantBtn = document.getElementById('addVariantBtn');

/* ── Core: recalculate hidden stock[] for one row ── */
function recalcStock(row) {
    const stripInput = row.querySelector('.strip-input');
    const upsInput = row.querySelector('.ups-input');
    const hiddenStock = row.querySelector('.stock-hidden');
    const preview = row.querySelector('.stock-preview');
    const previewText = row.querySelector('.preview-text');

    if (!stripInput || !upsInput || !hiddenStock) return;

    const strips = parseInt(stripInput.value, 10);
    const ups = parseInt(upsInput.value, 10);

    const validStrips = !isNaN(strips) && strips >= 0;
    const validUps = !isNaN(ups) && ups > 0;

    if (validStrips && validUps) {
        const computed = strips * ups;
        hiddenStock.value = computed;
        previewText.textContent = `${strips} packs × ${ups} units/pack = ${computed} units`;
        preview.style.display = 'inline-flex';
    } else if (validStrips && !validUps) {
        hiddenStock.value = strips;
        previewText.textContent = `${strips} units (1 pack = 1 unit)`;
        preview.style.display = 'inline-flex';
    } else {
        hiddenStock.value = 0;
        preview.style.display = 'none';
    }
}

function renumber() {
    variantsContainer.querySelectorAll('.variant-row').forEach((row, index) => {
        const no = row.querySelector('.variant-no');
        if (no) no.textContent = index + 1;
    });
}

function updateRemoveBtns() {
    const rows = variantsContainer.querySelectorAll('.variant-row');
    rows.forEach(row => {
        row.querySelector('.remove-variant-btn').disabled = rows.length === 1;
    });
}

/* ── Attach all listeners to a row ── */
function attachRowListeners(row) {
    const stripInput = row.querySelector('.strip-input');
    const upsInput = row.querySelector('.ups-input');
    if (stripInput) stripInput.addEventListener('input', () => recalcStock(row));
    if (upsInput) upsInput.addEventListener('input', () => recalcStock(row));

    row.querySelector('.remove-variant-btn').addEventListener('click', function () {
        row.remove();
        renumber();
        updateRemoveBtns();
    });
}

function addVariantRow() {
    const row = document.getElementById('variantTemplate').content.firstElementChild.cloneNode(true);
    variantsContainer.appendChild(row);
    attachRowListeners(row);
    recalcStock(row);
    renumber();
    updateRemoveBtns();
    return row;
}

/* ── Init existing rows ── */
variantsContainer.querySelectorAll('.variant-row').forEach(row => {
    attachRowListeners(row);
    recalcStock(row);   // show initial preview if values already set
});
renumber();
updateRemoveBtns();

if (!variantsContainer.querySelector('.variant-row')) {
    addVariantRow();
}

/* ── Add new variant row ── */
addVariantBtn.addEventListener('click', function () {
    addVariantRow();
});

/* ── Guard: ensure hidden stock[] is up-to-date on submit ── */
document.querySelector('form').addEventListener('submit', function () {
    variantsContainer.querySelectorAll('.variant-row').forEach(row => recalcStock(row));
});

/* ── Custom Medicine Type Dropdown ── */
function initMedicineTypeDropdown() {
    const wrap = document.querySelector('.med-type-dropdown-wrap');
    if (!wrap) return;
    const trigger = wrap.querySelector('.med-type-trigger');
    const menu = wrap.querySelector('.med-type-menu');
    const search = wrap.querySelector('.med-type-search');
    const items = Array.from(wrap.querySelectorAll('.med-type-item'));
    const emptyMsg = wrap.querySelector('.med-type-empty');
    const hiddenInput = wrap.querySelector('input[name="medicine_type"]');
    const label = wrap.querySelector('.med-type-label');
    let highlightedIndex = -1;

    function getVisibleItems() {
        return items.filter(it => it.style.display !== 'none');
    }

    function openMenu() {
        menu.classList.add('show');
        trigger.setAttribute('aria-expanded', 'true');
        search.value = '';
        filterItems('');
        setTimeout(() => search.focus(), 50);
        const active = items.find(it => it.classList.contains('selected'));
        if (active) {
            highlightItem(getVisibleItems().indexOf(active));
            active.scrollIntoView({ block: 'nearest' });
        } else {
            highlightItem(0);
        }
    }

    function closeMenu(focusTrigger) {
        menu.classList.remove('show');
        trigger.setAttribute('aria-expanded', 'false');
        highlightItem(-1);
        if (focusTrigger) trigger.focus();
    }

    function highlightItem(index) {
        items.forEach(it => it.classList.remove('highlighted'));
        const visible = getVisibleItems();
        if (index >= 0 && index < visible.length) {
            visible[index].classList.add('highlighted');
            visible[index].scrollIntoView({ block: 'nearest' });
            highlightedIndex = index;
        } else {
            highlightedIndex = -1;
        }
    }

    function selectItem(item) {
        const val = item.getAttribute('data-value');
        const text = item.textContent.trim();
        hiddenInput.value = val;
        label.textContent = text;
        label.classList.remove('text-muted');
        items.forEach(it => it.classList.remove('selected'));
        item.classList.add('selected');
        trigger.classList.remove('is-invalid');
        hiddenInput.dispatchEvent(new Event('change', { bubbles: true }));
        closeMenu(true);
    }

    function filterItems(query) {
        const q = query.toLowerCase().trim();
        let matchCount = 0;
        items.forEach(it => {
            const match = !q || it.textContent.toLowerCase().includes(q);
            it.style.display = match ? '' : 'none';
            if (match) matchCount++;
        });
        if (emptyMsg) {
            emptyMsg.style.display = matchCount === 0 ? '' : 'none';
        }
        highlightItem(matchCount > 0 ? 0 : -1);
    }

    trigger.addEventListener('click', function (e) {
        e.preventDefault();
        if (menu.classList.contains('show')) {
            closeMenu();
        } else {
            openMenu();
        }
    });

    trigger.addEventListener('keydown', function (e) {
        if (e.key === 'ArrowDown' || e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            openMenu();
        }
    });

    search.addEventListener('input', function () {
        filterItems(search.value);
    });

    search.addEventListener('keydown', function (e) {
        const visible = getVisibleItems();
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            if (visible.length > 0) {
                const next = (highlightedIndex + 1) % visible.length;
                highlightItem(next);
            }
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            if (visible.length > 0) {
                const prev = (highlightedIndex - 1 + visible.length) % visible.length;
                highlightItem(prev);
            }
        } else if (e.key === 'Enter') {
            e.preventDefault();
            if (highlightedIndex >= 0 && highlightedIndex < visible.length) {
                selectItem(visible[highlightedIndex]);
            }
        } else if (e.key === 'Escape') {
            e.preventDefault();
            closeMenu(true);
        }
    });

    items.forEach(item => {
        item.addEventListener('click', function () {
            selectItem(item);
        });
    });

    document.addEventListener('click', function (e) {
        if (!wrap.contains(e.target)) {
            closeMenu();
        }
    });

    if (hiddenInput) {
        hiddenInput.addEventListener('invalid', function () {
            trigger.classList.add('is-invalid');
            trigger.focus();
        });
    }

    const form = wrap.closest('form');
    if (form) {
        form.addEventListener('submit', function (e) {
            if (!hiddenInput.value) {
                e.preventDefault();
                trigger.classList.add('is-invalid');
                trigger.focus();
                openMenu();
            }
        });
    }
}
initMedicineTypeDropdown();
