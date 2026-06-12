# Doctor Portal Full Audit & Fix Plan

Based on recent discoveries, several functionalities across the doctor portal are broken due to architectural discrepancies, specifically involving Django template tags inside static JavaScript files and insecure raw database ID passing. 

This audit plan will systematically resolve these issues to restore full functionality.

## Proposed Changes

### 1. Fix Broken Medicine Addition and Editing
The dynamic row generation in "Add Medicine" and "Edit Medicine" is broken because it attempts to render Django template logic (`{% for ... %}`) within static `.js` files.
- [MODIFY] `templates/medicine/add_medicine1.html`: Inject the `unit_choices` as a JSON object into a `<script>` tag before loading `add_medicine.js`.
- [MODIFY] `templates/medicine/edit_medicine.html`: Inject the `unit_choices` as a JSON object into a `<script>` tag before loading `edit_medicine.js`.
- [MODIFY] `static/assets/js/add_medicine.js`: Update the script to build `unitOptions` using the globally injected JSON object rather than using Django tags.
- [MODIFY] `static/assets/js/edit_medicine.js`: Update the script to build `unitOptions` using the globally injected JSON object.

### 2. Fix Broken Search Functionalities
Several search modules are broken because they use `{% url %}` in static JS, causing network requests to hit incorrect paths like `/%7B%25%...`.
- [MODIFY] `static/assets/js/add_purchase.js`: Replace `{% url 'medicine:search_medicine' %}` with the literal URL `/medicine/search/`.
- [MODIFY] `static/assets/js/manage_patients.js`: Replace `{% url 'doctor:manage_patients' %}` with the literal URL `/doctor/patients/`.

### 3. Fix View Patient CSRF Bug
- [MODIFY] `static/assets/js/view_patient.js`: Replace `{{ csrf_token }}` with `getCsrfToken()` logic (similar to the staff and feedback fixes) to ensure AJAX requests for deleting/modifying patient family members succeed without `403 Forbidden` errors.

### 4. Audit Raw ID Exposures
We will perform a thorough sweep across `appointment/views.py`, `medicine/views.py`, and `billing/views.py` to ensure all redirects and reverse URL lookups use hashed IDs (`_hashid.encode_id(...)`) instead of raw integer `.id`s. This prevents `404 Not Found` errors when moving between pages.

## Verification Plan

### Automated/Manual Verification
- Attempt to add a new medicine and verify the "Add Variant" button works perfectly without throwing JS template errors.
- Test searching medicines on the "Add Purchase" page.
- Test searching and filtering on the "Manage Patients" page.
- Attempt to view a patient and execute any secure actions (like managing family members).
- Confirm all changes pass securely and no `403` or `404` errors are thrown in the browser console.

## User Review Required
> [!IMPORTANT]
> Please review this plan. Once you approve, I will execute these changes immediately to resolve all the broken modules across the portal.
