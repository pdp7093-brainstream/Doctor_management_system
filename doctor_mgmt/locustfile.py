import uuid
import random
from locust import HttpUser, task, between

class RealUserClinicJourney(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        # 1. Fetch CSRF from signup page
        response = self.client.get("/sign-up/")
        self.csrf_token = response.cookies.get('csrftoken', '')

        # Generate unique fake data matching the form UI
        self.fake_phone = f"9876{random.randint(100000, 999999)}"
        self.fake_name = f"Test User {uuid.uuid4().hex[:4]}"
        self.email = f"user_{uuid.uuid4().hex[:4]}@gmail.com"
        self.password = "SecurePass123!"

        # 2. Complete registration on the real path
        print(f"--- Registering user via /sign-up/ with phone {self.fake_phone} ---")
        self.client.post("/sign-up/", {
            "name": self.fake_name,
            "email": self.email,
            "phone": self.fake_phone,
            "password": self.password,
            "csrfmiddlewaretoken": self.csrf_token
        }, headers={"Referer": f"{self.host}/sign-up/"})

        # 3. Handle login session setup on the correct path
        login_page = self.client.get("/login/")
        login_csrf = login_page.cookies.get('csrftoken', '')
        
        self.client.post("/login/", {
            "phone": self.fake_phone,
            "password": self.password,
            "csrfmiddlewaretoken": login_csrf
        }, headers={"Referer": f"{self.host}/login/"})

    @task
    def complete_appointment_flow(self):
        # 1. Access dashboard first to maintain session context
        self.client.get("/")
        current_csrf = self.client.cookies.get('csrftoken', '')
        
        # 2. Strict validation wrapper using catch_response=True
        # Adjusted Payload Keys: Django expects 'date' and 'time_slot'.
        # Dynamic User Context: 'patient_id' is NOT needed because Django automatically
        # extracts the patient from `request.user` via the active session cookie.
        appointment_payload = {
            "date": "2026-06-12",
            "time_slot": "11:30",
            "message": "Routine checkup via locust",  # Maps to notes internally
            "csrfmiddlewaretoken": current_csrf,
        }
        
        with self.client.post("/appointment/", data=appointment_payload, headers={"Referer": f"{self.host}/appointment/"}, catch_response=True) as response:
            # Agar Django redirect (302) karta hai ya response me success text aata hai toh pass karo
            if response.status_code == 302 or (response.status_code == 200 and "appointment" in response.url and "error" not in response.text.lower()):
                response.success()
            else:
                # Agar wapas wahi page load ho jaye validation error ke saath, toh failure catch karo
                response.failure(f"Form validation failed or user unauthorized. Status: {response.status_code}")