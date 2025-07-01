# Testing the Facial Recognition Exam Auth System

This document provides guidance on manually testing the various features of the application. Comprehensive automated testing (unit, integration, E2E) is recommended for production systems but is outside the scope of the initial build by the agent.

## Prerequisites for Testing

1.  **Local Setup Complete:** Ensure you have followed all steps in `README.md` for local development setup, including:
    *   Python environment with all dependencies installed (`requirements.txt`).
    *   Database initialized (`flask db upgrade`).
    *   At least one admin user created (`flask create-admin <user> <pass>`).
2.  **Camera:** A working webcam (built-in or USB) accessible by OpenCV on your system. For Raspberry Pi, ensure the Pi Camera is enabled and configured.
3.  **Sample Face Images:** Prepare a small dataset of clear, frontal face images for at least 2-3 individuals.
    *   **Good Quality:** Well-lit, subject looking directly at the camera, no major obstructions (sunglasses, hats obscuring face).
    *   **Variations (Optional, for more robust testing):** Include images with slight variations in expression or lighting if you want to test the limits of the recognition.
    *   **Format:** JPG or PNG.

## Testing Checklist

### 1. Admin Authentication

*   [ ] **Accessing Protected Page:** Navigate to `/` (dashboard). You should be redirected to `/login`.
*   [ ] **Incorrect Login:** Attempt login with invalid credentials. Verify an appropriate error message is flashed.
*   [ ] **Correct Login:** Log in with the admin credentials created via `flask create-admin`. You should be redirected to the admin dashboard (`/index`).
*   [ ] **Accessing Login Page When Authenticated:** While logged in, try to navigate to `/login`. You should be redirected back to the dashboard.
*   [ ] **Logout:** Click the "Logout" link/button. You should be logged out and redirected to the login page, with a confirmation message.

### 2. Student Management (Admin Dashboard)

*   [ ] **Navigate to Student Management:** From the dashboard, go to "Manage Students".
*   [ ] **Add New Student (No Photo):** Attempt to add a student without uploading a photo. Validation should prevent this (photo is required for new students).
*   [ ] **Add New Student (Invalid Photo Type):** Attempt to add a student with a non-image file (e.g., a `.txt` file). Validation should prevent this.
*   [ ] **Add New Student (Photo with No Face):** Upload an image that does not contain a detectable human face. Verify the system reports "No face found" and the student is not added with faulty data.
*   [ ] **Add New Student (Successful):**
    *   Provide Student ID, Name, and a valid face photo.
    *   Verify student is added and appears in the "Manage Students" list.
    *   Verify the photo is visible as a thumbnail.
    *   (Optional) Check the `data/student_images/` directory for the saved image and the database for the `face_embedding` (it will be a BLOB/PickleType).
*   [ ] **Add Multiple Students:** Add 2-3 different students with their respective photos.
*   [ ] **Edit Student (Details only):**
    *   Select a student and edit their Name and/or Student ID Number. Do not upload a new photo.
    *   Save changes. Verify details are updated and the original photo/embedding remains.
*   [ ] **Edit Student (With New Photo):**
    *   Select a student and upload a *new* photo for them (preferably a different image of the same person or a different person to see if recognition changes).
    *   Save changes. Verify the new photo is displayed and (implicitly) the embedding is updated.
*   [ ] **Edit Student (Duplicate Student ID):** Try to change a student's ID to one that already exists for another student. Validation should prevent this.
*   [ ] **Delete Student:**
    *   Select a student and delete them. Confirm the action.
    *   Verify the student is removed from the list.
    *   (Optional) Check that their image file is removed from `data/student_images/`.

### 3. Exam Management (Admin Dashboard)

*   [ ] **Navigate to Exam Management:** From the dashboard, go to "Manage Exams".
*   [ ] **Add New Exam (Invalid Times):** Attempt to add an exam where the end time is before or the same as the start time. Validation should prevent this.
*   [ ] **Add New Exam (Successful):**
    *   Provide Subject, Date, Start Time, and End Time.
    *   Verify the exam is added and appears in the "Manage Exams" list.
*   [ ] **Add Multiple Exams:** Add a few exams with different dates/times.
*   [ ] **Edit Exam:**
    *   Select an exam and modify its details.
    *   Save changes. Verify details are updated.
*   [ ] **Delete Exam:**
    *   Select an exam and delete it. Confirm the action.
    *   Verify the exam is removed from the list.
    *   If this exam had any logs associated with it (see Log testing), those logs should also be deleted.

### 4. Facial Recognition Authentication

*   **Prerequisite:** At least 1-2 students registered with good quality face photos. At least one exam created.
*   [ ] **Refresh Face Cache (from Select Exam page):**
    *   Navigate to "Live Authentication Session" -> "Select Exam".
    *   Click "Refresh Known Faces Cache". Verify a success message.
*   [ ] **Start Authentication Session:**
    *   Select an exam from the list to start the session.
    *   The `live_auth.html` page should load, showing the exam details.
    *   The video feed from your camera should appear. If not, check console logs for camera errors.
    *   A flash message should indicate how many faces were loaded into the cache.
*   [ ] **Recognize Known Student:**
    *   Position a registered student in front of the camera.
    *   Verify their name appears on the video feed with a green bounding box.
    *   Verify their attendance is logged (check "View Logs" later).
    *   Keep them in view for more than the `LOG_COOLDOWN_SECONDS` (default 60s). They should only be logged once initially, then not again until the cooldown expires.
*   [ ] **Recognize Multiple Known Students:** If possible, have multiple registered students in the frame. Verify they are recognized.
*   [ ] **Unknown Person:** Have an unregistered person in front of the camera. Verify they are marked as "Unknown" with a red bounding box.
*   [ ] **Refresh Face Cache (from Live Auth page):**
    *   While the session is live, click "Refresh Known Faces (Live)".
    *   If you add/update a student in another tab, this refresh *should* pick up the changes for the current session. Test this if feasible.
*   [ ] **End Session:** Navigate away from the live auth page (e.g., back to dashboard or select exam). The camera should release. (The `stop_video_feed` route is intended for this, ideally triggered by JS `onbeforeunload` or a specific "Stop" button if added).

### 5. View Logs (Admin Dashboard)

*   [ ] **Navigate to View Logs:** From the dashboard, go to "View Logs".
*   [ ] **Verify Log Entries:**
    *   Check if attendance logs from the facial recognition session appear correctly.
    *   Verify Student Name, Student ID, Exam Subject, Exam Date, Timestamp, and Status ("Verified").
*   [ ] **Pagination:** If you have more than 15 logs, test the pagination controls (Next, Previous, page numbers).
*   [ ] **(If Filters Implemented):** Test filtering logs by date, exam, or student.

### 6. General UI/UX

*   [ ] **Responsiveness:** Resize your browser window to check how the layout adapts on smaller screens. Pay attention to tables and forms.
*   [ ] **Navigation:** Ensure all navigation links in the navbar and on dashboard cards work correctly.
*   [ ] **Flashed Messages:** Verify success, error, and info messages appear appropriately after actions (e.g., adding student, login error). Ensure they are dismissible.
*   [ ] **Clarity of Forms:** Check if form labels, placeholders, and error messages are clear.

## Notes on `dlib` and `face-recognition` Installation

If `pip install -r requirements.txt` fails, it's often due to `dlib`.

*   **Linux/Raspberry Pi:**
    *   Ensure `build-essential`, `cmake`, `libopenblas-dev`, `liblapack-dev` are installed.
    *   `sudo pip3 install dlib --verbose` might give more insight or try to find a pre-compiled wheel for your specific Pi architecture if available (`.whl` file).
*   **macOS:**
    *   `brew install cmake`
    *   `brew install boost` (sometimes needed for dlib)
    *   Face XQuartz issues if dlib tries to build GUI components (usually not needed for this project).
*   **Windows:**
    *   This can be the most challenging. You'll need a C++ compiler (e.g., from Visual Studio Build Tools) and CMake.
    *   Often, finding a pre-compiled `dlib.whl` file for your Python version and Windows architecture from a trusted source (like Christoph Gohlke's Unofficial Windows Binaries for Python Extension Packages) and installing it via `pip install dlib‑X.Y.Z‑cpXX‑cpXXm‑win_amd64.whl` before running `requirements.txt` is the easiest path.

This testing guide should help ensure the application's core functionalities are working as expected.
