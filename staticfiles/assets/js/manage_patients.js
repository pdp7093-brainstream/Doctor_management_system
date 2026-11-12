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
                    ...window.swalSharedCustomClass,
                    popup: 'rounded-4 shadow-lg',
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
        const params = new URLSearchParams(window.location.search);
        if (searchInput) {
            const val = searchInput.value.trim();
            if (val) {
                params.set('search', val);
            } else {
                params.delete('search');
            }
        }
        params.set('page', page);

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

            const newCount = doc.querySelector('.dc-count');
            const oldCount = document.querySelector('.dc-count');
            if (newCount && oldCount) oldCount.textContent = newCount.textContent;

            const tableWrap = document.querySelector('.dc-table-wrap');
            const emptyState = document.querySelector('.dc-empty');
            const newTableWrap = doc.querySelector('.dc-table-wrap');
            const newEmptyState = doc.querySelector('.dc-empty');
            if (tableWrap && newTableWrap) tableWrap.className = newTableWrap.className;
            if (newEmptyState) {
                if (emptyState) emptyState.replaceWith(newEmptyState);
                else if (tableWrap) tableWrap.insertAdjacentElement('afterend', newEmptyState);
            } else if (emptyState) {
                emptyState.remove();
            }

            window.history.replaceState({}, '', `?${params.toString()}`);

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

    if (searchInput) {
        searchInput.addEventListener('input', () => debounce(() => fetchPatients(1)));
    }

    const filterToggleBtn = document.getElementById('filterToggleBtn');
    const filterPanel = document.getElementById('filterPanel');
    const closeFilterPanelBtn = document.getElementById('closeFilterPanel');
    const filterForm = document.getElementById('medicineFilterForm') || document.getElementById('patientFilterForm');
    const filterResetBtn = document.getElementById('filterResetBtn');

    function closeFilterPanel() {
        if (!filterPanel) return;
        filterPanel.classList.add('d-none');
        if (filterToggleBtn) filterToggleBtn.setAttribute('aria-expanded', 'false');
    }

    if (filterToggleBtn && filterPanel) {
        filterToggleBtn.addEventListener('click', event => {
            event.stopPropagation();
            const isOpen = filterToggleBtn.getAttribute('aria-expanded') === 'true';
            filterPanel.classList.toggle('d-none', isOpen);
            filterToggleBtn.setAttribute('aria-expanded', String(!isOpen));
        });
        if (closeFilterPanelBtn) closeFilterPanelBtn.addEventListener('click', closeFilterPanel);
        filterPanel.addEventListener('click', event => event.stopPropagation());
        document.addEventListener('click', event => {
            if (!filterPanel.classList.contains('d-none') && !filterPanel.contains(event.target) && !filterToggleBtn.contains(event.target)) {
                closeFilterPanel();
            }
        });
        document.addEventListener('keydown', event => {
            if (event.key === 'Escape' && !filterPanel.classList.contains('d-none')) closeFilterPanel();
        });
    }

    if (filterResetBtn && filterForm) {
        filterResetBtn.addEventListener('click', () => {
            filterForm.querySelectorAll('select').forEach(select => { select.value = ''; });
            filterForm.requestSubmit();
        });
    }

    if (filterForm) {
        filterForm.addEventListener('submit', () => {
            if (searchInput) {
                let hiddenSearch = filterForm.querySelector('input[name="search"]');
                const val = searchInput.value.trim();
                if (val) {
                    if (!hiddenSearch) {
                        hiddenSearch = document.createElement('input');
                        hiddenSearch.type = 'hidden';
                        hiddenSearch.name = 'search';
                        filterForm.appendChild(hiddenSearch);
                    }
                    hiddenSearch.value = val;
                } else if (hiddenSearch) {
                    hiddenSearch.remove();
                }
            }
        });
    }

    bindPaginationLinks();
    bindDeleteButtons();
