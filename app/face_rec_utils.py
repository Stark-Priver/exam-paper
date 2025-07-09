# app/face_rec_utils.py
from deepface import DeepFace
import numpy as np
from app.models import Student, Log, Exam
from app import db
from datetime import datetime, timedelta
from flask import current_app
import os
import re # For parsing student ID from filename

# Configuration for DeepFace
DEEPFACE_MODEL_NAME = 'VGG-Face' # Non-dlib model
DEEPFACE_DETECTOR_BACKEND = 'opencv' # Haar cascade, non-dlib
DEEPFACE_DISTANCE_METRIC = 'cosine'

# Tracks recently logged students to prevent log spam for a single recognition event.
RECENTLY_LOGGED_STUDENTS = {}  # Structure: {exam_id: {student_id: last_log_timestamp}}
LOG_COOLDOWN_SECONDS = 60  # Log a student only once per this interval for an exam.

# Global variable to store student details mapped by their image filename for quick lookup
# This can be populated by `load_known_faces_from_db`
STUDENT_IMAGE_MAP = {} # Example: {"student_1_john_doe.jpg": {"id": 1, "name": "John Doe", "student_id_number": "S1001"}}

def load_known_faces_from_db():
    """
    Verifies the student image database path and populates STUDENT_IMAGE_MAP.
    Returns the number of student profiles with images found.
    """
    global STUDENT_IMAGE_MAP
    STUDENT_IMAGE_MAP = {} # Reset map
    image_db_path = current_app.config.get('UPLOAD_FOLDER')
    if not image_db_path or not os.path.isdir(image_db_path):
        current_app.logger.error(f"Student image database path not found or not a directory: {image_db_path}")
        return 0

    students_with_images = Student.query.filter(Student.face_image_path.isnot(None)).all()
    count = 0
    for student in students_with_images:
        # Ensure the image file actually exists
        full_image_path = os.path.join(image_db_path, student.face_image_path)
        if os.path.isfile(full_image_path):
            STUDENT_IMAGE_MAP[student.face_image_path] = {
                "id": student.id,
                "name": student.name,
                "student_id_number": student.student_id_number
            }
            count += 1
        else:
            current_app.logger.warning(f"Image file {student.face_image_path} for student {student.name} not found in {image_db_path}.")

    if current_app:
        current_app.logger.info(f"Verified {count} student profiles with accessible images in {image_db_path}.")
    return count

def find_and_log_recognized_faces(frame_bgr, exam_id):
    """
    Detects and recognizes faces in a BGR frame using DeepFace, logs attendance,
    and returns data for drawing annotations.

    Args:
        frame_bgr: A BGR image (NumPy array) from OpenCV.
        exam_id: The ID of the current exam session.

    Returns:
        A list of dictionaries, where each dictionary contains:
        {'name': str, 'student_id': int or None, 'student_id_number': str or None,
         'box': (top, right, bottom, left), 'status': str}
        for each detected face.
    """
    detected_faces_data = []
    image_db_path = current_app.config.get('UPLOAD_FOLDER')

    if not STUDENT_IMAGE_MAP: # If map is empty, try to load it.
        load_known_faces_from_db()
        if not STUDENT_IMAGE_MAP: # Still empty after loading
            current_app.logger.warning("No known student images available to compare against for exam_id %s.", exam_id)
            # Optionally, perform face detection anyway to draw boxes for unknown faces
            try:
                detected_raw_faces = DeepFace.extract_faces(
                    img_path=frame_bgr.copy(), # Pass a copy to avoid modification by DeepFace
                    detector_backend=DEEPFACE_DETECTOR_BACKEND,
                    enforce_detection=False,
                    align=False # Usually good to have align=True for recognition, but for just detection it's faster
                )
                for face_info in detected_raw_faces:
                    if face_info['confidence'] > 0: # Check if a face was actually detected
                        x, y, w, h = face_info['facial_area']['x'], face_info['facial_area']['y'], face_info['facial_area']['w'], face_info['facial_area']['h']
                        box = (y, x + w, y + h, x) # top, right, bottom, left
                        detected_faces_data.append({'name': 'Unknown', 'student_id': None, 'student_id_number': None, 'box': box, 'status': 'Unknown_Student'})
            except Exception as e:
                current_app.logger.error(f"Error during face detection for unknown faces: {e}")
            return detected_faces_data


    current_exam = Exam.query.get(exam_id)
    if not current_exam:
        current_app.logger.error(f"Exam with ID {exam_id} not found in find_and_log_recognized_faces.")
        # To provide bounding boxes even on error, we'd need to run detection separately.
        # For now, return empty if exam not found, or adapt to detect and return unknown boxes.
        return []

    registered_student_ids_for_exam = {s.id for s in current_exam.registered_students}

    try:
        # DeepFace.find returns a list of pandas DataFrames if multiple faces are detected in img_path.
        # Each DataFrame corresponds to one detected face in img_path and lists its matches from db_path.
        # If img_path has one face, result is a list with one DataFrame.
        # If img_path has no faces, DeepFace.find might raise an exception if enforce_detection=True (default).
        # We use enforce_detection=False with extract_faces for initial detection.
        
        # 1. Detect all faces in the frame
        # DeepFace.extract_faces returns a list of dicts, each with 'facial_area' and 'confidence'
        all_detected_in_frame = DeepFace.extract_faces(
            img_path=frame_bgr.copy(), # Use a copy
            detector_backend=DEEPFACE_DETECTOR_BACKEND,
            enforce_detection=False,
            align=True # Align for better recognition
        )

        if not all_detected_in_frame:
            return [] # No faces detected in the frame

        for detected_face_info in all_detected_in_frame:
            if detected_face_info['confidence'] == 0: # Should not happen with enforce_detection=False if it returns the entry
                continue

            x, y, w, h = detected_face_info['facial_area']['x'], detected_face_info['facial_area']['y'], detected_face_info['facial_area']['w'], detected_face_info['facial_area']['h']
            current_face_box = (y, x + w, y + h, x) # top, right, bottom, left

            # Crop the detected face for DeepFace.find, as it expects a single face image for img_path
            # or use DeepFace.represent on the crop and compare manually if find is slow.
            # For now, let's try DeepFace.find with the cropped face. (Needs path, so save temp or use represent)

            # Alternative: Use DeepFace.represent on the cropped face and compare with pre-loaded known embeddings
            # For simplicity with DeepFace.find and db_path, we identify *each* detected face from the frame
            # against the entire image DB.
            
            # DeepFace.find can take a numpy array for img_path.
            # It will find faces in this array and compare each found face with db_path.
            # However, it's more efficient to pass already cropped faces if we have them.
            # The return of DeepFace.find when img_path has multiple faces can be complex.
            # Let's use the frame_bgr directly with DeepFace.find and then map results to original detections.
            # This is simpler if DeepFace.find itself handles multiple faces in img_path well.
            # According to docs, if img_path contains multiple faces, find results is a list of DFs.
            # The DataFrame for each found face in img_path will have 'source_x', 'source_y', 'source_w', 'source_h'
            # This allows us to map the recognized person back to a specific detected face in the original frame.

            # We will iterate over faces found by DeepFace.find in the frame_bgr
            # This avoids calling DeepFace.find multiple times for each detected face by extract_faces
            pass # Placeholder for the loop logic below which will use DeepFace.find on the whole frame


        # Perform recognition on the whole frame
        # DeepFace.find will detect faces and try to recognize them
        # The result is a list of DataFrames, one for each detected face in `frame_bgr`.
        recognition_results_list = DeepFace.find(
            img_path=frame_bgr.copy(), # Pass a copy, DeepFace might modify
            db_path=image_db_path,
            model_name=DEEPFACE_MODEL_NAME,
            detector_backend=DEEPFACE_DETECTOR_BACKEND, # It will re-detect.
            distance_metric=DEEPFACE_DISTANCE_METRIC,
            enforce_detection=False, # Don't error if no face found in frame
            silent=True
        )
        # print(f"DeepFace.find results: {recognition_results_list}") # For debugging

        # Process each DataFrame in the list (each corresponds to a face detected in frame_bgr)
        for df_result in recognition_results_list:
            if df_result.empty:
                # This means a face was detected in frame_bgr by DeepFace.find's internal detector,
                # but no match was found in db_path. We need its bounding box.
                # The DataFrame itself contains 'source_x', 'source_y', 'source_w', 'source_h' for the detected face in frame_bgr
                if 'source_x' in df_result.columns: # Check if these columns exist (they should if a face was detected by find)
                    # This case is tricky: df_result is empty if NO matches, but we need the source box.
                    # This structure suggests DeepFace.find's return for "no match" might not directly give the source box of the unmatched face.
                    # Let's re-evaluate. If df_result is empty, it means no match.
                    # We need to get the boxes from an initial detection pass.
                    # The initial `all_detected_in_frame` using `extract_faces` provides these boxes.
                    # We should iterate through `all_detected_in_frame`, then for each, try to recognize.
                    # This is becoming complex. A simpler approach for now:
                    # Iterate through `recognition_results_list` (faces found AND potentially matched in frame).
                    # For faces detected but not matched, `DeepFace.find` might not list them clearly if the DF is for matches.

                    # Let's assume `recognition_results_list` contains one DF per face *detected by find's detector* in `img_path`.
                    # If that face has matches, the DF is populated. If not, the DF might be empty or structured differently.
                    # The `DeepFace.find` documentation implies the DF is for *matches*.
                    # This means we need to handle "unknowns" by comparing boxes from `extract_faces` and `find`.

                    # For now, let's simplify: if df_result is truly empty for a detected region, we mark as Unknown.
                    # The issue is getting the box for that unknown if df_result itself doesn't have it.
                    # Let's use the boxes from `DeepFace.find` directly. These are in `df_result.iloc[0]['source_x']` etc.
                    # but only if df_result is NOT empty.
                    pass # Covered by the logic below if no match from STUDENT_IMAGE_MAP

            if not df_result.empty:
                # Face detected in frame_bgr and at least one match found in db_path
                best_match = df_result.iloc[0] # Closest match
                identity_path = best_match['identity'] # Path to matched image in db_path
                
                # Extract filename from identity_path
                matched_filename = os.path.basename(identity_path)

                student_info = STUDENT_IMAGE_MAP.get(matched_filename)

                # Get bounding box of the detected face in the source image (frame_bgr)
                source_x = int(best_match['source_x'])
                source_y = int(best_match['source_y'])
                source_w = int(best_match['source_w'])
                source_h = int(best_match['source_h'])
                current_face_box = (source_y, source_x + source_w, source_y + source_h, source_x) # top, right, bottom, left

                if student_info:
                    name = student_info["name"]
                    student_id_recognized = student_info["id"]
                    student_id_number_recognized = student_info["student_id_number"]

                    if student_id_recognized in registered_student_ids_for_exam:
                        recognition_status = "Verified_Eligible"
                    else:
                        recognition_status = "Verified_Not_Eligible"

                    _log_student_attendance(student_id_recognized, exam_id, name, recognition_status)

                    detected_faces_data.append({
                        'name': name,
                        'student_id': student_id_recognized,
                        'student_id_number': student_id_number_recognized,
                        'box': current_face_box,
                        'status': recognition_status
                    })
                else: # Match found by DeepFace, but filename not in our STUDENT_IMAGE_MAP (should not happen if map is current)
                    current_app.logger.warning(f"DeepFace matched {matched_filename}, but not found in STUDENT_IMAGE_MAP.")
                    detected_faces_data.append({
                        'name': 'ErrorMap', # Indicates a mapping error
                        'student_id': None,
                        'student_id_number': None,
                        'box': current_face_box,
                        'status': 'Error_Student_Map'
                    })
            else:
                # This block might not be reached if DeepFace.find returns empty list for no faces,
                # or list of empty dataframes if faces detected but not matched.
                # We need a reliable way to get boxes of UNKNOWN faces.
                # The most robust way is to use extract_faces first, then for each face, try to verify/find.
                # For now, this path for "unknown from find" is less clear.
                # Let's rely on the initial all_detected_in_frame and post-process to find those not matched.
                pass


        # Post-processing: Identify unknown faces by comparing boxes from extract_faces and recognized faces
        # This is to ensure we draw boxes for faces that were detected but not recognized.
        # We need to get the bounding boxes of faces that DeepFace.find processed.
        # The `recognition_results_list` contains DataFrames. Each DF, if non-empty, has source_x,y,w,h.
        
        # Create a list of boxes for faces that were recognized
        recognized_boxes = [d['box'] for d in detected_faces_data] # (top, right, bottom, left)

        # Iterate through all initially detected faces by extract_faces
        for face_info in all_detected_in_frame:
            if face_info['confidence'] == 0: continue
            x, y, w, h = face_info['facial_area']['x'], face_info['facial_area']['y'], face_info['facial_area']['w'], face_info['facial_area']['h']
            extracted_box = (y, x + w, y + h, x) # top, right, bottom, left

            is_recognized = False
            for rec_box in recognized_boxes:
                # Check if this extracted_box substantially overlaps with a recognized_box
                # Simple IoU or center proximity check could be used. For now, direct match or close center.
                iou_threshold = 0.5

                # Calculate Intersection over Union (IoU)
                xA = max(extracted_box[3], rec_box[3]) # max of lefts
                yA = max(extracted_box[0], rec_box[0]) # max of tops
                xB = min(extracted_box[1], rec_box[1]) # min of rights
                yB = min(extracted_box[2], rec_box[2]) # min of bottoms

                interArea = max(0, xB - xA) * max(0, yB - yA)
                if interArea == 0: continue

                boxA_area = (extracted_box[1] - extracted_box[3]) * (extracted_box[2] - extracted_box[0])
                boxB_area = (rec_box[1] - rec_box[3]) * (rec_box[2] - rec_box[0])

                current_iou = interArea / float(boxA_area + boxB_area - interArea)

                if current_iou > iou_threshold:
                    is_recognized = True
                    break

            if not is_recognized:
                detected_faces_data.append({
                    'name': 'Unknown',
                    'student_id': None,
                    'student_id_number': None,
                    'box': extracted_box,
                    'status': 'Unknown_Student'
                })

    except Exception as e:
        current_app.logger.error(f"Error in DeepFace recognition or processing: {e}", exc_info=True)
        # Fallback: detect faces and mark all as unknown if recognition fails badly
        # This part is similar to the above 'no known faces' block.
        detected_faces_data = [] # Clear any partial data
        try:
            detected_raw_faces = DeepFace.extract_faces(
                img_path=frame_bgr.copy(), detector_backend=DEEPFACE_DETECTOR_BACKEND, enforce_detection=False, align=False
            )
            for face_info in detected_raw_faces:
                if face_info['confidence'] > 0:
                    x, y, w, h = face_info['facial_area']['x'], face_info['facial_area']['y'], face_info['facial_area']['w'], face_info['facial_area']['h']
                    box = (y, x + w, y + h, x)
                    detected_faces_data.append({'name': 'Unknown', 'student_id': None, 'student_id_number': None, 'box': box, 'status': 'Unknown_Student_ErrorInRecognition'})
        except Exception as det_e:
            current_app.logger.error(f"Error during fallback face detection: {det_e}")

    return detected_faces_data

def _log_student_attendance(student_id, exam_id, student_name_for_log, status_to_log):
    """
    Internal helper to log student attendance if not logged recently for the given exam,
    with the determined status.
    Returns True if logged, False otherwise.
    """
    global RECENTLY_LOGGED_STUDENTS
    now = datetime.utcnow()

    if exam_id not in RECENTLY_LOGGED_STUDENTS:
        RECENTLY_LOGGED_STUDENTS[exam_id] = {}

    last_log_time = RECENTLY_LOGGED_STUDENTS[exam_id].get(student_id)

    if last_log_time is None or (now - last_log_time) > timedelta(seconds=LOG_COOLDOWN_SECONDS):
        try:
            log_entry = Log(student_id=student_id, exam_id=exam_id, timestamp=now, status=status_to_log)
            db.session.add(log_entry)
            db.session.commit()
            RECENTLY_LOGGED_STUDENTS[exam_id][student_id] = now
            if current_app:
                current_app.logger.info(f"Attendance logged for {student_name_for_log} (ID: {student_id}) for Exam ID: {exam_id} with status: {status_to_log}.")
            return True
        except Exception as e:
            db.session.rollback()
            if current_app:
                current_app.logger.error(f"Error logging attendance for Student {student_name_for_log} (ID: {student_id}), Status: {status_to_log}: {e}")
            return False
    return False

def get_active_or_upcoming_exams():
    """Returns a list of exams that are upcoming today or currently active (simplified)."""
    today = datetime.utcnow().date()
    return Exam.query.filter(Exam.date >= today).order_by(Exam.date, Exam.start_time).all()

def clear_face_cache():
    """
    This function is now less about an in-memory embedding cache and more about
    potentially clearing or refreshing the STUDENT_IMAGE_MAP if needed,
    though load_known_faces_from_db already rebuilds it.
    For now, it can simply log that a refresh logic might occur here if extended.
    """
    global STUDENT_IMAGE_MAP
    STUDENT_IMAGE_MAP = {} # Clear the map, will be repopulated on next load_known_faces_from_db call
    if current_app:
        current_app.logger.info("Student image map cache cleared. Will be repopulated on next access.")
    else:
        print("(No app context) Student image map cache cleared.")


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