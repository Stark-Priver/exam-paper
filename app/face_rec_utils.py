# app/face_rec_utils.py

import face_recognition
import numpy as np
from app.models import Student, Log, Exam
from app import db # Assuming db is your SQLAlchemy instance from app/__init__.py
from datetime import datetime, timedelta
from flask import current_app

# In-memory cache for known faces. For multi-worker setups, a shared cache (e.g., Redis) is better.
CACHED_KNOWN_FACES = {
    "ids": [],
    "names": [],
    "embeddings": []
}

# Tracks recently logged students to prevent log spam for a single recognition event.
RECENTLY_LOGGED_STUDENTS = {}  # Structure: {exam_id: {student_id: last_log_timestamp}}
LOG_COOLDOWN_SECONDS = 60  # Log a student only once per this interval for an exam.

def load_known_faces_from_db():
    """
    Loads all student face embeddings, IDs, and names from the database into the cache.
    Returns the number of faces loaded.
    """
    global CACHED_KNOWN_FACES
    try:
        # Ensure app context for database query if called outside a request/CLI command context
        # However, this function is typically called from within a route or CLI command context.
        students_with_embeddings = Student.query.filter(Student.face_embedding.isnot(None)).all()
        
        CACHED_KNOWN_FACES["ids"] = [student.id for student in students_with_embeddings]
        CACHED_KNOWN_FACES["names"] = [student.name for student in students_with_embeddings]
        CACHED_KNOWN_FACES["embeddings"] = [student.face_embedding for student in students_with_embeddings]
        
        count = len(CACHED_KNOWN_FACES["ids"])
        if current_app: # current_app might not be available if called at module load time by some tools
            current_app.logger.info(f"Loaded {count} known face(s) from the database into cache.")
        else:
            print(f"(No app context) Loaded {count} known face(s) from the database into cache.")
        return count
    except Exception as e:
        if current_app:
            current_app.logger.error(f"Error loading known faces from DB: {e}")
        else:
            print(f"(No app context) Error loading known faces from DB: {e}")
        CACHED_KNOWN_FACES = {"ids": [], "names": [], "embeddings": []} # Clear cache on error
        return 0

def find_and_log_recognized_faces(frame_rgb, exam_id):
    """
    Detects faces in a frame, recognizes them against cached known faces, logs attendance,
    and returns data for drawing annotations on the frame.

    Args:
        frame_rgb: An RGB image (NumPy array).
        exam_id: The ID of the current exam session.

    Returns:
        A list of dictionaries, where each dictionary contains:
        {'name': str, 'student_id': int or None, 'box': (top, right, bottom, left)}
        for each detected face. 'student_id' is None for unknown faces.
    """
    if not CACHED_KNOWN_FACES["embeddings"]:
        if current_app:
            current_app.logger.warning("No known faces in cache to compare against.")
        else:
            print("(No app context) No known faces in cache to compare against.")
        face_locations = face_recognition.face_locations(frame_rgb)
        return [{'name': 'Unknown', 'student_id': None, 'box': box} for box in face_locations]

    face_locations = face_recognition.face_locations(frame_rgb) # Uses HOG model by default
    face_encodings = face_recognition.face_encodings(frame_rgb, face_locations) # Computes 128-d embeddings

    detected_faces_data = []

    for i, face_encoding in enumerate(face_encodings):
        current_face_box = face_locations[i]
        name = "Unknown"
        student_id_recognized = None

        matches = face_recognition.compare_faces(CACHED_KNOWN_FACES["embeddings"], face_encoding, tolerance=0.50)
        
        best_match_index = -1
        if True in matches:
            face_distances = face_recognition.face_distance(CACHED_KNOWN_FACES["embeddings"], face_encoding)
            best_match_index = np.argmin(face_distances)
            
            if matches[best_match_index]:
                name = CACHED_KNOWN_FACES["names"][best_match_index]
                student_id_recognized = CACHED_KNOWN_FACES["ids"][best_match_index]
                
                was_logged = _log_student_attendance(student_id_recognized, exam_id, name)
                if was_logged and current_app:
                    current_app.logger.info(f"Attendance logged for {name} (ID: {student_id_recognized}) for Exam ID: {exam_id}.")
            else: 
                name = "Unknown"
                student_id_recognized = None
        
        detected_faces_data.append({
            'name': name,
            'student_id': student_id_recognized,
            'box': current_face_box
        })
        
    return detected_faces_data

def _log_student_attendance(student_id, exam_id, student_name_for_log):
    """
    Internal helper to log student attendance if not logged recently for the given exam.
    Returns True if logged, False otherwise.
    """
    global RECENTLY_LOGGED_STUDENTS
    now = datetime.utcnow()

    if exam_id not in RECENTLY_LOGGED_STUDENTS:
        RECENTLY_LOGGED_STUDENTS[exam_id] = {}

    last_log_time = RECENTLY_LOGGED_STUDENTS[exam_id].get(student_id)

    if last_log_time is None or (now - last_log_time) > timedelta(seconds=LOG_COOLDOWN_SECONDS):
        try:
            student_exists = Student.query.get(student_id)
            exam_exists = Exam.query.get(exam_id)

            if not student_exists:
                if current_app:
                    current_app.logger.warning(f"Attempted to log non-existent student ID: {student_id}")
                return False
            if not exam_exists:
                if current_app:
                    current_app.logger.warning(f"Attempted to log for non-existent exam ID: {exam_id}")
                return False

            log_entry = Log(student_id=student_id, exam_id=exam_id, timestamp=now, status="Verified")
            db.session.add(log_entry)
            db.session.commit()
            RECENTLY_LOGGED_STUDENTS[exam_id][student_id] = now
            return True 
        except Exception as e:
            db.session.rollback()
            if current_app:
                current_app.logger.error(f"Error logging attendance for Student {student_name_for_log} (ID: {student_id}): {e}")
            else:
                print(f"(No app context) Error logging attendance for Student {student_name_for_log} (ID: {student_id}): {e}")
            return False
    return False

def get_active_or_upcoming_exams():
    """Returns a list of exams that are upcoming today or currently active (simplified)."""
    today = datetime.utcnow().date()
    return Exam.query.filter(Exam.date >= today).order_by(Exam.date, Exam.start_time).all()

def clear_face_cache():
    """Clears the in-memory face cache."""
    global CACHED_KNOWN_FACES
    CACHED_KNOWN_FACES = {"ids": [], "names": [], "embeddings": []}
    if current_app:
        current_app.logger.info("In-memory face cache cleared.")
    else:
        print("(No app context) In-memory face cache cleared.")

def clear_recent_logs_cache(exam_id=None):
    """Clears the recent logs cache, optionally for a specific exam."""
    global RECENTLY_LOGGED_STUDENTS
    if exam_id:
        if exam_id in RECENTLY_LOGGED_STUDENTS:
            del RECENTLY_LOGGED_STUDENTS[exam_id]
            if current_app:
                current_app.logger.info(f"Recent logs cache cleared for exam ID {exam_id}.")
    else:
        RECENTLY_LOGGED_STUDENTS = {}
        if current_app:
            current_app.logger.info("Entire recent logs cache cleared.")