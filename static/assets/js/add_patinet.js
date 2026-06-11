const parentSearch   = document.getElementById('parentSearch');
const parentSuggestions = document.getElementById('parentSuggestions');
const parentInput    = document.getElementById('parent_patient_input');
const relationField  = document.getElementById('relationField');
const relationSelect = document.getElementById('relationSelect');
const phoneInput     = document.getElementById('phoneInput');
const phoneLabel     = document.getElementById('phoneLabel');
const phoneHint      = document.getElementById('phoneHint');
const emailField     = document.getElementById('emailField');
const addressField   = document.getElementById('addressField');
const modeText       = document.getElementById('modeText');
const submitText     = document.getElementById('submitText');

let parentTimer;

function clearParentSuggestions(){
    parentSuggestions.innerHTML = '';
    parentSuggestions.style.display = 'none';
}

function renderParentItems(items){
    parentSuggestions.innerHTML = '';
    if(!items || !items.length){
        // show a helpful "no results" action allowing creation of a new main patient
        const q = parentSearch.value.trim();
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'list-group-item list-group-item-action disabled text-muted';
        btn.textContent = q ? `No match found — will create new patient: "${q}"` : 'No match found';
        parentSuggestions.appendChild(btn);
        parentSuggestions.style.display = 'block';
        return;
    }
    items.forEach(it => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'list-group-item list-group-item-action';
        btn.textContent = it.display;
        btn.dataset.id = it.id;
        btn.dataset.name = it.name || '';
        btn.dataset.phone = it.phone || '';
        btn.addEventListener('click', () => {
            parentSearch.value = btn.dataset.name || btn.textContent;
            phoneInput.value = btn.dataset.phone || '';
            parentInput.value = btn.dataset.id;

            // show relation field and adjust validation
            relationField.style.display = 'block';
            relationSelect.required = true;
            phoneInput.required = false;
            emailField.style.display = 'none';
            addressField.style.display = 'none';
            modeText.innerHTML = ` Parent selected — this person will be added as a <strong>family member</strong> of <strong>${btn.dataset.name || btn.textContent}</strong>. No separate login will be created.`;
            submitText.textContent = 'Save Family Member';
            clearParentSuggestions();
        });
        parentSuggestions.appendChild(btn);
    });
    parentSuggestions.style.display = 'block';
}

parentSearch && parentSearch.addEventListener('input', function(){
    clearTimeout(parentTimer);
    parentInput.value = '';
    relationField.style.display = 'none';
    relationSelect.required = false;
    phoneInput.required = true;
    emailField.style.display = 'block';
    addressField.style.display = 'block';
    modeText.innerHTML = ` No parent selected — this person will be added as a <strong>main patient</strong> with their own login.`;
    submitText.textContent = 'Save Patient';

    const q = this.value.trim();
    if(!q || q.length < 2){ clearParentSuggestions(); return; }

    parentTimer = setTimeout(()=>{
        fetch(`/appointment/search-patients/?q=${encodeURIComponent(q)}`)
            .then(r => r.json())
            .then(data => {
                        const results = data.results || [];
                        // Only include main patients (ids like 'patient_<id>') — ignore family member results
                        const patientResults = results.filter(r => (typeof r.id === 'string' && r.id.startsWith('patient_')));
                        const items = patientResults.map(it => {
                            let parsedId = it.id.split('_')[1];
                            return {
                                id: parsedId,
                                name: it.name || (it.user__first_name ? (it.user__first_name + (it.user__last_name ? (' ' + it.user__last_name) : '')) : ''),
                                phone: it.phone || it.user__email || '',
                                display: it.display || it.name || it.phone || ''
                            };
                        });
                renderParentItems(items);
            })
            .catch(err => { console.error('parent search error', err); clearParentSuggestions(); });
    }, 250);
});

// if click outside suggestions, hide
document.addEventListener('click', function(e){
    if(!e.target.closest('#parentSuggestions') && !e.target.closest('#parentSearch')){
        clearParentSuggestions();
    }
});