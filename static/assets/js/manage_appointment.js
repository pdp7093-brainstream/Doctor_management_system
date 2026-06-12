
const searchInput = document.getElementById('search');
const dateInput = document.getElementById('appointmentDate');
const statusInput = document.getElementById('appointmentStatus');
const clearBtn = document.getElementById('clearBtn');
let debounceTimer;

function fetchAppointments(page = 1) {
    const params = new URLSearchParams({
        search: searchInput.value,
        appointment_date: dateInput.value,
        status: statusInput.value,
        page: page,
    });

    fetch(`/appointment/manage_appointments/?${params.toString()}`, {
        headers: { 'x-requested-with': 'XMLHttpRequest' }
    })
        .then(res => res.text())
        .then(html => {
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, 'text/html');

            const newTbody = doc.querySelector('#tableBody');
            const oldTbody = document.querySelector('#tableBody');
            if (newTbody && oldTbody) oldTbody.replaceWith(newTbody);

            const newPag = doc.querySelector('#paginationWrapper');
            const oldPag = document.querySelector('#paginationWrapper');
            if (newPag && oldPag) oldPag.replaceWith(newPag);
            else if (newPag) document.getElementById('paginationContainer').appendChild(newPag);

            // Uncheck select all when page changes
            const selectAll = document.getElementById('selectAllAppointments');
            if (selectAll) selectAll.checked = false;
            updateBulkDeleteBtn();

            bindPaginationLinks();
        })
        .catch(err => console.error('Fetch error:', err));
}

function bindPaginationLinks() {
    document.querySelectorAll('.pagination-link').forEach(link => {
        link.addEventListener('click', function (e) {
            e.preventDefault();
            fetchAppointments(parseInt(this.getAttribute('data-page')));
        });
    });
}

function debounce(fn, delay = 350) {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(fn, delay);
}

searchInput.addEventListener('input', () => debounce(() => fetchAppointments(1)));
dateInput.addEventListener('change', () => fetchAppointments(1));
statusInput.addEventListener('change', () => fetchAppointments(1));
clearBtn.addEventListener('click', () => {
    searchInput.value = '';
    dateInput.value = '';
    statusInput.value = 'all';
    fetchAppointments(1);
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
            text: "This appointment will be permanently deleted and will not appear in archived records.",
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

// Bulk Delete Logic
function updateBulkDeleteBtn() {
    const checkboxes = document.querySelectorAll('.appointment-checkbox:checked');
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
    if (e.target.id === 'selectAllAppointments') {
        const isChecked = e.target.checked;
        document.querySelectorAll('.appointment-checkbox').forEach(cb => {
            cb.checked = isChecked;
        });
        updateBulkDeleteBtn();
    } else if (e.target.classList.contains('appointment-checkbox')) {
        updateBulkDeleteBtn();
        const allCheckboxes = document.querySelectorAll('.appointment-checkbox');
        const allChecked = document.querySelectorAll('.appointment-checkbox:checked');
        const selectAll = document.getElementById('selectAllAppointments');
        if (selectAll) {
            selectAll.checked = allCheckboxes.length > 0 && allCheckboxes.length === allChecked.length;
        }
    }
});

function bulkDeleteAppointments() {
    const checkboxes = document.querySelectorAll('.appointment-checkbox:checked');
    const ids = Array.from(checkboxes).map(cb => cb.value);
    
    if (ids.length === 0) return;
    
    Swal.fire({
        title: 'Are you sure?',
        text: `You are about to permanently delete ${ids.length} appointment(s).`,
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#d33',
        cancelButtonColor: '#3085d6',
        confirmButtonText: 'Yes, delete them!'
    }).then((result) => {
        if (result.isConfirmed) {
            fetch('/appointment/bulk-delete-appointments/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken')
                },
                body: JSON.stringify({ appointment_ids: ids })
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    Swal.fire('Deleted!', data.message, 'success').then(() => {
                        window.location.reload();
                    });
                } else {
                    Swal.fire('Error', data.error || 'Failed to delete appointments.', 'error');
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
