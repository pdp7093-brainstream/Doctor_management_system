# prescription/views.py

from django.shortcuts import render
from django.core.files.storage import FileSystemStorage
import google.generativeai as genai
from PIL import Image
import os

# ✅ Apni API Key yahan daalo
genai.configure(api_key="AIzaSyCMyfi2ZG341vUHZlr3dUE2-EKGLPdGNxU")

# Gemini Vision Model
model = genai.GenerativeModel('gemini-2.0-flash')

def upload_prescription(request):
    result = None
    error = None
    medicines = []

    if request.method == 'POST' and request.FILES.get('prescription'):
        try:
            # Image save karein
            uploaded_file = request.FILES['prescription']
            fs = FileSystemStorage()
            filename = fs.save(uploaded_file.name, uploaded_file)
            file_path = fs.path(filename)

            # Image open karein
            image = Image.open(file_path)

            # Gemini ko prompt do
            prompt = """
            Yeh ek doctor ki handwritten prescription hai.
            Please is prescription mein se yeh information extract karo:
            
            1. 💊 Medicines/Drugs ke naam
            2. 📏 Dosage (kitni mg/ml)
            3. ⏰ Frequency (din mein kitni baar)
            4. 📅 Duration (kitne din tak)
            5. 🍽️ Before/After food
            6. 🔖 Any special instructions
            
            Agar kuch clearly nahi dikh raha toh "unclear" likho.
            Hindi ya English mein jawab do.
            """

            # Gemini se response lo
            response = model.generate_content([prompt, image])
            result = response.text

        except Exception as e:
            error = f"Kuch problem aayi: {str(e)}"

    return render(request, 'prescription/upload.html', {
        'result': result,
        'error': error,
    })