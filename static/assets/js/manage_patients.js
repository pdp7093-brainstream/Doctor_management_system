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

    const patientsTable = document.querySelector('.patients-table');

    function openCaseNoEditor(button) {
        const cell = button.closest('.case-no-cell');
        if (!cell || cell.querySelector('.case-no-editor')) return;

        const currentValue = button.querySelector('.case-no-value')?.textContent.trim() || '';
        const input = document.createElement('input');
        input.type = 'text';
        input.className = 'form-control form-control-sm';
        input.value = currentValue === '—' ? '' : currentValue;
        input.setAttribute('aria-label', 'Case No.');

        const editor = document.createElement('div');
        editor.className = 'case-no-editor';
        editor.dataset.url = button.dataset.url;
        editor.appendChild(input);

        const controls = document.createElement('div');
        controls.className = 'case-no-editor-controls';
        const saveButton = document.createElement('button');
        saveButton.type = 'button';
        saveButton.className = 'btn btn-sm btn-success case-no-save';
        saveButton.setAttribute('aria-label', 'Save Case No.');
        saveButton.textContent = '✓';
        const cancelButton = document.createElement('button');
        cancelButton.type = 'button';
        cancelButton.className = 'btn btn-sm btn-outline-secondary case-no-cancel';
        cancelButton.setAttribute('aria-label', 'Cancel edit');
        cancelButton.textContent = '×';
        controls.append(saveButton, cancelButton);
        editor.appendChild(controls);

        const error = document.createElement('div');
        error.className = 'case-no-error text-danger small mt-1';
        error.setAttribute('role', 'alert');
        editor.appendChild(error);

        button.hidden = true;
        cell.appendChild(editor);
        input.focus();
        input.select();
    }

    function cancelCaseNoEdit(editor) {
        const cell = editor.closest('.case-no-cell');
        if (!cell) return;
        editor.remove();
        const display = cell.querySelector('.case-no-edit');
        if (display) display.hidden = false;
    }

    async function saveCaseNo(editor) {
        if (!editor || editor.dataset.saving === 'true') return;
        const input = editor.querySelector('input');
        const buttons = editor.querySelectorAll('button');
        const error = editor.querySelector('.case-no-error');
        const caseNo = input.value.trim();
        error.textContent = '';
        if (!caseNo) {
            error.textContent = 'Case No. is required.';
            input.focus();
            return;
        }

        editor.dataset.saving = 'true';
        input.disabled = true;
        buttons.forEach(button => { button.disabled = true; });
        const csrfToken = document.querySelector('[name="csrfmiddlewaretoken"]')?.value || '';
        try {
            const response = await fetch(editor.dataset.url, {
                method: 'POST',
                credentials: 'same-origin',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
                    'X-CSRFToken': csrfToken,
                    'X-Requested-With': 'XMLHttpRequest',
                },
                body: new URLSearchParams({ case_no: caseNo }),
            });
            const result = await response.json();
            if (!response.ok || !result.ok) {
                error.textContent = result.error || 'Could not save Case No.';
                editor.dataset.saving = 'false';
                input.disabled = false;
                buttons.forEach(button => { button.disabled = false; });
                input.focus();
                return;
            }

            const cell = editor.closest('.case-no-cell');
            const display = cell?.querySelector('.case-no-edit');
            const value = display?.querySelector('.case-no-value');
            if (value) value.textContent = result.case_no;
            editor.remove();
            if (display) {
                display.hidden = false;
                const saved = document.createElement('i');
                saved.className = 'bi bi-check-circle-fill text-success case-no-saved';
                saved.setAttribute('aria-label', 'Saved');
                display.appendChild(saved);
                window.setTimeout(() => saved.remove(), 1400);
            }
        } catch (fetchError) {
            error.textContent = 'Could not save Case No. Please try again.';
            editor.dataset.saving = 'false';
            input.disabled = false;
            buttons.forEach(button => { button.disabled = false; });
            input.focus();
        }
    }

    if (patientsTable) {
        patientsTable.addEventListener('click', event => {
            const editButton = event.target.closest('.case-no-edit');
            if (editButton) {
                openCaseNoEditor(editButton);
                return;
            }

            const saveButton = event.target.closest('.case-no-save');
            if (saveButton) {
                saveCaseNo(saveButton.closest('.case-no-editor'));
                return;
            }

            const cancelButton = event.target.closest('.case-no-cancel');
            if (cancelButton) {
                cancelCaseNoEdit(cancelButton.closest('.case-no-editor'));
                return;
            }

            const cell = event.target.closest('.case-no-cell');
            if (cell && !event.target.closest('.case-no-editor')) {
                const display = cell.querySelector('.case-no-edit');
                if (display) openCaseNoEditor(display);
            }
        });

        patientsTable.addEventListener('keydown', event => {
            const input = event.target.closest('.case-no-editor input');
            if (!input) return;
            if (event.key === 'Enter') {
                event.preventDefault();
                saveCaseNo(input.closest('.case-no-editor'));
            } else if (event.key === 'Escape') {
                event.preventDefault();
                cancelCaseNoEdit(input.closest('.case-no-editor'));
            }
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
            const allLettersRadio = document.getElementById('letter-all');
            if (allLettersRadio) allLettersRadio.checked = true;
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
