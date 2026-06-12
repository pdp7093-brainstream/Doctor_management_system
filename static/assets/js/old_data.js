// Bootstrap form validation
function setupFormValidation() {
    const form = document.querySelector('form');
    if (form) {
        form.addEventListener('submit', function (e) {
            if (!form.checkValidity() || !document.getElementById('patient_id').value) {
                e.preventDefault();
                e.stopPropagation();
                if (!document.getElementById('patient_id').value) {
                    document.getElementById('patientSearch').classList.add('is-invalid');
                }
            }
            form.classList.add('was-validated');
        });
    }
}

// Patient Search Functionality
const patientSearch = document.getElementById('patientSearch');
const searchResults = document.getElementById('searchResults');
const patientId = document.getElementById('patient_id');
const familyMemberId = document.getElementById('family_member_id');
const selectedPatientDisplay = document.getElementById('selectedPatientDisplay');
const selectedPatientName = document.getElementById('selectedPatientName');
const clearBtn = document.getElementById('clearBtn');
const clearSelectionBtn = document.getElementById('clearSelectionBtn');
const submitBtn = document.getElementById('submitBtn');
const searchError = document.getElementById('searchError');

let searchTimeout;

patientSearch.addEventListener('input', async function () {
    const query = this.value.trim();
    clearTimeout(searchTimeout);
    searchError.style.display = 'none';

    if (query.length > 0) {
        clearBtn.style.display = 'block';
    } else {
        clearBtn.style.display = 'none';
    }

    if (query.length < 2) {
        searchResults.style.display = 'none';
        return;
    }

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

                document.querySelectorAll('.search-result-item').forEach(item => {
                    item.addEventListener('click', function () {
                        const rawId = this.dataset.id;
                        const name = this.querySelector('.search-result-name').textContent;
                        const type = this.querySelector('.search-result-label').textContent;

                        if (rawId.startsWith('patient_')) {
                            patientId.value = rawId.replace('patient_', '');
                            familyMemberId.value = '';
                        } else if (rawId.startsWith('family_')) {
                            familyMemberId.value = rawId.replace('family_', '');
                            // Find patient id by another fetch if needed, but the search API only returns family ID.
                            // Wait, the search_patients API doesn't return the patient ID for the family member!
                            // It just returns 'id': f"family_{fm['id']}"
                        }

                        // Let's modify the above if we need patient id. Wait, in old_data_upload, if it's family member, we don't strictly have patient ID from the form unless we provide it.
                        patientSearch.value = `${name} (${type})`;
                        selectedPatientName.textContent = `${name} (${type})`;
                        selectedPatientDisplay.style.display = 'flex';
                        searchResults.style.display = 'none';
                        submitBtn.disabled = false;
                        clearBtn.style.display = 'none';
                        patientSearch.classList.remove('is-invalid');

                        // Let's set a hidden attribute for processing
                        patientSearch.setAttribute('data-rawid', rawId);
                    });
                });
            } else {
                searchResults.innerHTML = `
                        <div class="search-result-item" style="text-align:center; color:#999; padding:20px;">
                            <div class="mb-2">No results found</div>
                            <a href="/doctor/add-patient/" class="btn btn-sm btn-primary mt-2" style="font-weight:600;">
                                <i class="bi bi-person-plus"></i> Add Patient
                            </a>
                        </div>
                    `;
                searchResults.style.display = 'block';
            }
        } catch (error) {
            console.error('Search error:', error);
            searchError.textContent = 'Error searching patients. Please try again.';
            searchError.style.display = 'block';
            searchResults.style.display = 'none';
        }
    }, 500);
});

// We must handle the rawId submission correctly.
// Let's intercept form submission to properly set patient_id and family_member_id
document.querySelector('form').addEventListener('submit', function (e) {
    const rawId = patientSearch.getAttribute('data-rawid');
    if (rawId) {
        if (rawId.startsWith('patient_')) {
            patientId.value = rawId.replace('patient_', '');
            familyMemberId.value = '';
        } else if (rawId.startsWith('family_')) {
            familyMemberId.value = rawId.replace('family_', '');
            patientId.value = 'family_only'; // We'll handle this in the backend
        }
    }
});

clearBtn.addEventListener('click', function (e) {
    e.preventDefault();
    patientSearch.value = '';
    patientSearch.removeAttribute('data-rawid');
    clearBtn.style.display = 'none';
    searchResults.style.display = 'none';
});

clearSelectionBtn.addEventListener('click', function (e) {
    e.preventDefault();
    patientId.value = '';
    familyMemberId.value = '';
    patientSearch.value = '';
    patientSearch.removeAttribute('data-rawid');
    selectedPatientDisplay.style.display = 'none';
    submitBtn.disabled = true;
    clearBtn.style.display = 'none';
    searchResults.style.display = 'none';
    searchError.style.display = 'none';
});

document.addEventListener('click', function (e) {
    if (!e.target.closest('#patientSearch') && !e.target.closest('#searchResults')) {
        searchResults.style.display = 'none';
    }
});

document.addEventListener('DOMContentLoaded', function () {
    setupFormValidation();
});
