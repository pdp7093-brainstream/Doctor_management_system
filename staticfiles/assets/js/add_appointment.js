

    // Set minimum date to today
    function setMinDate() {
        const today = new Date();
        const yyyy = today.getFullYear();
        const mm   = String(today.getMonth() + 1).padStart(2, '0');
        const dd   = String(today.getDate()).padStart(2, '0');
        document.getElementById('id_appointment_date').setAttribute('min', `${yyyy}-${mm}-${dd}`);
    }

    // Bootstrap form validation
    function setupFormValidation() {
        const form = document.querySelector('form');
        if (form) {
            form.addEventListener('submit', function (e) {
                if (!form.checkValidity()) {
                    e.preventDefault();
                    e.stopPropagation();
                }
                form.classList.add('was-validated');
            });
        }
    }

    // Patient Search Functionality
    const patientSearch = document.getElementById('patientSearch');
    const searchResults = document.getElementById('searchResults');
    const patientSelection = document.getElementById('patient_selection');
    const selectedPatientDisplay = document.getElementById('selectedPatientDisplay');
    const selectedPatientName = document.getElementById('selectedPatientName');
    const clearBtn = document.getElementById('clearBtn');
    const clearSelectionBtn = document.getElementById('clearSelectionBtn');
    const submitBtn = document.getElementById('submitBtn');
    const searchError = document.getElementById('searchError');

    let searchTimeout;

    patientSearch.addEventListener('input', async function() {
        const query = this.value.trim();
        clearTimeout(searchTimeout);
        searchError.style.display = 'none';

        // Show clear button if has input
        if (query.length > 0) {
            clearBtn.style.display = 'block';
        } else {
            clearBtn.style.display = 'none';
        }

        if (query.length < 2) {
            searchResults.style.display = 'none';
            return;
        }

        // Debounce search
        searchTimeout = setTimeout(async () => {
            try {
                const response = await fetch(`/appointment/search-patients/?q=${encodeURIComponent(query)}`);
                const data = await response.json();

                if (data.error) {
                    searchError.textContent = data.error;
                    searchError.style.display = 'block';
                    searchResults.style.display = 'none';
                    return;
                }

                if (data.results && data.results.length > 0) {
                    searchResults.innerHTML = data.results.map(result => `
                        <div class="search-result-item" data-id="${result.id}">
                            <div class="search-result-label">${result.type}</div>
                            <div class="search-result-name">${result.name}</div>
                            <div class="search-result-phone">📱 ${result.phone}</div>
                        </div>
                    `).join('');

                    searchResults.style.display = 'block';

                    // Add click listeners
                    document.querySelectorAll('.search-result-item').forEach(item => {
                        item.addEventListener('click', function() {
                            const id = this.dataset.id;
                            const name = this.querySelector('.search-result-name').textContent;
                            const type = this.querySelector('.search-result-label').textContent;

                            patientSelection.value = id;
                            patientSearch.value = `${name} (${type})`;
                            selectedPatientName.textContent = `${name} (${type})`;
                            selectedPatientDisplay.style.display = 'flex';
                            searchResults.style.display = 'none';
                            submitBtn.disabled = false;
                            clearBtn.style.display = 'none';
                        });
                    });
                } else {
                    searchResults.innerHTML = '<div class="search-result-item" style="text-align:center; color:#999; padding:20px;">No results found</div>';
                    searchResults.style.display = 'block';
                }
            } catch (error) {
                console.error('Search error:', error);
                searchError.textContent = 'Error searching patients. Please try again.';
                searchError.style.display = 'block';
                searchResults.style.display = 'none';
            }
        }, 500); // Debounce 500ms
    });

    // Clear button - just clear search field
    clearBtn.addEventListener('click', function(e) {
        e.preventDefault();
        patientSearch.value = '';
        clearBtn.style.display = 'none';
        searchResults.style.display = 'none';
    });

    // Clear selection button - reset everything
    clearSelectionBtn.addEventListener('click', function(e) {
        e.preventDefault();
        patientSelection.value = '';
        patientSearch.value = '';
        selectedPatientDisplay.style.display = 'none';
        submitBtn.disabled = true;
        clearBtn.style.display = 'none';
        searchResults.style.display = 'none';
        searchError.style.display = 'none';
    });

    // Close dropdown when clicking outside
    document.addEventListener('click', function(e) {
        if (!e.target.closest('#patientSearch') && !e.target.closest('#searchResults')) {
            searchResults.style.display = 'none';
        }
    });

    // Fetch available time slots on date change
    document.getElementById('id_appointment_date').addEventListener('change', function () {
        const date   = this.value;
        const select = document.getElementById('id_time_slot');
        select.innerHTML = '<option value="">-- Loading slots... --</option>';

        fetch(`/appointment/get-slots/?appointment_date=${date}`, { cache: 'no-store' })
            .then(res => res.json())
            .then(data => {
                if (data.slots && data.slots.length > 0) {
                    select.innerHTML = '<option value="">-- Select Time --</option>';
                    data.slots.forEach(slot => {
                        const option = document.createElement('option');
                        option.value       = slot;
                        option.textContent = slot;
                        select.appendChild(option);
                    });
                } else {
                    select.innerHTML = '<option value="">No slots available</option>';
                }
            })
            .catch(err => {
                console.error('Error fetching slots:', err);
                select.innerHTML = '<option value="">Error loading slots</option>';
            });
    });

    document.addEventListener('DOMContentLoaded', function () {
        setMinDate();
        setupFormValidation();
    });


    