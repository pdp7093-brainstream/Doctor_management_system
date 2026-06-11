
    const searchInput = document.getElementById('search');
    const dateInput = document.getElementById('billDate');
    const statusInput = document.getElementById('billStatus');
    const clearBtn = document.getElementById('clearBtn');
    let debounceTimer;

    function fetchArchivedBills(page = 1) {
        const params = new URLSearchParams({
            search: searchInput.value,
            bill_date: dateInput.value,
            status: statusInput.value,
            page: page,
        });

        fetch(`/reports/archived-bills/?${params.toString()}`, {
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
                if (page) fetchArchivedBills(page);
            });
        });
    }

    function debounce(fn, delay = 350) {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(fn, delay);
    }

    searchInput.addEventListener('input', () => debounce(() => fetchArchivedBills(1)));
    dateInput.addEventListener('change', () => fetchArchivedBills(1));
    statusInput.addEventListener('change', () => fetchArchivedBills(1));
    clearBtn.addEventListener('click', () => {
        searchInput.value = '';
        dateInput.value = '';
        statusInput.value = 'all';
        fetchArchivedBills(1);
    });

    bindPaginationLinks();

    document.addEventListener('click', function (e) {
        const btn = e.target.closest('.restore-btn');
        if (!btn) return;

        e.preventDefault();
        const form = btn.closest('form');

        Swal.fire({
            title: 'Restore bill?',
            text: 'This bill will return to active billing records.',
            icon: 'question',
            showCancelButton: true,
            confirmButtonColor: '#198754',
            cancelButtonColor: '#6c757d',
            confirmButtonText: 'Yes, restore it'
        }).then((result) => {
            if (result.isConfirmed) form.submit();
        });
    });
