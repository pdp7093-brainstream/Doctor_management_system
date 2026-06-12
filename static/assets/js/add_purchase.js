const itemsContainer = document.getElementById('itemsContainer');
const addItemBtn = document.getElementById('addItemBtn');
const medicineSearchUrl = "/medicine/search/";
const autocompleteTimers = new WeakMap();

function updateRemoveBtns() {
    const rows = itemsContainer.querySelectorAll('.purchase-item-row');
    rows.forEach(row => {
        const btn = row.querySelector('.remove-item-btn');
        if (btn) btn.disabled = rows.length === 1;
    });
}

function attachRemoveListener(row) {
    const btn = row.querySelector('.remove-item-btn');
    if (btn) {
        btn.addEventListener('click', function () {
            row.remove();
            updateRemoveBtns();
        });
    }
}

// Existing rows
itemsContainer.querySelectorAll('.purchase-item-row').forEach(attachRemoveListener);

addItemBtn.addEventListener('click', function () {
    const row = document.createElement('div');
    row.className = 'purchase-item-row';
    row.style.cssText = 'background:#f8fbff; border:1px solid #e2e8f0; border-radius:10px; padding:14px; margin-bottom:12px;';
    row.innerHTML = `
            <div style="display:grid; grid-template-columns:2fr 1fr 1fr auto;
                        gap:10px; align-items:end;">
                <div style="position:relative;">
                    <label class="patient-label" style="font-size:0.78rem;">Medicine</label>
                    <input type="text" class="patient-input medicine-search"
                        placeholder="Name, short name, or company..." autocomplete="off">
                    <input type="hidden" name="variant_id[]" class="variant-id">
                    <input type="hidden" name="strip_price[]" value="0">
                    <input type="hidden" name="tax_percent[]" value="0">
                    <input type="hidden" name="discount_amount[]" value="0">
                    <div class="autocomplete-list"
                        style="display:none; position:absolute; top:100%; left:0; right:0;
                               background:white; border:1px solid #ddd; border-top:none;
                               border-radius:0 0 8px 8px; max-height:280px; overflow-y:auto;
                               z-index:1000; box-shadow:0 4px 8px rgba(0,0,0,0.12);">
                    </div>
                </div>
                <div>
                    <label class="patient-label" style="font-size:0.78rem;">Qty Strips</label>
                    <input type="number" name="quantity_strips[]"
                        class="patient-input" placeholder="e.g. 10" min="1" required>
                </div>
                <div>
                    <label class="patient-label" style="font-size:0.78rem;">Unit/Strip</label>
                    <input type="number" name="unit_per_strip[]"
                        class="patient-input" placeholder="e.g. 10" min="1" required>
                </div>
                <div style="padding-bottom:2px;">
                    <button type="button" class="btn btn-sm btn-outline-danger remove-item-btn"
                        style="border-radius:8px;">
                        <i class="bi bi-trash"></i>
                    </button>
                </div>
            </div>`;

    itemsContainer.appendChild(row);
    attachRemoveListener(row);
    updateRemoveBtns();
});

function hideAutocomplete(row) {
    const dropdown = row.querySelector('.autocomplete-list');
    if (!dropdown) return;
    dropdown.style.display = 'none';
    dropdown.innerHTML = '';
}

function showAutocompleteMessage(dropdown, message) {
    dropdown.innerHTML = '';
    const item = document.createElement('div');
    item.textContent = message;
    item.style.cssText = 'padding:10px 12px; color:#6c757d; font-size:0.86rem;';
    dropdown.appendChild(item);
    dropdown.style.display = 'block';
}

function renderMedicineResults(row, medicines) {
    const dropdown = row.querySelector('.autocomplete-list');
    dropdown.innerHTML = '';

    if (!medicines.length) {
        showAutocompleteMessage(dropdown, 'No medicine found');
        return;
    }

    medicines.forEach(medicine => {
        const item = document.createElement('button');
        item.type = 'button';
        item.className = 'autocomplete-item';
        item.dataset.variantId = medicine.id;
        item.dataset.medicineName = medicine.name;
        item.style.cssText = 'width:100%; border:0; background:#fff; padding:10px 12px; text-align:left; cursor:pointer; border-bottom:1px solid #eef2f7;';

        const title = document.createElement('div');
        title.textContent = `${medicine.name}${medicine.power ? ' - ' + medicine.power : ''}`;
        title.style.cssText = 'font-weight:700; color:#1f2937; font-size:0.9rem;';

        const meta = document.createElement('div');
        meta.textContent = medicine.company || 'Generic';
        meta.style.cssText = 'font-size:0.78rem; color:#6b7280; margin-top:2px;';

        item.appendChild(title);
        item.appendChild(meta);
        item.addEventListener('mouseenter', () => item.style.background = '#f8fbff');
        item.addEventListener('mouseleave', () => item.style.background = '#fff');
        dropdown.appendChild(item);
    });

    dropdown.style.display = 'block';
}

function searchMedicines(input) {
    const row = input.closest('.purchase-item-row');
    const dropdown = row.querySelector('.autocomplete-list');
    const variantIdInput = row.querySelector('.variant-id');
    const query = input.value.trim();

    variantIdInput.value = '';

    if (!query) {
        // Still search with empty query to get top options
        // but we don't return early
    }

    showAutocompleteMessage(dropdown, 'Searching...');

    fetch(`${medicineSearchUrl}?q=${encodeURIComponent(query)}`)
        .then(response => {
            if (!response.ok) throw new Error('Search request failed');
            return response.json();
        })
        .then(medicines => {
            if (input.value.trim() !== query) return;
            renderMedicineResults(row, medicines);
        })
        .catch(() => {
            showAutocompleteMessage(dropdown, 'Unable to search medicines');
        });
}

document.addEventListener('keyup', function (e) {
    if (!e.target.classList.contains('medicine-search')) return;

    const input = e.target;
    const timer = autocompleteTimers.get(input);
    if (timer) clearTimeout(timer);

    autocompleteTimers.set(input, setTimeout(() => searchMedicines(input), 300));
});

document.addEventListener('focusin', function (e) {
    if (e.target.classList.contains('medicine-search')) {
        const input = e.target;
        const dropdown = input.closest('.purchase-item-row').querySelector('.autocomplete-list');
        // If dropdown is hidden or empty, trigger a search to show top options
        if (!dropdown.style.display || dropdown.style.display === 'none' || dropdown.innerHTML === '') {
            searchMedicines(input);
        }
    }
});

document.addEventListener('click', function (e) {
    const item = e.target.closest('.autocomplete-item');

    if (item) {
        const row = item.closest('.purchase-item-row');
        const variantId = item.dataset.variantId;
        const variantInput = row.querySelector('.variant-id');

        console.log("Selected Variant:", variantId);
        console.log(variantInput);

        row.querySelector('.medicine-search').value = item.dataset.medicineName;
        variantInput.value = variantId;
        hideAutocomplete(row);
        return;
    }

    if (!e.target.closest('.autocomplete-list') && !e.target.classList.contains('medicine-search')) {
        itemsContainer.querySelectorAll('.purchase-item-row').forEach(row => hideAutocomplete(row));
    }
});

document.querySelector('form').addEventListener('submit', function (e) {
    const invalidRow = Array.from(itemsContainer.querySelectorAll('.purchase-item-row')).find(row => {
        return !row.querySelector('.variant-id').value;
    });

    if (invalidRow) {
        e.preventDefault();
        invalidRow.querySelector('.medicine-search').focus();
        alert('Please select a medicine from the search results.');
    }
});

updateRemoveBtns();
