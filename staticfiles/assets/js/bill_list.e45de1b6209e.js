
const searchInput = document.getElementById('search');
const dateInput = document.getElementById('billDate');
const monthInput = document.getElementById('billMonth');
const statusInput = document.getElementById('paymentStatus');
const clearBtn = document.getElementById('clearBtn');

let debounceTimer;
let paginationState = {};

function fetchBills(paramName = null, paramValue = null) {
    if (paramName) {
        paginationState[paramName] = paramValue;
    } else {
        // Reset pagination state when filters change
        paginationState = {};
    }

    const params = new URLSearchParams({
        search: searchInput.value,
        bill_date: dateInput.value,
        bill_month: monthInput.value,
        payment_status: statusInput.value,
        ...paginationState
    });

    fetch(`/billing/?${params.toString()}`, {
        headers: { 'x-requested-with': 'XMLHttpRequest' }
    })
        .then(res => res.text())
        .then(html => {
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, 'text/html');

            const newContainer = doc.querySelector('#monthsContainer');
            const oldContainer = document.querySelector('#monthsContainer');

            if (newContainer && oldContainer) {
                oldContainer.replaceWith(newContainer);
                const selectAll = document.getElementById('selectAllBills');
                if (selectAll) selectAll.checked = false;
                if (typeof updateBulkDeleteBtn === 'function') updateBulkDeleteBtn();
                bindPaginationLinks();
            }
        })
        .catch(err => console.error('Fetch error:', err));
}

function bindPaginationLinks() {
    document.querySelectorAll('.pagination-link').forEach(link => {
        link.addEventListener('click', function (e) {
            e.preventDefault();
            if (!this.parentElement.classList.contains('disabled')) {
                const paramName = this.getAttribute('data-param-name') || 'page';
                const pageNum = parseInt(this.getAttribute('data-page'));
                fetchBills(paramName, pageNum);
            }
        });
    });
}

function debounce(fn, delay = 350) {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(fn, delay);
}

searchInput.addEventListener('input', () => debounce(() => fetchBills(1)));
dateInput.addEventListener('change', () => fetchBills(1));
monthInput.addEventListener('input', () => debounce(() => fetchBills(1)));
monthInput.addEventListener('change', () => fetchBills(1));
statusInput.addEventListener('change', () => fetchBills(1));

clearBtn.addEventListener('click', () => {
    searchInput.value = '';
    dateInput.value = '';
    monthInput.value = '';
    statusInput.value = 'all';
    fetchBills(1);
});

bindPaginationLinks();

// SweetAlert for Delete Buttons using Event Delegation
document.addEventListener('click', function (e) {
    const btn = e.target.closest('.delete-btn');
    if (btn) {
        e.preventDefault();
        const form = btn.closest('form');
        Swal.fire({
            title: 'Are you sure?',
            text: "This bill and its associated appointment will be permanently deleted and will not appear in archived records.",
            icon: 'warning',
            showCancelButton: true,
            confirmButtonColor: '#d33',
            cancelButtonColor: '#3085d6',
            confirmButtonText: 'Yes, delete it!'
        }).then((result) => {
            if (result.isConfirmed) {
                form.submit();
            }
        });
    }
});

// Live search for patient/name in Add Bill modal
(function () {
    const searchInput = document.getElementById('patientSearch');
    const suggestions = document.getElementById('patientSuggestions');
    const patientIdInput = document.getElementById('patient_id');
    const familyMemberIdInput = document.getElementById('family_member_id');
    const phoneInput = document.getElementById('patientPhone');

    let timer;

    function clearSuggestions() {
        suggestions.innerHTML = '';
        suggestions.style.display = 'none';
    }

    function renderResults(items) {
        suggestions.innerHTML = '';
        if (!items || items.length === 0) {
            clearSuggestions();
            return;
        }
        items.forEach(item => {
            const el = document.createElement('button');
            el.type = 'button';
            el.className = 'list-group-item list-group-item-action';
            el.textContent = item.display;
            el.dataset.type = item.type; // patient or family
            el.dataset.id = item.id;
            el.dataset.name = item.name || '';
            el.dataset.phone = item.phone || '';
            el.addEventListener('click', () => {
                searchInput.value = el.dataset.name || el.textContent;
                phoneInput.value = el.dataset.phone || '';
                if (el.dataset.type === 'family') {
                    familyMemberIdInput.value = el.dataset.id;
                    patientIdInput.value = '';
                } else {
                    patientIdInput.value = el.dataset.id;
                    familyMemberIdInput.value = '';
                }
                clearSuggestions();
            });
            suggestions.appendChild(el);
        });
        suggestions.style.display = 'block';
    }

    function fetchSearch(q) {
        if (!q || q.length < 2) { clearSuggestions(); return; }
        fetch(`/appointment/search-patients/?q=${encodeURIComponent(q)}`)
            .then(r => r.json())
            .then(data => {
                const results = data.results || [];
                // normalize to {id,type,display,name,phone}
                const items = results.map(it => {
                    let parsedType = 'patient';
                    let parsedId = it.id;
                    if (typeof it.id === 'string') {
                        if (it.id.startsWith('patient_')) {
                            parsedType = 'patient';
                            parsedId = it.id.split('_')[1];
                        } else if (it.id.startsWith('family_')) {
                            parsedType = 'family';
                            parsedId = it.id.split('_')[1];
                        }
                    }
                    return {
                        id: parsedId,
                        type: parsedType,
                        display: it.display || it.name || it.phone || '',
                        name: it.name || '',
                        phone: it.phone || ''
                    };
                });
                renderResults(items);
            })
            .catch(err => { console.error('search error', err); clearSuggestions(); });
    }

    searchInput && searchInput.addEventListener('input', function () {
        clearTimeout(timer);
        timer = setTimeout(() => fetchSearch(this.value.trim()), 250);
        // clear selected ids when typing
        patientIdInput.value = '';
        familyMemberIdInput.value = '';
    });

    // hide suggestions when clicking outside
    document.addEventListener('click', function (e) {
        if (!e.target.closest('#patientSuggestions') && !e.target.closest('#patientSearch')) {
            clearSuggestions();
        }
    });
})();

// Consultation mode buttons handler in Add Bill modal — behave like radio buttons
(function () {
    const modeButtons = Array.from(document.querySelectorAll('.btn-mode'));
    const hiddenInput = document.getElementById('consultation_type');
    const modalEl = document.getElementById('addBillModal');
    if (!modeButtons.length || !hiddenInput) return;

    function setActiveButton(btn) {
        modeButtons.forEach(b => {
            b.classList.toggle('active', b === btn);
            b.setAttribute('aria-pressed', b === btn ? 'true' : 'false');
        });
        hiddenInput.value = btn ? (btn.dataset.value || 'in_person') : 'in_person';
    }

    // initialize based on hidden input value
    const initialVal = (hiddenInput.value || 'in_person');
    const initialBtn = modeButtons.find(b => b.dataset.value === initialVal) || modeButtons[0];
    setActiveButton(initialBtn);

    // clicks
    modeButtons.forEach(btn => {
        btn.addEventListener('click', function (e) {
            setActiveButton(this);
        });
        // keyboard activation (Space / Enter)
        btn.addEventListener('keydown', function (e) {
            if (e.key === ' ' || e.key === 'Enter') {
                e.preventDefault();
                setActiveButton(this);
            }
        });
    });

    // when modal opens, ensure UI reflects hidden input (in case value changed programmatically)
    if (modalEl) {
        modalEl.addEventListener('shown.bs.modal', function () {
            const val = (hiddenInput.value || 'in_person');
            const btn = modeButtons.find(b => b.dataset.value === val) || modeButtons[0];
            setActiveButton(btn);
        });
    }
})();

// remove item-related handlers (modal simplified)

// Bulk Delete Logic
function updateBulkDeleteBtn() {
    const checkboxes = document.querySelectorAll('.bill-checkbox:checked');
    const btn = document.getElementById('bulkDeleteBtn');
    const countSpan = document.getElementById('selectedCount');
    if (!btn) return;
    if (checkboxes.length > 0) {
        btn.classList.remove('d-none');
        if (countSpan) countSpan.textContent = checkboxes.length;
    } else {
        btn.classList.add('d-none');
        if (countSpan) countSpan.textContent = '0';
    }
}

document.addEventListener('change', function(e) {
    if (e.target.id === 'selectAllBills') {
        const isChecked = e.target.checked;
        document.querySelectorAll('.bill-checkbox').forEach(cb => {
            cb.checked = isChecked;
        });
        updateBulkDeleteBtn();
    } else if (e.target.classList.contains('bill-checkbox')) {
        updateBulkDeleteBtn();
        const allCheckboxes = document.querySelectorAll('.bill-checkbox');
        const allChecked = document.querySelectorAll('.bill-checkbox:checked');
        const selectAll = document.getElementById('selectAllBills');
        if (selectAll) {
            selectAll.checked = allCheckboxes.length > 0 && allCheckboxes.length === allChecked.length;
        }
    }
});

function bulkDeleteBills() {
    const checkboxes = document.querySelectorAll('.bill-checkbox:checked');
    const ids = Array.from(checkboxes).map(cb => cb.value);
    
    if (ids.length === 0) return;
    
    Swal.fire({
        title: 'Are you sure?',
        text: `You are about to permanently delete ${ids.length} bill(s) and their associated appointments.`,
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#d33',
        cancelButtonColor: '#3085d6',
        confirmButtonText: 'Yes, delete them!'
    }).then((result) => {
        if (result.isConfirmed) {
            fetch('/billing/bulk-delete/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken')
                },
                body: JSON.stringify({ bill_ids: ids })
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    Swal.fire('Deleted!', data.message, 'success').then(() => {
                        window.location.reload();
                    });
                } else {
                    Swal.fire('Error', data.error || 'Failed to delete bills.', 'error');
                }
            })
            .catch(err => {
                console.error(err);
                Swal.fire('Error', 'An unexpected error occurred.', 'error');
            });
        }
    });
}

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}
