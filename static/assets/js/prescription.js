
let selectedVariantId = null;
let selectedMedicineName = '';

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

    // Check if meal timing is selected (should have a value)
    const meal = document.getElementById('modal_meal').value;
    if (!meal || meal.trim() === '') {
        showToast('Please select meal timing (Before or After Food)', 'warning');
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

function resetModalForm() {
    try {
        selectedVariantId = null;
        selectedMedicineName = '';
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
        document.getElementById('modal_medicine_notes').value = '';

        document.querySelectorAll('.v-chip').forEach(c => c.classList.remove('selected'));
    } catch (e) {
        console.error("Error in resetModalForm:", e);
    }
}

// ---- Search ----
let searchTimer;
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
                                        <span class="badge bg-primary-subtle text-primary mb-1">${med.type}</span>
                                        <h6 class="mb-0 fw-bold text-dark">${med.name}</h6>
                                        <small class="text-muted">${med.company || 'Generic'}</small>
                                    </div>
                                </div>
                                <div class="variant-grid">
                                    ${med.variants.map(v => `
                                        <div class="v-chip ${v.stock <= 0 ? 'out-of-stock' : ''}"
                                             onclick="${v.stock > 0 ? `selectVariant(${v.id}, '${med.name} ${v.power}', this)` : ''}">
                                            <span class="stock-dot"></span>
                                            ${v.power} ${v.stock > 0 ? `<span class="ms-1 text-muted">(${v.stock})</span>` : '(OOS)'}
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
    const info = document.getElementById('selectedMedicineInfo');
    document.getElementById('selectedMedicineName').textContent = name;
    info.style.setProperty('display', 'flex', 'important');
}

function clearSelectedMedicine() {
    selectedVariantId = null;
    selectedMedicineName = '';
    document.getElementById('selectedMedicineInfo').style.setProperty('display', 'none', 'important');
    document.querySelectorAll('.v-chip').forEach(c => c.classList.remove('selected'));
}

function escapeHtml(value) {
    return value
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function escapeAttr(value) {
    return escapeHtml(value).replace(/`/g, '&#096;');
}

// ✅ Row index tracker — existing items se start hoga
function getNextIndex() {
    // Sabse bade index value ko find karo existing checkboxes se
    let max = -1;
    document.querySelectorAll('input[name="should_deduct[]"]').forEach(cb => {
        const val = parseInt(cb.value);
        if (val > max) max = val;
    });
    return max + 1;
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
    const medicineNotes = document.getElementById('modal_medicine_notes').value.trim();
    const mealLabel = meal === 'after_food' ? 'After Food' : 'Before Food';
    const mealBadge = meal === 'after_food'
        ? 'bg-info-subtle text-info'
        : 'bg-warning-subtle text-warning';

    // ✅ FIX: Default to true since toggle is removed
    const shouldDeduct = true;
    const rowIndex = getNextIndex();

    const row = `
                <tr>
                    <td class="text-center">
                        <input type="checkbox" class="form-check-input prescription-checkbox" onchange="updatePrescriptionBulkDeleteBtn()">
                    </td>
                    <td class="px-4">
                        <div class="fw-bold text-dark">${selectedMedicineName}</div>
                        ${medicineNotes ? `<div class="small text-muted mt-1"><i class="bi bi-journal-text me-1"></i>${escapeHtml(medicineNotes)}</div>` : ''}
                        <input type="hidden" name="variant_id[]" value="${selectedVariantId}">
                        <input type="hidden" name="item_id[]" value="">
                        <input type="hidden" name="medicine_notes" value="${escapeAttr(medicineNotes)}">
                    </td>
                    <td class="text-center">${m}<input type="hidden" name="morning" value="${m}"></td>
                    <td class="text-center">${a}<input type="hidden" name="afternoon" value="${a}"></td>
                    <td class="text-center">${e}<input type="hidden" name="evening" value="${e}"></td>
                    <td class="text-center">${n}<input type="hidden" name="night" value="${n}"></td>
                    <td>
                        <span class="badge ${mealBadge}">${mealLabel}</span>
                        <input type="hidden" name="meal" value="${meal}">
                    </td>
                    <td class="text-center">${days} Days<input type="hidden" name="days" value="${days}"></td>
                    <td class="text-center">
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
                    </td>
                    <td class="text-center">
                        <span class="badge bg-light text-muted rounded-pill">
                            <i class="bi bi-clock me-1"></i>Pending
                        </span>
                    </td>
                    <td class="text-center">
                        <button type="button" class="btn btn-link text-danger p-0" onclick="removeMedicineRow(this)">
                            <i class="bi bi-trash3 fs-5"></i>
                        </button>
                    </td>
                </tr>`;

    document.getElementById('medicineList').insertAdjacentHTML('beforeend', row);
    document.getElementById('emptyMessage').style.display = 'none';
    currentPage = Math.max(1, Math.ceil(document.getElementById('medicineList').children.length / rowsPerPage));
    updateCounts();

    // Show success toast
    showToast(`${selectedMedicineName} added successfully!`, 'success', 2000);

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
    updateCounts();
    if (!document.getElementById('medicineList').children.length) {
        document.getElementById('emptyMessage').style.display = 'block';
    }
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
