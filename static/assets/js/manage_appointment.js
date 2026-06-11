
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
