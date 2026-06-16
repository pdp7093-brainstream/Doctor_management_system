
    const searchInput = document.getElementById('searchInput');
    let debounceTimer;

    function bindDeleteButtons() {
        document.querySelectorAll('.delete-btn').forEach(button => {
            button.onclick = function () {
            const form = this.closest('form');
            const type = this.dataset.type;

            Swal.fire({
                title: 'Delete Confirmation',
                text: `Are you sure you want to delete this ${type}?`,
                icon: 'warning',
                showCancelButton: true,
                confirmButtonColor: '#007aff',
                cancelButtonColor: '#dc3545',
                confirmButtonText: 'Yes, Delete',
                cancelButtonText: 'Cancel',
                reverseButtons: true,
                backdrop: 'rgba(0,0,0,0.45)',
                customClass: {
                    popup: 'rounded-4 shadow-lg',
                    confirmButton: 'px-4 py-2',
                    cancelButton: 'px-4 py-2'
                }
            }).then((result) => {
                if (result.isConfirmed) {
                    Swal.fire({
                        title: 'Deleting...',
                        html: 'Please wait',
                        allowOutsideClick: false,
                        showConfirmButton: false,
                        didOpen: () => { Swal.showLoading(); }
                    });
                    setTimeout(() => { form.submit(); }, 1200);
                }
            });
            };
        });
    }

    function fetchPatients(page = 1) {
        const params = new URLSearchParams({
            search: searchInput.value,
            page: page,
        });

        // Use the same route as the server view for manage patients
        fetch(`/doctor/manage-patients/?${params.toString()}`, {
            headers: { 'x-requested-with': 'XMLHttpRequest' }
        })
        .then(res => res.text())
        .then(html => {
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, 'text/html');

            const newTbody = doc.querySelector('#tableBody');
            const oldTbody = document.querySelector('#tableBody');
            if (newTbody && oldTbody) oldTbody.replaceWith(newTbody);

            const newPagination = doc.querySelector('#paginationWrapper');
            const oldPagination = document.querySelector('#paginationWrapper');
            if (newPagination && oldPagination) oldPagination.replaceWith(newPagination);
            else if (newPagination) document.getElementById('paginationContainer').appendChild(newPagination);
            else if (oldPagination) oldPagination.remove();

            bindPaginationLinks();
            bindDeleteButtons();
        })
        .catch(err => console.error('Fetch error:', err));
    }

    function bindPaginationLinks() {
        document.querySelectorAll('.pagination-link').forEach(link => {
            link.onclick = function (e) {
                e.preventDefault();
                fetchPatients(parseInt(this.getAttribute('data-page')));
            };
        });
    }

    function debounce(fn, delay = 350) {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(fn, delay);
    }

    searchInput.addEventListener('input', () => debounce(() => fetchPatients(1)));

    bindPaginationLinks();
    bindDeleteButtons();
