from django import forms
from django.core.exceptions import ValidationError

MAX_FILE_SIZE_MB = 5
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024


class PatientImportForm(forms.Form):
    file = forms.FileField(
        label="Select File",
        widget=forms.ClearableFileInput(attrs={
            "class": "form-control",
            "accept": ".csv, .xlsx, .xlsm, application/vnd.openxmlformats-officedocument.spreadsheetml.sheet, text/csv",
        }),
        help_text=f"CSV or Excel (.xlsx) file, maximum {MAX_FILE_SIZE_MB} MB."
    )

    def clean_file(self):
        uploaded_file = self.cleaned_data.get("file")
        if not uploaded_file:
            raise ValidationError("Please select a file to upload.")

        filename = uploaded_file.name.lower()
        if not (filename.endswith(".csv") or filename.endswith(".xlsx") or filename.endswith(".xlsm")):
            raise ValidationError("Invalid file format. Please upload a .csv or .xlsx file.")

        if uploaded_file.size > MAX_FILE_SIZE_BYTES:
            raise ValidationError(f"File size exceeds {MAX_FILE_SIZE_MB} MB. Please upload a smaller file.")

        return uploaded_file
