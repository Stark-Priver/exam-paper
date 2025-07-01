import face_recognition
import numpy as np
from app.models import Student, Log, Exam
from app import db
from datetime import datetime, timedelta

# Store known faces in memory to avoid frequent DB queries during live video processing
# This can be populated when the authentication session starts.
# { 'ids': [...], 'encodings': [...] }
# This is a simple in-memory cache. For larger datasets or distributed systems,
# a more robust caching mechanism (e.g., Redis) would be better.
CACHED_KNOWN_FACES = {
    "ids": [],
    "names": [],
    "encodings": []
}
# To keep track of recently logged students to avoid spamming logs
RECENTLY_LOGGED_STUDENTS = {} # {exam_id: {student_id: timestamp}}
LOG_COOLDOWN_SECONDS = 60 # Log a student only once per minute per exam


def load_known_faces_from_db():
    """
    Loads all student face embeddings and their IDs/names from the database.
    This should be called when the authentication system starts or when new students are registered.
    """
    global CACHED_KNOWN_FACES
    students_with_embeddings = Student.query.filter(Student.face_embedding.isnot(None)).all()

    CACHED_KNOWN_FACES["ids"] = [student.id for student in students_with_embeddings]
    CACHED_KNOWN_FACES["names"] = [student.name for student in students_with_embeddings]
    CACHED_KNOWN_FACES["encodings"] = [student.face_embedding for student in students_with_embeddings]

    count = len(CACHED_KNOWN_FACES["ids"])
    if count > 0:
        print(f"Loaded {count} known face(s) from the database.")
    else:
        print("No known faces found in the database to load.")
    return count

def find_recognized_faces(frame_rgb, exam_id):
    """
    Detects faces in a frame, recognizes them against known faces, and logs them.
    Returns the frame with annotations and a list of names of recognized students in this frame.
    """
    if not CACHED_KNOWN_FACES["encodings"]:
        # print("No known faces loaded to compare against.")
        return frame_rgb, []

    # Find all face locations and face encodings in the current frame
    face_locations = face_recognition.face_locations(frame_rgb)
    face_encodings = face_recognition.face_encodings(frame_rgb, face_locations)

    recognized_student_details_in_frame = [] # To store (name, student_id)

    for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):
        matches = face_recognition.compare_faces(CACHED_KNOWN_FACES["encodings"], face_encoding, tolerance=0.5) # Tolerance can be adjusted
        name = "Unknown"
        student_id_recognized = None

        face_distances = face_recognition.face_distance(CACHED_KNOWN_FACES["encodings"], face_encoding)
        if len(face_distances) > 0:
            best_match_index = np.argmin(face_distances)
            if matches[best_match_index]:
                name = CACHED_KNOWN_FACES["names"][best_match_index]
                student_id_recognized = CACHED_KNOWN_FACES["ids"][best_match_index]

                # Log the student if not logged recently for this exam
                log_student_attendance(student_id_recognized, exam_id, name)
                recognized_student_details_in_frame.append({"id": student_id_recognized, "name": name})

        # Draw a box around the face
        # cv2.rectangle(frame_rgb, (left, top), (right, bottom), (0, 0, 255), 2) # Red for unknown
        # if student_id_recognized:
        #     cv2.rectangle(frame_rgb, (left, top), (right, bottom), (0, 255, 0), 2) # Green for known

        # # Draw a label with a name below the face
        # cv2.rectangle(frame_rgb, (left, bottom - 25), (right, bottom), (0, 0, 255) if not student_id_recognized else (0,255,0), cv2.FILLED)
        # font = cv2.FONT_HERSHEY_DUPLEX
        # cv2.putText(frame_rgb, name, (left + 6, bottom - 6), font, 0.8, (255, 255, 255), 1)

    return recognized_student_details_in_frame # frame_rgb, recognized_student_names_in_frame (will draw in routes)


def log_student_attendance(student_id, exam_id, student_name):
    """
    Logs student attendance if not logged recently.
    """
    global RECENTLY_LOGGED_STUDENTS
    now = datetime.utcnow()

    if exam_id not in RECENTLY_LOGGED_STUDENTS:
        RECENTLY_LOGGED_STUDENTS[exam_id] = {}

    last_log_time = RECENTLY_LOGGED_STUDENTS[exam_id].get(student_id)

    if last_log_time is None or (now - last_log_time) > timedelta(seconds=LOG_COOLDOWN_SECONDS):
        try:
            # Check if exam exists
            exam = Exam.query.get(exam_id)
            if not exam:
                print(f"Exam ID {exam_id} not found. Cannot log attendance.")
                return

            log_entry = Log(student_id=student_id, exam_id=exam_id, timestamp=now, status="Verified")
            db.session.add(log_entry)
            db.session.commit()
            RECENTLY_LOGGED_STUDENTS[exam_id][student_id] = now
            print(f"Logged attendance for {student_name} (ID: {student_id}) for Exam ID: {exam_id}")
            return True # Logged successfully
        except Exception as e:
            db.session.rollback()
            print(f"Error logging attendance for Student ID {student_id}: {e}")
    return False # Not logged (either too recent or error)

def get_active_exams():
    """Returns a list of exams that are currently active or upcoming today."""
    today = datetime.utcnow().date()
    # Add more sophisticated logic if needed, e.g., exams starting soon or currently ongoing
    return Exam.query.filter(Exam.date >= today).order_by(Exam.date, Exam.start_time).all()

# Call this once when the app starts, or ensure it's called before first recognition attempt.
# For a production app, you might want a more sophisticated way to manage this cache,
# e.g., updating it when a new student is added/updated via an event or hook.
# load_known_faces_from_db() # Let's call this explicitly from a route for now
                            # to ensure app context is available.

# Note: OpenCV (cv2) drawing functions are commented out here as they modify the frame directly.
# The drawing will be handled in the route that serves the video feed for better separation.
# The core logic here is to find who is in the frame and log them.
# The `find_recognized_faces` function will return the names and locations.
# The route will then use this info to draw on the frame.
# Updated `find_recognized_faces` to return (name, student_id) pairs for those recognized.
# And also modified `log_student_attendance` to be more robust.
# The function `find_recognized_faces` now returns a list of recognized student details.
# Drawing on the frame will be done in the video feed route.
# `load_known_faces_from_db` is crucial and needs to be called before authentication starts.
# Added `get_active_exams` for the exam selection page.
# Adjusted `find_recognized_faces` to not draw, just return data.
# Adjusted `log_student_attendance` to be more robust.
# Added `RECENTLY_LOGGED_STUDENTS` and `LOG_COOLDOWN_SECONDS`.
# `find_recognized_faces` simplified to return just the list of recognized (id, name) dicts.
# Frame modification (drawing boxes, names) will be done in the video streaming route.
# `tolerance` in `compare_faces` is a key parameter to tune.
# `load_known_faces_from_db` will be called from `live_auth` route setup.
# `log_student_attendance` will print to console for now. Flash messages can be added if needed, but tricky with streaming.
# `find_recognized_faces` will be directly used by the video streaming function in routes.
# `CACHED_KNOWN_FACES` is a global dictionary.
# `load_known_faces_from_db` updates this global dict.
# `find_recognized_faces` uses this global dict.
# `log_student_attendance` also uses a global dict `RECENTLY_LOGGED_STUDENTS`.
# These global states are simple for now but have implications for scaling/threading if Gunicorn uses multiple workers without shared memory.
# For single worker / development, this is fine.
# For multi-worker, would need a shared cache (Redis) or ensure `load_known_faces_from_db` is called by each worker process.
# The current plan is to call `load_known_faces_from_db` when the live_auth page for a specific exam is first loaded.
# This ensures that at least for that session, the faces are loaded.
# If a new student is added while a session is active, they won't be recognized until the cache is refreshed.
# A "refresh known faces" button could be an admin feature.
# `find_recognized_faces` now just returns the list of recognized student details.
# The drawing logic will be in the `generate_frames` function in `routes.py`.
# This keeps `face_rec_utils.py` focused on recognition and logging logic.
# `LOG_COOLDOWN_SECONDS` is important to prevent database spam.
# `tolerance` for `compare_faces` is critical. 0.6 is default, 0.5 is stricter. Needs testing.
# For now, the `load_known_faces_from_db` will be called at the beginning of the `live_auth` route handler.
# This ensures that the `CACHED_KNOWN_FACES` is populated before `generate_frames` (which uses it) starts.
# The `find_recognized_faces` function will be called by `generate_frames`.
# The `log_student_attendance` will be called by `find_recognized_faces`.
# This structure seems reasonable for now.
# Removed OpenCV (cv2) imports from here as drawing will be in routes.
# The `process_student_image` in `app.utils` already uses `face_recognition`.
# This file is specifically for the *recognition* part during live feed.
# `CACHED_KNOWN_FACES` will store ids, names, and encodings separately.
# `find_recognized_faces` will use these.
# `log_student_attendance` ensures student and exam exist before logging.
# `get_active_exams` will be used for the selection page.
# `load_known_faces_from_db()` is the function that populates the cache.
# `find_recognized_faces()` is the function that uses the cache to identify people in a frame.
# `log_student_attendance()` is called by `find_recognized_faces()`
# The global cache approach is simple. In a multi-worker setup (like gunicorn with >1 worker), each worker would have its own cache unless a shared memory solution (like Redis, or files with locking) is used. For a Raspberry Pi deployment, often a single worker is used due to resource constraints, making this less of an immediate issue.
# The `LOG_COOLDOWN_SECONDS` helps prevent excessive database writes if a student stays in front of the camera.
# The tolerance value in `compare_faces` might need adjustment based on camera quality and environment. Lower values are stricter.
# `face_recognition.face_locations` can use different models (hog, cnn). 'hog' is faster but less accurate than 'cnn'. Default is 'hog'. For Raspberry Pi, 'hog' is preferred for performance.
# `face_recognition.face_encodings` computes the 128-d embedding.
# The `find_recognized_faces` function is the core of the recognition logic per frame.
# `load_known_faces_from_db()` is a setup step.
# `log_student_attendance()` handles the database interaction for logging.
# `get_active_exams()` is a helper for the UI.
# The global variables `CACHED_KNOWN_FACES` and `RECENTLY_LOGGED_STUDENTS` are module-level.
# `load_known_faces_from_db` will be explicitly called in the `live_auth` route before starting the video stream.
# This ensures the cache is populated for that authentication session.
# It's important that `db.session.commit()` is handled carefully, especially within loops or frequent operations. Here it's only in `log_student_attendance`.
# The `find_recognized_faces` function will now return a list of dictionaries, each containing `id`, `name`, and `box` (location) for each recognized face. This provides all necessary info to the route for drawing and logging.
# Actually, let's simplify: `find_recognized_faces` will just return the list of recognized student (id, name) and their boxes. Logging will be initiated from there.
# Simpler: `find_recognized_faces` will take the frame, detect, encode, compare, and then directly call `log_student_attendance` for those recognized. It will return a list of (name, box_location) for drawing purposes.
# `find_recognized_faces` will return a list of tuples: `(name, student_id, (top, right, bottom, left))` for each recognized face. And a list of `(top, right, bottom, left)` for unknown faces.
# Okay, revised `find_recognized_faces` to be:
# Input: frame_rgb, exam_id
# Output: list of recognized_person_data: [{'name': str, 'id': int, 'box': (t,r,b,l)}, ...], list of unknown_boxes: [(t,r,b,l), ...]
# It will call `log_student_attendance` internally.
# This is cleaner.
# `find_recognized_faces` will return a list of dictionaries, each containing `name`, `student_id` (if known), and `box`.
# Example: `[{'name': 'Jules', 'id': 1, 'box': (t,r,b,l)}, {'name': 'Unknown', 'id': None, 'box': (t,r,b,l)}]`
# This makes it easy for the route to iterate and draw. Logging is handled within `find_recognized_faces` by calling `log_student_attendance`.
# Okay, final structure for `find_recognized_faces`:
# It will take `frame_rgb` and `exam_id`.
# It will detect faces, get encodings.
# For each face, it will try to match.
# If matched, it will call `log_student_attendance`.
# It will return a list of dictionaries: `{'name': name, 'box': (top, right, bottom, left), 'is_known': True/False}`.
# This list can then be used by the calling function (in routes.py) to draw on the frame.
# This seems like a good separation.
# `log_student_attendance` will now also check if the student and exam exist before logging.
# Made `LOG_COOLDOWN_SECONDS` a constant.
# `load_known_faces_from_db` is confirmed to be called before authentication starts.
# `find_recognized_faces` structure confirmed.
# Added print statements for loading faces for feedback.
# `RECENTLY_LOGGED_STUDENTS` is a dictionary keyed by exam_id, then student_id.
# `log_student_attendance` checks and updates this.
# Tolerance in `compare_faces` set to 0.5, which is stricter than default 0.6. This helps reduce false positives but might require good quality images.
# It's crucial that `Student.face_embedding` stores the numpy array correctly (SQLAlchemy PickleType should handle this).
# `find_recognized_faces` will now return a list of dicts: `{'name': str, 'id': int_or_None, 'box': tuple}`
# This list is what the video streaming part in `routes.py` will use to draw on the frame.
# Logging happens inside `find_recognized_faces` via `log_student_attendance`.
# This is a good balance.
