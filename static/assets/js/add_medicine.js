
const variantsContainer = document.getElementById('variantsContainer');
const addVariantBtn = document.getElementById('addVariantBtn');

// Unit choices from Django (injected via HTML)
const unitOptions = window.UNIT_CHOICES 
    ? window.UNIT_CHOICES.map(c => `<option value="${c.value}">${c.label}</option>`).join('')
    : '<option value="piece">Piece</option>';

/* ── Core: recalculate stock for one variant row ── */
function recalcStock(row) {
    const stripInput = row.querySelector('.strip-input');
    const upsInput = row.querySelector('.ups-input');
    const hiddenStock = row.querySelector('.stock-hidden');
    const preview = row.querySelector('.stock-preview');
    const previewText = row.querySelector('.preview-text');

    const strips = parseInt(stripInput.value, 10);
    const ups = parseInt(upsInput.value, 10);

    const validStrips = !isNaN(strips) && strips >= 0;
    const validUps = !isNaN(ups) && ups > 0;

    if (validStrips && validUps) {
        const computed = strips * ups;
        hiddenStock.value = computed;
        previewText.textContent = `${strips} strips × ${ups} units/strip = ${computed} units`;
        preview.style.display = 'flex';
        preview.style.alignItems = 'center';
    } else if (validStrips && !validUps) {
        // No unit_per_strip set → treat strips field as raw units
        hiddenStock.value = strips;
        previewText.textContent = `${strips} units (no strip size set)`;
        preview.style.display = 'flex';
        preview.style.alignItems = 'center';
    } else {
        hiddenStock.value = 0;
        preview.style.display = 'none';
    }
}

/* ── Attach listeners to a row ── */
function attachRowListeners(row) {
    // Strip / UPS → recalculate
    row.querySelector('.strip-input').addEventListener('input', () => recalcStock(row));
    row.querySelector('.ups-input').addEventListener('input', () => recalcStock(row));

    // Remove button
    row.querySelector('.remove-variant-btn').addEventListener('click', function () {
        row.remove();
        updateRemoveBtns();
    });
}

function updateRemoveBtns() {
    const rows = variantsContainer.querySelectorAll('.variant-row');
    rows.forEach(row => {
        row.querySelector('.remove-variant-btn').disabled = rows.length === 1;
    });
}

/* ── Init existing rows ── */
variantsContainer.querySelectorAll('.variant-row').forEach(row => {
    attachRowListeners(row);
    recalcStock(row);
});
updateRemoveBtns();

/* ── Add new variant row ── */
addVariantBtn.addEventListener('click', function () {
    const row = document.createElement('div');
    row.className = 'variant-row';
    row.style.cssText = 'background:#f8fbff; border:1px solid #e2e8f0; border-radius:10px; padding:14px; margin-bottom:12px;';
    row.innerHTML = `
            <div style="display:grid; grid-template-columns:1fr 1fr 1fr 1fr 1fr; gap:10px; margin-bottom:10px;">
                <div>
                    <label class="patient-label" style="font-size:0.78rem;">Power / Strength</label>
                    <input type="text" name="power[]" class="patient-input" placeholder="e.g., 250mg" required>
                </div>
                <div>
                    <label class="patient-label" style="font-size:0.78rem;">Cost Price (₹)</label>
                    <input type="number" name="cost_price[]" class="patient-input" placeholder="0.00" min="0" step="0.01" required>
                </div>
                <div>
                    <label class="patient-label" style="font-size:0.78rem;">Selling Price (₹)</label>
                    <input type="number" name="selling_price[]" class="patient-input" placeholder="0.00" min="0" step="0.01" required>
                </div>
                <div>
                    <label class="patient-label" style="font-size:0.78rem;">Total Strips</label>
                    <input type="number" name="total_strips[]" class="patient-input strip-input" placeholder="e.g., 20" min="0">
                    <input type="hidden" name="stock[]" class="stock-hidden" value="0">
                </div>
                <div>
                    <label class="patient-label" style="font-size:0.78rem;">Low Alert</label>
                    <input type="number" name="low_stock_alert[]" class="patient-input" value="10" min="0">
                </div>
            </div>
            <div style="display:grid; grid-template-columns:1fr 1fr 1fr 1fr auto; gap:10px; align-items:end;">
                <div>
                    <label class="patient-label" style="font-size:0.78rem;">Unit</label>
                    <select name="unit[]" class="patient-input">${unitOptions}</select>
                </div>
                <div>
                    <label class="patient-label" style="font-size:0.78rem;">Unit / Strip</label>
                    <input type="number" name="unit_per_strip[]" class="patient-input ups-input" placeholder="e.g., 10" min="1">
                </div>
                <div>
                    <label class="patient-label" style="font-size:0.78rem;">Mfg Date</label>
                    <input type="date" name="mfg_date[]" class="patient-input">
                </div>
                <div>
                    <label class="patient-label" style="font-size:0.78rem;">Exp Date</label>
                    <input type="date" name="exp_date[]" class="patient-input">
                </div>
                <div style="padding-bottom:2px;">
                    <button type="button" class="btn btn-sm btn-outline-danger remove-variant-btn" style="border-radius:8px;">
                        <i class="bi bi-trash"></i>
                    </button>
                </div>
            </div>
            <div class="stock-preview" style="
                display:none;
                margin-top:10px;
                padding:7px 12px;
                background:linear-gradient(90deg,#eef6ff 0%,#f0fff8 100%);
                border:1px solid #c7dff7;
                border-radius:8px;
                font-size:0.8rem;
                color:#2c5282;
            ">
                <i class="bi bi-calculator" style="color:#3182ce;"></i>
                &nbsp;<strong>Calculated stock:</strong>
                &nbsp;<span class="preview-text">—</span>
                <span style="color:#718096; margin-left:6px; font-size:0.75rem;">(units stored in DB)</span>
            </div>`;

    variantsContainer.appendChild(row);
    attachRowListeners(row);
    updateRemoveBtns();
});

/* ── Guard: make sure hidden stock[] is up-to-date on submit ── */
document.getElementById('addMedicineForm').addEventListener('submit', function () {
    variantsContainer.querySelectorAll('.variant-row').forEach(row => recalcStock(row));
});
