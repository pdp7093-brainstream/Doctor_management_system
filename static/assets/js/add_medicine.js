
const variantsContainer = document.getElementById('variantsContainer');
const addVariantBtn = document.getElementById('addVariantBtn');

function updateRemoveBtns() {
    const rows = variantsContainer.querySelectorAll('.variant-row');
    rows.forEach(row => {
        row.querySelector('.remove-variant-btn').disabled = rows.length === 1;
    });
}

function variantRowHTML() {
    return `
        <div class="variant-row rounded-3 p-3 mb-3" style="background:#f8fbff; border:1px solid #e2e8f0;">
            <div style="display:grid; grid-template-columns:1fr 1fr 1fr 1fr auto; gap:12px; align-items:end;">
                <div>
                    <label style="font-size:0.78rem; font-weight:600; color:#475569; display:block; margin-bottom:4px;">Power / Strength</label>
                    <input type="text" name="power[]" class="form-control form-control-sm" placeholder="e.g., 250mg" required>
                </div>
                <div>
                    <label style="font-size:0.78rem; font-weight:600; color:#475569; display:block; margin-bottom:4px;">Price (₹)</label>
                    <input type="number" name="price[]" class="form-control form-control-sm" placeholder="0.00" min="0" step="0.01" required>
                </div>
                <div>
                    <label style="font-size:0.78rem; font-weight:600; color:#475569; display:block; margin-bottom:4px;">Stock</label>
                    <input type="number" name="stock[]" class="form-control form-control-sm" placeholder="0" min="0" required>
                </div>
                <div>
                    <label style="font-size:0.78rem; font-weight:600; color:#475569; display:block; margin-bottom:4px;">Low Alert</label>
                    <input type="number" name="low_stock_alert[]" class="form-control form-control-sm" value="10" min="0">
                </div>
                <div>
                    <button type="button" class="btn btn-sm remove-variant-btn"
                            style="background:#fee2e2; color:#dc2626; border:1px solid #fecaca; border-radius:8px;">
                        <i class="bi bi-trash"></i>
                    </button>
                </div>
            </div>
        </div>`;
}

addVariantBtn.addEventListener('click', function () {
    const tmp = document.createElement('div');
    tmp.innerHTML = variantRowHTML();
    const row = tmp.firstElementChild;
    row.querySelector('.remove-variant-btn').addEventListener('click', function () {
        row.remove();
        updateRemoveBtns();
    });
    variantsContainer.appendChild(row);
    updateRemoveBtns();
});

// First row remove button
variantsContainer.querySelector('.remove-variant-btn').addEventListener('click', function () {
    this.closest('.variant-row').remove();
    updateRemoveBtns();
});

