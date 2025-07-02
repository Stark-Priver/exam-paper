from flask import Blueprint, render_template, redirect, url_for, flash, request, Response, current_app, send_from_directory
from flask_login import login_user, logout_user, login_required, current_user
from app.models import User, Student, Exam, Log, exam_registrations
from app.forms import LoginForm, StudentForm, ExamForm, ExamRegistrationForm
from app import db
from app.utils import process_student_image, remove_student_image
from app.face_rec_utils import (
    load_known_faces_from_db, 
    find_and_log_recognized_faces, 
    get_active_or_upcoming_exams,
    clear_face_cache,
    clear_recent_logs_cache
)
import os
import logging # Added for fallback logger
from datetime import datetime, timedelta
import cv2 # For OpenCV
import numpy as np
# import face_recognition # Already used in face_rec_utils & utils
import base64
import io

bp = Blueprint('main', __name__)

# Global camera object. Handled by initialize_camera and release_camera.
camera = None 

# Dictionary to store the latest recognition status for each active exam session
# Not suitable for multi-worker production environments without a proper shared cache (e.g., Redis, Memcached)
# For simplicity in this context, we'll use a global dict.
# Structure: {exam_id: {"name": "Student Name", "status": "StatusString", "timestamp": datetime}}
LATEST_RECOGNITION_STATUS = {}
RECOGNITION_STATUS_TTL_SECONDS = 10 # How long to keep a status before considering it stale

@bp.route('/uploads/<path:filename>')
def uploaded_file(filename):
    upload_dir = current_app.config['UPLOAD_FOLDER']
    return send_from_directory(upload_dir, filename)

def initialize_camera(logger_instance):
    """
    Initializes the global camera object if not already initialized.
    Tries common camera indices (0, -1, 1, 2).
    Logs success or failure using the provided logger instance.
    Returns:
        bool: True if camera is initialized or was already initialized, False on failure.
    """
    global camera
    if camera is None:
        camera_indices_to_try = [0, -1, 1, 2] # Common indices
        for index in camera_indices_to_try:
            cap = None # Initialize cap here for safety in except block
            try:
                logger_instance.info(f"Attempting to initialize camera at index {index}...")
                cap = cv2.VideoCapture(index)
                if cap and cap.isOpened(): # Check if cap is not None before cap.isOpened()
                    camera = cap
                    logger_instance.info(f"Camera initialized successfully at index {index}.")
                    # Optional: Set camera properties for performance/consistency
                    # camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                    # camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                    # camera.set(cv2.CAP_PROP_FPS, 15) # Lower FPS can reduce CPU load
                    return True
                elif cap: # If cap was created but not opened
                    cap.release()
            except Exception as e:
                logger_instance.error(f"Exception trying to open camera at index {index}: {e}")
                if cap: 
                    cap.release()
        logger_instance.error("All default camera indices failed. Camera could not be initialized.")
        camera = None # Ensure camera is None if all attempts fail
        return False
    return True # Camera was already initialized

def release_camera(logger_instance):
    """
    Releases the global camera object if it's currently initialized.
    Also clears face recognition caches associated with a live session.
    Uses the provided logger instance.
    """
    global camera
    if camera is not None:
        logger_instance.info("Releasing camera resource.")
        camera.release()
        camera = None
        # Clear caches as they are relevant to a live camera session
        clear_face_cache() 
        clear_recent_logs_cache() # Clears all recently logged students across exams
        logger_instance.info("Face cache and recent logs cache cleared.")

# --- Standard Admin Routes (Login, Dashboard etc.) ---
@bp.route('/')
@bp.route('/index')
@login_required
def index():
    return render_template('admin_dashboard.html', title='Admin Dashboard')

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember_me.data)
            next_page = request.args.get('next')
            flash('Login Successful!', 'success')
            return redirect(next_page) if next_page else redirect(url_for('main.index'))
        else:
            flash('Login Unsuccessful. Please check username and password', 'danger')
    return render_template('login.html', title='Login', form=form)


@bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('main.login'))

# --- Student Management Routes ---
@bp.route('/manage_students')
@login_required
def manage_students():
    students = Student.query.order_by(Student.name).all()
    return render_template('manage_students.html', students=students, title="Manage Students")

@bp.route('/add_student', methods=['GET', 'POST'])
@login_required
def add_student():
    form = StudentForm()
    if form.validate_on_submit():
        photo_file = form.photo.data
        captured_image_data_b64 = request.form.get('captured_image_data')

        image_to_process = None
        image_source_type = None # 'fileupload' or 'capture'

        if captured_image_data_b64 and captured_image_data_b64.startswith('data:image/jpeg;base64,'):
            base64_data = captured_image_data_b64.split(',')[1]
            try:
                image_bytes = base64.b64decode(base64_data)
                image_to_process = io.BytesIO(image_bytes)
                image_source_type = 'capture'
            except Exception as e:
                flash(f'Error decoding captured image: {str(e)}', 'danger')
                return render_template('add_student.html', title='Add Student', form=form)
        elif photo_file and photo_file.filename:
            image_to_process = photo_file
            image_source_type = 'fileupload'

        if not image_to_process:
            flash('No photo provided. Please upload a file or capture a photo.', 'danger')
            return render_template('add_student.html', title='Add Student', form=form)

        # Construct a filename for the captured image if it's from BytesIO
        # process_student_image will expect a filename if it's saving the file.
        # We can pass the source_type to process_student_image if it needs to handle BytesIO differently.
        # For now, process_student_image is expected to be adapted (next step).

        # If image_to_process is BytesIO, we might need to give it a pseudo-filename
        # or the process_student_image function needs to handle it.
        # Let's assume process_student_image will be adapted to handle BytesIO directly
        # and generate its own filename for captures.

        image_filename, embedding_or_error = process_student_image(
            image_to_process,
            form.student_id_number.data,
            source_type=image_source_type # Pass source_type for context
        )

        if image_filename is None:
            flash(f'Could not process image: {embedding_or_error}', 'danger')
        else:
            student = Student(
                student_id_number=form.student_id_number.data,
                name=form.name.data,
                face_image_path=image_filename,
                face_embedding=embedding_or_error
            )
            db.session.add(student)
            db.session.commit()
            clear_face_cache() # Ensure the new student is loaded on next recognition
            flash('Student added successfully with face data!', 'success')
            return redirect(url_for('main.manage_students'))
            
    return render_template('add_student.html', title='Add Student', form=form)

@bp.route('/edit_student/<int:student_id>', methods=['GET', 'POST'])
@login_required
def edit_student(student_id):
    student = Student.query.get_or_404(student_id)
    form = StudentForm(original_student_id_number=student.student_id_number)

    if form.validate_on_submit():
        if student.student_id_number != form.student_id_number.data:
            existing_student = Student.query.filter_by(student_id_number=form.student_id_number.data).first()
            if existing_student:
                flash('That Student ID Number is already taken by another student.', 'danger')
                return render_template('edit_student.html', title='Edit Student', form=form, student=student)
        
        student.name = form.name.data
        student.student_id_number = form.student_id_number.data
        
        if form.photo.data: 
            if student.face_image_path:
                remove_student_image(student.face_image_path)
            
            image_filename, embedding_or_error = process_student_image(form.photo.data, student.student_id_number)
            if image_filename:
                student.face_image_path = image_filename
                student.face_embedding = embedding_or_error
                flash('Student details and photo updated successfully!', 'success')
            else:
                flash(f'Could not process new image: {embedding_or_error}. Student details (except photo) updated.', 'warning')
        else:
            flash('Student details updated successfully (photo unchanged).', 'success')
            
        db.session.commit()
        return redirect(url_for('main.manage_students'))

    elif request.method == 'GET':
        form.name.data = student.name
        form.student_id_number.data = student.student_id_number

    return render_template('edit_student.html', title='Edit Student', form=form, student=student)

@bp.route('/delete_student/<int:student_id>', methods=['POST'])
@login_required
def delete_student(student_id):
    student = Student.query.get_or_404(student_id)
    if student.face_image_path:
        remove_student_image(student.face_image_path)
    db.session.delete(student)
    db.session.commit()
    flash('Student deleted successfully.', 'success')
    return redirect(url_for('main.manage_students'))

# --- Exam Management Routes ---
@bp.route('/manage_exams')
@login_required
def manage_exams():
    exams = Exam.query.order_by(Exam.date.desc(), Exam.start_time.desc()).all()
    return render_template('manage_exams.html', exams=exams, title="Manage Exams")

@bp.route('/add_exam', methods=['GET', 'POST'])
@login_required
def add_exam():
    form = ExamForm()
    if form.validate_on_submit():
        exam = Exam(
            subject=form.subject.data,
            date=form.date.data,
            start_time=form.start_time.data,
            end_time=form.end_time.data
        )
        db.session.add(exam)
        db.session.commit()
        flash('Exam created successfully!', 'success')
        return redirect(url_for('main.manage_exams'))
    return render_template('add_exam.html', title='Add Exam', form=form)

@bp.route('/edit_exam/<int:exam_id>', methods=['GET', 'POST'])
@login_required
def edit_exam(exam_id):
    exam = Exam.query.get_or_404(exam_id)
    form = ExamForm(obj=exam) 

    if form.validate_on_submit():
        exam.subject = form.subject.data
        exam.date = form.date.data
        exam.start_time = form.start_time.data
        exam.end_time = form.end_time.data
        db.session.commit()
        flash('Exam updated successfully!', 'success')
        return redirect(url_for('main.manage_exams'))
    
    return render_template('edit_exam.html', title='Edit Exam', form=form, exam=exam)

@bp.route('/delete_exam/<int:exam_id>', methods=['POST'])
@login_required
def delete_exam(exam_id):
    exam = Exam.query.get_or_404(exam_id)
    Log.query.filter_by(exam_id=exam.id).delete()
    db.session.delete(exam)
    db.session.commit()
    flash('Exam and associated logs deleted successfully.', 'success')
    return redirect(url_for('main.manage_exams'))

@bp.route('/manage_exam_registrations/<int:exam_id>', methods=['GET', 'POST'])
@login_required
def manage_exam_registrations(exam_id):
    exam = Exam.query.get_or_404(exam_id)
    form = ExamRegistrationForm()

    if form.validate_on_submit():
        # Clear existing registrations for this exam
        exam.registered_students = []

        student_id_numbers_str = form.students.data
        student_id_numbers_list = [sid.strip() for sid in student_id_numbers_str.split(',') if sid.strip()]

        not_found_students = []
        registered_count = 0

        for sid_num in student_id_numbers_list:
            student = Student.query.filter_by(student_id_number=sid_num).first()
            if student:
                exam.registered_students.append(student)
                registered_count += 1
            else:
                not_found_students.append(sid_num)

        db.session.commit()

        if not_found_students:
            flash(f'Successfully registered {registered_count} students. Could not find students with ID numbers: {", ".join(not_found_students)}.', 'warning')
        else:
            flash(f'Successfully registered {registered_count} students for the exam: {exam.subject}.', 'success')
        return redirect(url_for('main.manage_exam_registrations', exam_id=exam_id))

    elif request.method == 'GET':
        # Populate form with currently registered students
        form.students.data = ", ".join([s.student_id_number for s in exam.registered_students])

    all_students = Student.query.order_by(Student.name).all() # For display or a selection helper
    return render_template('manage_exam_registrations.html', title=f"Manage Registrations for {exam.subject}",
                           exam=exam, form=form, all_students=all_students)


# --- Facial Recognition and Authentication Routes ---

@bp.route('/refresh_face_cache', methods=['POST'])
@login_required
def refresh_face_cache():
    # Make sure to use the app's logger, not current_app.logger directly if not in request context
    # However, this is a route, so current_app.logger should be fine.
    count = load_known_faces_from_db() 
    clear_recent_logs_cache()
    if count > 0:
        return {"status": "success", "message": f"Known faces cache refreshed. {count} faces loaded.", "faces_loaded": count}, 200
    else:
        return {"status": "warning", "message": "No faces found in DB or error loading.", "faces_loaded": 0}, 200


@bp.route('/select_exam_for_auth')
@login_required
def select_exam_for_auth():
    exams = get_active_or_upcoming_exams()
    return render_template('select_exam_for_auth.html', exams=exams, title="Select Exam")

def generate_frames(exam_id):
    """
    Generator function for video streaming.
    Captures frames, performs face recognition, draws annotations, and yields JPEG frames.
    """
    global camera
    # It's crucial to get a logger instance that's safe to use within a generator
    # that might outlive a single request context if not careful.
    # current_app._get_current_object() provides the actual app instance.
    app_instance = current_app._get_current_object()
    logger = app_instance.logger
    
    if not initialize_camera(logger) or camera is None: 
        logger.error("Camera not initialized for generate_frames.")
        img = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.putText(img, "Camera Error", (50, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (255,255,255), 2)
        _, buffer = cv2.imencode('.jpg', img)
        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        return

    logger.info(f"Starting frame generation for exam ID: {exam_id}")
    frame_skip = 0 
    frame_count = 0

    while True:
        try:
            success, frame = camera.read()
            if not success:
                logger.warning("Failed to grab frame from camera.")
                break 
            
            frame_count += 1
            if frame_skip > 0 and frame_count % (frame_skip + 1) != 1:
                _, buffer = cv2.imencode('.jpg', frame)
                raw_frame_bytes = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + raw_frame_bytes + b'\r\n')
                continue

            rgb_frame = frame[:, :, ::-1]
            
            # Use app_instance for context if needed by find_and_log_recognized_faces
            # or ensure find_and_log_recognized_faces uses its own logger or passed logger
            recognized_data_list = find_and_log_recognized_faces(rgb_frame, exam_id) # This util uses current_app.logger internally

            # Update LATEST_RECOGNITION_STATUS with the most relevant status
            # For simplicity, if multiple faces, pick the first "interesting" one (not just unknown)
            # or the first one if all are unknown.
            primary_status_to_report = None
            if recognized_data_list:
                # Prioritize non-unknown students
                eligible_or_not_eligible = [d for d in recognized_data_list if d['status'] != 'Unknown_Student' and d['student_id'] is not None]
                if eligible_or_not_eligible:
                    primary_status_to_report = eligible_or_not_eligible[0]
                else: # All are unknown or errors
                    primary_status_to_report = recognized_data_list[0]

                if primary_status_to_report:
                    LATEST_RECOGNITION_STATUS[exam_id] = {
                        "name": primary_status_to_report['name'],
                        "status": primary_status_to_report['status'],
                        # student_id_number is now directly available from find_and_log_recognized_faces
                        "student_id_number": primary_status_to_report.get('student_id_number'),
                        "timestamp": datetime.utcnow()
                    }

            # Add a comment explaining the primary_status_to_report logic
            # The primary_status_to_report aims to show the most "important" face status if multiple faces are detected.
            # It prioritizes known students (eligible or not) over unknown faces for the summary status.
            for data in recognized_data_list:
                top, right, bottom, left = data['box']
                name_display = data['name']
                status_display = data['status'] # e.g. Verified_Eligible, Unknown_Student

                # Determine color based on status
                if status_display == 'Verified_Eligible':
                    color = (0, 255, 0)  # Green
                    name_prefix = ""
                elif status_display == 'Verified_Not_Eligible':
                    color = (0, 0, 255)  # Red
                    name_prefix = "NOT ELIGIBLE: "
                elif status_display == 'Unknown_Student':
                    color = (0, 165, 255) # Orange for unknown
                    name_prefix = "UNKNOWN: "
                else: # Error or other states
                    color = (255, 0, 255) # Magenta for errors
                    name_prefix = "ERROR: "

                cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
                cv2.rectangle(frame, (left, bottom - 25), (right, bottom), color, cv2.FILLED)
                font = cv2.FONT_HERSHEY_DUPLEX
                cv2.putText(frame, f"{name_prefix}{name_display}", (left + 6, bottom - 6), font, 0.6, (255, 255, 255), 1)

            ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            if not ret:
                logger.error("cv2.imencode failed")
                continue
            frame_bytes = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        except Exception as e:
            logger.error(f"Error in generate_frames loop: {e}", exc_info=True)
            break # Exit loop on error to prevent broken pipe or other issues
    
    logger.info(f"generate_frames loop ended for exam ID: {exam_id}.")

@bp.route('/live_auth/<int:exam_id>')
@login_required
def live_auth(exam_id):
    """Route to display the live authentication page for a specific exam."""
    exam = Exam.query.get_or_404(exam_id)
    
    # Ensure app context for DB operations and logging
    with current_app.app_context():
        faces_loaded_count = load_known_faces_from_db()
        if faces_loaded_count == 0:
            flash('No student face data found in the database. Please register students with photos.', 'warning')
        else:
            flash(f'{faces_loaded_count} student face profiles loaded for recognition.', 'info')
        clear_recent_logs_cache(exam_id=exam_id)
    
    return render_template('live_auth.html', exam=exam, title=f"Live Auth: {exam.subject}")

@bp.route('/video_feed/<int:exam_id>')
@login_required
def video_feed(exam_id):
    """Provides the video stream for a given exam ID."""
    exam = Exam.query.get_or_404(exam_id) 
    return Response(generate_frames(exam_id=exam.id),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@bp.route('/stop_video_feed', methods=['POST'])
@login_required
def stop_video_feed():
    """Endpoint to explicitly stop the camera and release resources."""
    # Use current_app.logger as this is a direct request context
    release_camera(current_app.logger) 
    flash("Camera session ended and resources released.", "info")

    exam_id_to_clear = None
    if request.is_json:
        data = request.get_json()
        if data:
            exam_id_to_clear = data.get('exam_id')
    elif request.form: # Fallback if it was sent as form data for some reason
        exam_id_to_clear = request.form.get('exam_id')

    if exam_id_to_clear:
        try:
            # Ensure exam_id_to_clear is an integer if it comes from JSON as string
            LATEST_RECOGNITION_STATUS.pop(int(exam_id_to_clear), None)
            logger_instance = current_app.logger if current_app else logging.getLogger(__name__)
            logger_instance.info(f"Cleared LATEST_RECOGNITION_STATUS for exam_id: {exam_id_to_clear}")
        except ValueError:
            logger_instance = current_app.logger if current_app else logging.getLogger(__name__)
            logger_instance.warning(f"Could not parse exam_id '{exam_id_to_clear}' to int for clearing status.")

    return {"status": "success", "message": "Camera released."}, 200

@bp.route('/live_auth_status/<int:exam_id>')
@login_required
def live_auth_status(exam_id):
    """Endpoint for the frontend to poll for the latest recognition status."""
    status_info = LATEST_RECOGNITION_STATUS.get(exam_id)

    if status_info:
        # Check if the status is stale
        if (datetime.utcnow() - status_info.get("timestamp", datetime.min)) > timedelta(seconds=RECOGNITION_STATUS_TTL_SECONDS):
            # If stale, remove it and report no current status
            LATEST_RECOGNITION_STATUS.pop(exam_id, None)
            return {"status": "NoDetection", "name": None, "student_id_number": None}, 200

        return {
            "name": status_info.get("name", "Unknown"),
            "status": status_info.get("status", "Unknown_Student"),
            "student_id_number": status_info.get("student_id_number", None)
        }, 200
    else:
        # No status recorded yet for this exam, or it was cleared/stale
        return {"status": "NoDetection", "name": None, "student_id_number": None}, 200

# --- Log Viewing Route ---
@bp.route('/view_logs')
@login_required
def view_logs():
    page = request.args.get('page', 1, type=int)
    sort_by = request.args.get('sort_by', 'timestamp')
    sort_order = request.args.get('sort_order', 'desc')

    # Define valid sortable columns to prevent arbitrary column sorting
    sortable_columns = {
        'log_id': Log.id,
        'student_name': Student.name,
        'student_id_number': Student.student_id_number,
        'exam_subject': Exam.subject,
        'exam_date': Exam.date,
        'timestamp': Log.timestamp,
        'status': Log.status
    }

    if sort_by not in sortable_columns:
        sort_by = 'timestamp' # Default sort column

    sort_column = sortable_columns[sort_by]

    # Base query
    query = db.session.query(
        Log.id.label('log_id'),
        Log.timestamp,
        Log.status,
        Student.name.label('student_name'),
        Student.student_id_number,
        Exam.subject.label('exam_subject'),
        Exam.date.label('exam_date')
    ).join(Student, Log.student_id == Student.id).join(Exam, Log.exam_id == Exam.id)

    # Apply sorting
    if sort_order == 'asc':
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc()) # Default to desc

    # Filtering (keeping existing filter logic if any, or add as needed)
    filter_date_str = request.args.get('filter_date')
    filter_exam_id = request.args.get('filter_exam_id')
    filter_student_id = request.args.get('filter_student_id')

    available_exams = Exam.query.order_by(Exam.subject).all()
    available_students = Student.query.order_by(Student.name).all()

    if filter_date_str:
        try:
            filter_date = datetime.strptime(filter_date_str, '%Y-%m-%d').date()
            query = query.filter(Exam.date == filter_date)
        except ValueError:
            flash('Invalid date format for filter. Please use YYYY-MM-DD.', 'warning')

    if filter_exam_id:
        query = query.filter(Exam.id == filter_exam_id)

    if filter_student_id:
        query = query.filter(Student.id == filter_student_id)


    logs_page = query.paginate(page=page, per_page=15)
    
    return render_template(
        'view_logs.html', 
        title="Authentication Logs", 
        logs_page=logs_page,
        sort_by=sort_by,
        sort_order=sort_order,
        available_exams=available_exams, # Pass for filter dropdown
        available_students=available_students # Pass for filter dropdown
    )