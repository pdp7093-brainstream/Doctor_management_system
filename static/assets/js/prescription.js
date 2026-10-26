
let selectedVariantId = null;
let selectedMedicineName = '';
let selectedMedicinePower = '';
let selectedMedicineType = '';
const sevanKaalLabels = {
    before_food: 'Before Food',
    after_food: 'After Food',
    empty_stomach: 'Empty Stomach',
    with_food: 'With Food',
    between_meals: 'Between Meals',
    bedtime: 'Bedtime'
};

// ===== Beautiful Toast Notification System =====
function showToast(message, type = 'info', duration = 3000) {
    const toastContainer = document.getElementById('toastContainer');
    const toastId = `toast-${Date.now()}`;

    // Define toast styles based on type
    const toastStyles = {
        'success': {
            bgColor: '#10b981',
            borderColor: '#059669',
            icon: 'check-circle-fill',
            emoji: '✓'
        },
        'danger': {
            bgColor: '#ef4444',
            borderColor: '#dc2626',
            icon: 'exclamation-circle-fill',
            emoji: '✕'
        },
        'warning': {
            bgColor: '#f59e0b',
            borderColor: '#d97706',
            icon: 'exclamation-triangle-fill',
            emoji: '!'
        },
        'info': {
            bgColor: '#3b82f6',
            borderColor: '#1d4ed8',
            icon: 'info-circle-fill',
            emoji: 'ℹ'
        }
    };

    const style = toastStyles[type] || toastStyles['info'];

    const toastHtml = `
                <div id="${toastId}" class="toast-custom animate-slide-in" style="
                    background: linear-gradient(135deg, ${style.bgColor} 0%, ${style.bgColor}dd 100%);
                    border-left: 4px solid ${style.borderColor};
                    border-radius: 8px;
                    padding: 14px 16px;
                    margin-bottom: 12px;
                    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
                    display: flex;
                    align-items: center;
                    gap: 12px;
                    min-width: 280px;
                    max-width: 380px;
                    color: white;
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                    font-size: 14px;
                    font-weight: 500;
                    transition: all 0.3s cubic-bezier(0.23, 1, 0.320, 1);
                    position: relative;
                ">
                    <div class="toast-icon" style="
                        width: 28px;
                        height: 28px;
                        border-radius: 50%;
                        background: rgba(255, 255, 255, 0.2);
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        flex-shrink: 0;
                        font-weight: bold;
                        font-size: 16px;
                    ">
                        ${style.emoji}
                    </div>
                    <div class="toast-content" style="flex: 1;">
                        ${message}
                    </div>
                    <button type="button" class="toast-close" style="
                        background: none;
                        border: none;
                        color: rgba(255, 255, 255, 0.7);
                        cursor: pointer;
                        padding: 0;
                        font-size: 16px;
                        width: 20px;
                        height: 20px;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        flex-shrink: 0;
                        transition: color 0.2s;
                    " onmouseover="this.style.color='white'" onmouseout="this.style.color='rgba(255,255,255,0.7)'">
                        ×
                    </button>
                </div>
            `;

    toastContainer.insertAdjacentHTML('beforeend', toastHtml);
    const toastEl = document.getElementById(toastId);

    // Close button functionality
    const closeBtn = toastEl.querySelector('.toast-close');
    closeBtn.addEventListener('click', () => {
        toastEl.classList.add('animate-slide-out');
        setTimeout(() => toastEl.remove(), 300);
    });

    // Auto-hide after duration
    const hideTimeout = setTimeout(() => {
        if (toastEl.parentElement) {
            toastEl.classList.add('animate-slide-out');
            setTimeout(() => toastEl.remove(), 300);
        }
    }, duration);

    // Cancel auto-hide if manually closed
    closeBtn.addEventListener('click', () => clearTimeout(hideTimeout));
}

// ===== Medicine Form Validation =====
function validateMedicineForm() {
    // Check if medicine is selected
    if (!selectedVariantId) {
        showToast('Please select a medicine first', 'warning');
        return false;
    }

    // Get timing values
    const morning = parseInt(document.getElementById('modal_morning').value) || 0;
    const afternoon = parseInt(document.getElementById('modal_afternoon').value) || 0;
    const evening = parseInt(document.getElementById('modal_evening').value) || 0;
    const night = parseInt(document.getElementById('modal_night').value) || 0;

    // Check if at least one timing is selected
    if (morning === 0 && afternoon === 0 && evening === 0 && night === 0) {
        showToast('Please select at least one timing (Morning, Afternoon, Evening, or Night)', 'warning');
        return false;
    }

    // Check if Sevan Kaal is selected.
    const meal = document.getElementById('modal_meal').value;
    if (!meal || meal.trim() === '') {
        showToast('Please select Sevan Kaal', 'warning');
        return false;
    }

    // Check duration
    const days = parseInt(document.getElementById('modal_days').value) || 0;
    if (days <= 0) {
        showToast('Please enter a valid duration (greater than 0)', 'warning');
        return false;
    }

    return true;
}

document.addEventListener('DOMContentLoaded', function () {
    updateCounts();
    initDietAdviceEditor();
    // Bootstrap tooltips init
    document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(el => {
        new bootstrap.Tooltip(el);
    });
    document.getElementById('medicineModal').addEventListener('shown.bs.modal', () => {
        resetModalForm();
        document.getElementById('modalSearchInput').focus();
    });
    document.getElementById('medicineModal').addEventListener('hidden.bs.modal', () => {
        resetModalForm();
    });
});

function initDietAdviceEditor() {
    const card = document.querySelector('.advice-card');
    if (!card) return;

    function syncValue(column) {
        const items = Array.from(column.querySelectorAll('.advice-chip-label'), el => el.textContent.trim());
        column.querySelector('.advice-value').value = items.join('\n');
    }

    function addItem(column, value) {
        const item = value.trim().slice(0, 100);
        if (!item || item.toLowerCase() === 'none') return;
        const labels = Array.from(column.querySelectorAll('.advice-chip-label'), el => el.textContent.trim());
        if (labels.length >= 50 || labels.some(label => label.toLowerCase() === item.toLowerCase())) return;

        const chip = document.createElement('span');
        chip.className = 'advice-chip';
        const label = document.createElement('span');
        label.className = 'advice-chip-label';
        label.textContent = item;
        const remove = document.createElement('button');
        remove.type = 'button';
        remove.className = 'advice-remove';
        remove.setAttribute('aria-label', `Remove ${item}`);
        remove.textContent = '×';
        chip.append(label, remove);
        column.querySelector('.advice-items').appendChild(chip);
        syncValue(column);
    }

    card.querySelectorAll('.advice-column').forEach(syncValue);
    card.addEventListener('click', event => {
        const column = event.target.closest('.advice-column');
        if (!column) return;
        if (event.target.closest('.advice-remove')) {
            event.target.closest('.advice-chip').remove();
            syncValue(column);
        } else if (event.target.closest('.advice-add')) {
            const input = column.querySelector('.advice-input');
            addItem(column, input.value);
            input.value = '';
        } else {
            const suggestion = event.target.closest('[data-advice-suggestion]');
            if (suggestion) addItem(column, suggestion.dataset.adviceSuggestion);
        }
    });
    card.querySelectorAll('.advice-input').forEach(input => input.addEventListener('keydown', event => {
        if (event.key === 'Enter') {
            event.preventDefault();
            input.closest('.advice-column').querySelector('.advice-add').click();
        }
    }));
}

function resetModalForm() {
    try {
        selectedVariantId = null;
        selectedMedicineName = '';
        selectedMedicinePower = '';
        selectedMedicineType = '';
        document.getElementById('modalSearchInput').value = '';
        document.getElementById('modalSearchResults').innerHTML =
            '<div class="text-center py-4 text-muted border rounded-3 border-dashed"><p class="mb-0 small">Type to search medicines...</p></div>';

        const infoBox = document.getElementById('selectedMedicineInfo');
        if (infoBox) {
            infoBox.style.setProperty('display', 'none', 'important');
        }

        document.getElementById('modal_morning').value = 0;
        document.getElementById('modal_afternoon').value = 0;
        document.getElementById('modal_evening').value = 0;
        document.getElementById('modal_night').value = 0;
        document.getElementById('modal_days').value = 7;
        document.getElementById('modal_meal').value = 'after_food';
        document.getElementById('modal_anupana').value = '';
        document.getElementById('modal_medicine_notes').value = '';

        document.querySelectorAll('.v-chip').forEach(c => c.classList.remove('selected'));
    } catch (e) {
        console.error("Error in resetModalForm:", e);
    }
}

// ---- Search ----
let searchTimer;
const medicineResults = document.getElementById('modalSearchResults');
medicineResults.addEventListener('click', function (event) {
    const chip = event.target.closest('.v-chip');
    if (!chip || !medicineResults.contains(chip) || chip.classList.contains('out-of-stock')) return;
    const variantId = chip.dataset.variantId;
    if (!variantId) return;
    selectVariant(variantId, chip.dataset.name, chip);
});

document.getElementById('modalSearchInput').addEventListener('input', function () {
    const query = this.value.trim();
    const container = document.getElementById('modalSearchResults');

    if (query.length < 2) {
        container.innerHTML = '<div class="text-center py-4 text-muted border rounded-3 border-dashed"><p class="mb-0 small">Type to search medicines...</p></div>';
        return;
    }

    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
        fetch(`/medicine/search/?q=${encodeURIComponent(query)}&grouped=1`)
            .then(res => res.json())
            .then(data => {
                if (!data.medicines.length) {
                    container.innerHTML = '<div class="text-center py-4 text-muted">No medicines found.</div>';
                    return;
                }
                container.innerHTML = data.medicines.map(med => `
                            <div class="med-result-item">
                                <div class="d-flex justify-content-between align-items-start">
                                    <div>
                                        <span class="badge bg-primary-subtle text-primary mb-1">${escapeHtml(med.type || '')}</span>
                                        <h6 class="mb-0 fw-bold text-dark">${escapeHtml(med.name || '')}</h6>
                                        <small class="text-muted">${escapeHtml(med.company || 'Generic')}</small>
                                    </div>
                                </div>
                                <div class="variant-grid">
                                    ${med.variants.map(v => `
                                        <div class="v-chip ${v.stock <= 0 ? 'out-of-stock' : ''}"
                                             ${v.stock > 0 ? `data-variant-id="${escapeHtml(String(v.id))}" data-name="${escapeHtml(`${med.name || ''} ${v.power || ''}`.trim())}" data-type="${escapeHtml(med.type || '')}"` : ''}>
                                            <span class="stock-dot"></span>
                                            ${escapeHtml(v.power || '')} ${v.stock > 0 ? `<span class="ms-1 text-muted">(${escapeHtml(String(v.stock))})</span>` : '(OOS)'}
                                        </div>
                                    `).join('')}
                                </div>
                            </div>
                        `).join('');
            });
    }, 300);
});

function selectVariant(id, name, el) {
    document.querySelectorAll('.v-chip').forEach(c => c.classList.remove('selected'));
    el.classList.add('selected');
    selectedVariantId = id;
    selectedMedicineName = name;
    selectedMedicinePower = '';
    selectedMedicineType = el.dataset.type || '';
    const info = document.getElementById('selectedMedicineInfo');
    document.getElementById('selectedMedicineName').textContent = name;
    info.style.setProperty('display', 'flex', 'important');
}

function clearSelectedMedicine() {
    selectedVariantId = null;
    selectedMedicineName = '';
    selectedMedicinePower = '';
    selectedMedicineType = '';
    document.getElementById('selectedMedicineInfo').style.setProperty('display', 'none', 'important');
    document.querySelectorAll('.v-chip').forEach(c => c.classList.remove('selected'));
}

function escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function escapeAttr(value) {
    return escapeHtml(value).replace(/`/g, '&#096;');
}

function saveMedicine(close) {
    // Validate form before saving
    if (!validateMedicineForm()) {
        return;
    }

    const days = document.getElementById('modal_days').value;
    const m = document.getElementById('modal_morning').value;
    const a = document.getElementById('modal_afternoon').value;
    const e = document.getElementById('modal_evening').value;
    const n = document.getElementById('modal_night').value;
    const meal = document.getElementById('modal_meal').value;
    const anupana = document.getElementById('modal_anupana').value.trim();
    const medicineNotes = document.getElementById('modal_medicine_notes').value.trim();
    const mealLabel = sevanKaalLabels[meal] || '';

    // ✅ FIX: Default to true since toggle is removed
    const shouldDeduct = true;
    const rowIndex = document.querySelectorAll('#medicineList > tr').length;

    const totalQuantity = (Number(m) + Number(a) + Number(e) + Number(n)) * Number(days);
    const row = `
                <tr class="prescription-row">
                    <td class="select-col" data-label="Select">
                        <input type="checkbox" class="form-check-input prescription-checkbox" onchange="updatePrescriptionBulkDeleteBtn()">
                    </td>
                    <td class="medicine-cell" data-label="Medicine">
                        <div class="medicine-name"></div>
                        <div class="medicine-meta"><span class="medicine-type"></span>${medicineNotes ? `<span class="medicine-notes" title="${escapeAttr(medicineNotes)}"><i class="bi bi-journal-text"></i> ${escapeHtml(medicineNotes)}</span>` : ''}</div>
                        <input type="hidden" name="variant_id[]" value="${selectedVariantId}">
                        <input type="hidden" name="item_id[]" value="">
                        <input type="hidden" name="medicine_notes" value="${escapeAttr(medicineNotes)}">
                    </td>
                    <td class="dosage-cell" data-label="Dosage">
                        <div class="dosage-stack"><div class="dosage-pill"><span class="${Number(m) ? '' : 'dose-zero'}">${m}</span><span>–</span><span class="${Number(a) ? '' : 'dose-zero'}">${a}</span><span>–</span><span class="${Number(e) ? '' : 'dose-zero'}">${e}</span><span>–</span><span class="${Number(n) ? '' : 'dose-zero'}">${n}</span></div><div class="dosage-caption">M · A · E · N</div></div>
                        <input type="hidden" name="morning" value="${m}"><input type="hidden" name="afternoon" value="${a}"><input type="hidden" name="evening" value="${e}"><input type="hidden" name="night" value="${n}">
                    </td>
                    <td class="timing-cell" data-label="Timing">
                        <span class="badge bg-info-subtle text-info text-nowrap">${escapeHtml(mealLabel)}</span>
                        ${anupana ? `<span class="small text-muted d-inline-block">with ${escapeHtml(anupana)}</span>` : ''}
                        <input type="hidden" name="meal" value="${meal}">
                        <input type="hidden" name="anupana" value="${escapeAttr(anupana)}">
                    </td>
                    <td class="duration-cell" data-label="Duration"><div>${days} days</div><div class="duration-total">${totalQuantity} units</div><input type="hidden" name="days" value="${days}"></td>
                    <td class="stock-cell" data-label="Stock">
                        <label class="toggle-switch">
                            <input 
                                type="checkbox" 
                                name="should_deduct[]" 
                                value="${rowIndex}"
                                class="toggle-input"
                                ${shouldDeduct ? 'checked' : ''}
                                onchange="updateCounts()"
                            >
                            <span class="toggle-slider"></span>
                        </label>
                        <span class="stock-status will-deduct">Will deduct</span>
                    </td>
                    <td class="action-cell" data-label="Action">
                        <div class="action-btns"><button type="button" class="btn-act btn-act-delete" title="Delete" aria-label="Delete" onclick="removeMedicineRow(this)">
                            <i class="bi bi-trash"></i>
                        </button></div>
                    </td>
                </tr>`;

    document.getElementById('medicineList').insertAdjacentHTML('beforeend', row);
    const addedRow = document.getElementById('medicineList').lastElementChild;
    addedRow.querySelector('.medicine-name').textContent = selectedMedicineName;
    addedRow.querySelector('.medicine-type').textContent = selectedMedicineType || '—';
    document.getElementById('emptyMessage').style.display = 'none';
    currentPage = Math.max(1, Math.ceil(document.getElementById('medicineList').children.length / rowsPerPage));
    updateCounts();

    // Show success toast
    showToast(`${escapeHtml(selectedMedicineName)} added successfully!`, 'success', 2000);

    if (close) {
        const modalEl = document.getElementById('medicineModal');
        const modal = bootstrap.Modal.getInstance(modalEl) || bootstrap.Modal.getOrCreateInstance(modalEl);
        modal.hide();
        resetModalForm();
    } else {
        resetModalForm();
        document.getElementById('modalSearchInput').focus();
    }
}

function removeMedicineRow(btn) {
    btn.closest('tr').remove();
    reindexDeductRows();
    updateCounts();
    if (!document.getElementById('medicineList').children.length) {
        document.getElementById('emptyMessage').style.display = 'block';
    }
}

function reindexDeductRows() {
    document.querySelectorAll('#medicineList > tr').forEach((row, index) => {
        const checkbox = row.querySelector('input[name="should_deduct[]"]');
        if (checkbox) checkbox.value = String(index);
    });
}

function updateDeductCount() {
    updateCounts();
}

const rowsPerPage = 5;
let currentPage = 1;

function getMedicineRows() {
    return Array.from(document.querySelectorAll('#medicineList > tr'));
}

function renderPagination(totalPages) {
    const container = document.getElementById('paginationControls');
    const items = getMedicineRows();
    if (!container) return;
    if (items.length <= rowsPerPage) {
        container.innerHTML = '';
        return;
    }

    const prevDisabled = currentPage === 1 ? ' disabled' : '';
    const nextDisabled = currentPage === totalPages ? ' disabled' : '';

    const pages = Array.from({ length: totalPages }, (_, index) => {
        const page = index + 1;
        const active = page === currentPage ? ' active' : '';
        return `<li class="page-item${active}"><button type="button" class="page-link" onclick="changePage(${page})">${page}</button></li>`;
    }).join('');

    container.innerHTML = `
                <li class="page-item${prevDisabled}"><button type="button" class="page-link" onclick="changePage(${currentPage - 1})">Previous</button></li>
                ${pages}
                <li class="page-item${nextDisabled}"><button type="button" class="page-link" onclick="changePage(${currentPage + 1})">Next</button></li>
            `;
}

function showPage(page) {
    const rows = getMedicineRows();
    const totalPages = Math.max(1, Math.ceil(rows.length / rowsPerPage));
    currentPage = Math.min(Math.max(page, 1), totalPages);

    rows.forEach((row, index) => {
        const start = (currentPage - 1) * rowsPerPage;
        const end = currentPage * rowsPerPage;
        row.style.display = index >= start && index < end ? '' : 'none';
    });

    const emptyMessage = document.getElementById('emptyMessage');
    if (emptyMessage) emptyMessage.style.display = rows.length ? 'none' : 'block';

    const paginationInfo = document.getElementById('paginationInfo');
    if (paginationInfo) paginationInfo.textContent = rows.length;

    const paginationPlural = document.getElementById('paginationPlural');
    if (paginationPlural) paginationPlural.textContent = rows.length === 1 ? '' : 's';

    renderPagination(totalPages);
}

function changePage(page) {
    showPage(page);
}

function updateCounts() {
    const totalRows = document.getElementById('medicineList').children.length;
    const deductCount = document.querySelectorAll('input[name="should_deduct[]"]:checked').length;
    const listCount = document.getElementById('prescriptionListCount');
    if (listCount) listCount.textContent = `${totalRows} ${totalRows === 1 ? 'medicine' : 'medicines'}`;
    document.querySelectorAll('#medicineList > tr').forEach(row => {
        const doses = ['morning', 'afternoon', 'evening', 'night'].map(name => Number(row.querySelector(`input[name="${name}"]`)?.value || 0));
        const days = Number(row.querySelector('input[name="days"]')?.value || 0);
        const total = row.querySelector('.duration-total');
        if (total) total.textContent = `${doses.reduce((sum, dose) => sum + dose, 0) * days} units`;
        const toggle = row.querySelector('input[name="should_deduct[]"]');
        const status = row.querySelector('.stock-status');
        if (toggle && status && !status.classList.contains('is-deducted')) {
            status.textContent = toggle.checked ? 'Will deduct' : 'Skipped';
            status.className = `stock-status ${toggle.checked ? 'will-deduct' : 'is-skipped'}`;
        }
    });
    document.getElementById('medicineCount').textContent = totalRows;
    const deductEl = document.getElementById('deductCount');
    if (deductEl) deductEl.textContent = deductCount;
    showPage(currentPage);
}

// Bulk Delete for Prescriptions
function updatePrescriptionBulkDeleteBtn() {
    const checkboxes = document.querySelectorAll('.prescription-checkbox:checked');
    const btn = document.getElementById('bulkDeletePrescriptionBtn');
    if (!btn) return;
    if (checkboxes.length > 0) {
        btn.classList.remove('d-none');
    } else {
        btn.classList.add('d-none');
    }
    
    const allCheckboxes = document.querySelectorAll('.prescription-checkbox');
    const selectAll = document.getElementById('selectAllPrescriptions');
    if (selectAll) {
        selectAll.checked = allCheckboxes.length > 0 && allCheckboxes.length === checkboxes.length;
    }
}

function toggleAllPrescriptions(source) {
    const isChecked = source.checked;
    document.querySelectorAll('.prescription-checkbox').forEach(cb => {
        // Only select rows that are currently visible
        if (cb.closest('tr').style.display !== 'none') {
            cb.checked = isChecked;
        }
    });
    updatePrescriptionBulkDeleteBtn();
}

function bulkRemoveMedicineRows() {
    const checkboxes = document.querySelectorAll('.prescription-checkbox:checked');
    if (checkboxes.length === 0) return;
    
    Swal.fire({
        title: 'Remove selected medicines?',
        text: "These medicines will be removed from the current prescription.",
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#d33',
        cancelButtonColor: '#3085d6',
        confirmButtonText: 'Yes, remove them!'
    }).then((result) => {
        if (result.isConfirmed) {
            checkboxes.forEach(cb => {
                cb.closest('tr').remove();
            });
            
            updateCounts();
            updatePrescriptionBulkDeleteBtn();
            
            const selectAll = document.getElementById('selectAllPrescriptions');
            if (selectAll) selectAll.checked = false;
            
            if (!document.getElementById('medicineList').children.length) {
                document.getElementById('emptyMessage').style.display = 'block';
            }
        }
    });
}

function updateTherapyCount() {
    const count = document.querySelectorAll('#therapyList .therapy-prescription-row').length;
    const countBadge = document.getElementById('therapyListCount');
    if (countBadge) countBadge.textContent = `${count} ${count === 1 ? 'therapy' : 'therapies'}`;
    const emptyMessage = document.getElementById('therapyEmptyMessage');
    if (emptyMessage) emptyMessage.style.display = count ? 'none' : 'block';
}

function removeTherapyRow(button) {
    button.closest('.therapy-prescription-row')?.remove();
    updateTherapyCount();
}

function resetTherapyModal() {
    const modal = document.getElementById('therapyModal');
    document.getElementById('therapySearchInput').value = '';
    document.getElementById('therapySelect').value = '';
    document.getElementById('therapySessionsInput').value = '7';
    document.getElementById('therapyFrequencyInput').value = 'daily';
    document.getElementById('therapyStartInput').value = modal.dataset.visitDate || '';
    document.getElementById('therapyNotesInput').value = '';
    document.querySelectorAll('#therapySelect option').forEach(option => {
        option.hidden = false;
    });
}

function addTherapyRow() {
    const select = document.getElementById('therapySelect');
    const option = select.selectedOptions[0];
    const therapyId = select.value;
    const sessions = Number(document.getElementById('therapySessionsInput').value);
    const frequencySelect = document.getElementById('therapyFrequencyInput');
    const frequency = frequencySelect.value;
    const startDate = document.getElementById('therapyStartInput').value;
    const notes = document.getElementById('therapyNotesInput').value.trim();

    if (!therapyId) {
        showToast('Select a therapy first.', 'warning');
        return;
    }
    if (!Number.isInteger(sessions) || sessions < 1 || sessions > 60) {
        showToast('Therapy sessions must be between 1 and 60.', 'warning');
        return;
    }

    const dateLabel = startDate
        ? new Intl.DateTimeFormat('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }).format(new Date(`${startDate}T00:00:00`))
        : '—';
    const row = `
        <tr class="therapy-prescription-row">
            <td><div class="fw-semibold">${escapeHtml(option.textContent.trim())}</div><small class="text-muted">${escapeHtml(option.dataset.duration)} min</small><input type="hidden" name="therapy_id[]" value="${escapeAttr(therapyId)}"><input type="hidden" name="therapy_item_id[]" value=""></td>
            <td>${sessions}<input type="hidden" name="therapy_sessions[]" value="${sessions}"></td>
            <td>${escapeHtml(frequencySelect.selectedOptions[0].textContent)}<input type="hidden" name="therapy_frequency[]" value="${escapeAttr(frequency)}"></td>
            <td>${escapeHtml(dateLabel)}<input type="hidden" name="therapy_start[]" value="${escapeAttr(startDate)}"></td>
            <td>${notes ? escapeHtml(notes) : '—'}<input type="hidden" name="therapy_notes[]" value="${escapeAttr(notes)}"></td>
            <td class="text-end"><button type="button" class="btn-act btn-act-delete" title="Delete" aria-label="Delete therapy" onclick="removeTherapyRow(this)"><i class="bi bi-trash"></i></button></td>
        </tr>`;
    document.getElementById('therapyList').insertAdjacentHTML('beforeend', row);
    updateTherapyCount();
    resetTherapyModal();
    bootstrap.Modal.getInstance(document.getElementById('therapyModal'))?.hide();
}

const therapySearchInput = document.getElementById('therapySearchInput');
if (therapySearchInput) {
    therapySearchInput.addEventListener('input', () => {
        const query = therapySearchInput.value.trim().toLowerCase();
        document.querySelectorAll('#therapySelect option').forEach(option => {
            option.hidden = Boolean(option.value) && !option.textContent.toLowerCase().includes(query);
        });
        document.getElementById('therapySelect').value = '';
    });
}

document.getElementById('therapyModal')?.addEventListener('hidden.bs.modal', resetTherapyModal);
