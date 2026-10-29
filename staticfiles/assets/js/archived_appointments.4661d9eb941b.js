
const searchInput = document.getElementById('search');
const dateInput = document.getElementById('appointmentDate');
const statusInput = document.getElementById('appointmentStatus');
const clearBtn = document.getElementById('clearBtn');
let debounceTimer;

function fetchArchivedAppointments(page = 1) {
    const params = new URLSearchParams({
        search: searchInput.value,
        appointment_date: dateInput.value,
        status: statusInput.value,
        page: page,
    });

    fetch(`/reports/archived-appointments/?${params.toString()}`, {
        headers: { 'x-requested-with': 'XMLHttpRequest' }
    })
        .then(res => res.text())
        .then(html => {
            const doc = new DOMParser().parseFromString(html, 'text/html');
            const newTbody = doc.querySelector('#tableBody');
            const oldTbody = document.querySelector('#tableBody');
            if (newTbody && oldTbody) oldTbody.replaceWith(newTbody);

            const newPagination = doc.querySelector('#paginationWrapper');
            const oldPagination = document.querySelector('#paginationWrapper');
            if (newPagination && oldPagination) oldPagination.replaceWith(newPagination);
            else if (newPagination) document.getElementById('paginationContainer').appendChild(newPagination);
            else if (oldPagination) oldPagination.remove();

            bindPaginationLinks();
        })
        .catch(err => console.error('Fetch error:', err));
}

function bindPaginationLinks() {
    document.querySelectorAll('.pagination-link').forEach(link => {
        link.addEventListener('click', function (e) {
            e.preventDefault();
            const page = parseInt(this.getAttribute('data-page'));
            if (page) fetchArchivedAppointments(page);
        });
    });
}

function debounce(fn, delay = 350) {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(fn, delay);
}

searchInput.addEventListener('input', () => debounce(() => fetchArchivedAppointments(1)));
dateInput.addEventListener('change', () => fetchArchivedAppointments(1));
statusInput.addEventListener('change', () => fetchArchivedAppointments(1));
clearBtn.addEventListener('click', () => {
    searchInput.value = '';
    dateInput.value = '';
    statusInput.value = 'all';
    fetchArchivedAppointments(1);
});

bindPaginationLinks();

document.addEventListener('click', function (e) {
    const btn = e.target.closest('.restore-btn');
    if (!btn) return;

    e.preventDefault();
    const form = btn.closest('form');

    Swal.fire({
        title: 'Restore appointment?',
        text: 'This appointment will return to active appointment records.',
        icon: 'question',
        showCancelButton: true,
        confirmButtonColor: '#198754',
        cancelButtonColor: '#6c757d',
        confirmButtonText: 'Yes, restore it'
    }).then((result) => {
        if (result.isConfirmed) {
            form.submit();
        }
    });
});
