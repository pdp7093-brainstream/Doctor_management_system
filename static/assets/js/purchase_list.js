
const searchInput = document.getElementById('purchaseSearch');
const dateInput = document.getElementById('purchaseDate');
const statusInput = document.getElementById('purchaseStatus');
const clearBtn = document.getElementById('clearBtn');
let debounceTimer;

function fetchPurchases(page = 1) {
    const params = new URLSearchParams({
        search: searchInput.value,
        purchase_date: dateInput.value,
        status: statusInput.value,
        page: page,
    });

    fetch(`/medicine/purchases/?${params.toString()}`, {
        headers: { 'x-requested-with': 'XMLHttpRequest' }
    })
        .then(res => res.text())
        .then(html => {
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, 'text/html');

            const newStats = doc.querySelector('#statsContainer');
            const oldStats = document.querySelector('#statsContainer');
            if (newStats && oldStats) oldStats.replaceWith(newStats);

            const newTbody = doc.querySelector('#tableBody');
            const oldTbody = document.querySelector('#tableBody');
            if (newTbody && oldTbody) oldTbody.replaceWith(newTbody);

            const newPagination = doc.querySelector('#paginationWrapper');
            const oldPagination = document.querySelector('#paginationWrapper');
            if (newPagination && oldPagination) {
                oldPagination.replaceWith(newPagination);
            } else if (newPagination) {
                document.getElementById('paginationContainer').appendChild(newPagination);
            }

            bindPaginationLinks();
        })
        .catch(err => console.error('Fetch error:', err));
}

function bindPaginationLinks() {
    document.querySelectorAll('.pagination-link').forEach(link => {
        link.addEventListener('click', function (e) {
            e.preventDefault();
            fetchPurchases(parseInt(this.getAttribute('data-page')));
        });
    });
}

function debounce(fn, delay = 350) {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(fn, delay);
}

searchInput.addEventListener('input', () => debounce(() => fetchPurchases(1)));
dateInput.addEventListener('change', () => fetchPurchases(1));
statusInput.addEventListener('change', () => fetchPurchases(1));

clearBtn.addEventListener('click', function () {
    searchInput.value = '';
    dateInput.value = '';
    statusInput.value = 'all';
    fetchPurchases(1);
});

function bindDeleteButtons() {
    document.querySelectorAll('.deletePurchaseForm').forEach(form => {

        form.addEventListener('submit', function (e) {
            e.preventDefault();

            Swal.fire({
                title: 'Delete Purchase?',
                text: "This action cannot be undone.",
                icon: 'warning',
                showCancelButton: true,
                confirmButtonColor: '#dc3545',
                cancelButtonColor: '#6c757d',
                confirmButtonText: 'Yes, Delete',
                cancelButtonText: 'Cancel',
                borderRadius: '12px'
            }).then((result) => {

                if (result.isConfirmed) {
                    form.submit();
                }

            });
        });

    });
}

bindPaginationLinks();
bindDeleteButtons();



function bindDeleteButtons() {

    document.querySelectorAll('.deletePurchaseForm').forEach(form => {

        form.addEventListener('submit', function (e) {

            e.preventDefault();

            Swal.fire({
                title: 'Delete Purchase?',
                text: "This action cannot be undone.",
                icon: 'warning',
                showCancelButton: true,
                confirmButtonColor: '#dc3545',
                cancelButtonColor: '#6c757d',
                confirmButtonText: 'Yes, Delete',
                cancelButtonText: 'Cancel',
                borderRadius: '12px'
            }).then((result) => {

                if (result.isConfirmed) {
                    form.submit();
                }

            });

        });

    });

}

bindDeleteButtons();
