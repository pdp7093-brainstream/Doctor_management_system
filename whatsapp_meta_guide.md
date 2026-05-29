# WhatsApp Meta Cloud API Setup Guide

To integrate WhatsApp for OTPs and appointment notifications in your Django system, we need to use the official **WhatsApp Business Cloud API**. 

Since we will be sending automated messages (system to user), Meta requires you to set up an official Business App. Here is exactly what you need to do on your end before we can write the Python code.

## Step 1: Create a Meta Developer Account
1. Go to [developers.facebook.com](https://developers.facebook.com/).
2. Log in with your Facebook account.
3. Click on **My Apps** -> **Create App**.

## Step 2: Set up the App
1. When asked what your app does, select **Other** and then **Business**.
2. Give your app a name (e.g., `PDP Clinic Notifications`).
3. Enter your contact email.
4. If you have a Meta Business Account (Business Manager), select it. If not, you can leave it unselected and Meta will create a default one for you.
5. Click **Create App**.

## Step 3: Add WhatsApp to your App
1. Once your app is created, you will see a list of "Products". Scroll down and find **WhatsApp**, then click **Set Up**.
2. Select your Meta Business Account and continue.
3. In the left sidebar, navigate to **WhatsApp** -> **API Setup**.

## Step 4: Collect API Credentials
On the "API Setup" page, you will see a testing environment. Meta provides you with a test phone number to send messages to yourself. **Please copy and save the following 3 things for me:**

1.  **Temporary Access Token:** (This expires in 24 hours. Later, we will generate a Permanent Token).
2.  **Phone Number ID:**
3.  **WhatsApp Business Account ID:**

## Step 5: Create Message Templates (Important)
Meta does not allow businesses to send random text messages to users unless the user messaged first. For OTPs and Appointment Reminders, we **must** use pre-approved Templates.

1. In the Meta Dashboard, go to **WhatsApp** -> **Message Templates**.
2. Create a new template for OTP. 
    *   **Category:** Authentication
    *   **Name:** `clinic_otp`
    *   **Language:** English
    *   **Content:** "Your verification code for PDP Clinic is {{1}}. Please do not share this code."
3. Create a template for Appointments.
    *   **Category:** Utility
    *   **Name:** `appointment_confirmed`
    *   **Content:** "Hello {{1}}, your appointment with Dr. {{2}} is confirmed for {{3}}. See you soon!"

## Next Steps for Us (Backend)
Once you provide me with the **Phone Number ID** and the **Access Token**, I will:
1. Write the Python code in `appointment/views.py` and `accounts/views.py` to call the Meta API.
2. Replace your current OTP system with the WhatsApp API call.
3. Set up the automated triggers when an appointment is booked or cancelled.

> [!WARNING]
> For production (going live with real patients), you will need to add a real phone number to the Meta dashboard. **Note:** That phone number cannot be currently registered on the normal WhatsApp or WhatsApp Business mobile app. It must be deleted from the mobile app first.
