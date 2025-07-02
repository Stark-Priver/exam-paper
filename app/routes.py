from flask import Blueprint, render_template, redirect, url_for, flash, request, Response, current_app, send_from_directory
from flask_login import login_user, logout_user, login_required, current_user
from app.models import User, Student, Exam, Log
from app.forms import LoginForm, StudentForm, ExamForm
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
import cv2 # For OpenCV
import numpy as np
# import face_recognition # Already used in face_rec_utils & utils

bp = Blueprint('main', __name__)

# Global camera object. Handled by initialize_camera and release_camera.
camera = None 

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
        image_filename, embedding_or_error = process_student_image(photo_file, form.student_id_number.data)

        if image_filename is None: # Error occurred or no face found
            flash(f'Could not process image: {embedding_or_error}', 'danger')
        else:
            student = Student(
                student_id_number=form.student_id_number.data,
                name=form.name.data,
                face_image_path=image_filename,
                face_embedding=embedding_or_error # This is the actual embedding
            )
            db.session.add(student)
            db.session.commit()
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
            recognized_data = find_and_log_recognized_faces(rgb_frame, exam_id) # This util uses current_app.logger internally

            for data in recognized_data:
                top, right, bottom, left = data['box']
                name = data['name']
                student_id = data['student_id']
                color = (0, 255, 0) if student_id else (0, 0, 255)
                cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
                cv2.rectangle(frame, (left, bottom - 25), (right, bottom), color, cv2.FILLED)
                font = cv2.FONT_HERSHEY_DUPLEX
                cv2.putText(frame, name, (left + 6, bottom - 6), font, 0.8, (255, 255, 255), 1)

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
    return {"status": "success", "message": "Camera released."}, 200

# --- Log Viewing Route ---
@bp.route('/view_logs')
@login_required
def view_logs():
    page = request.args.get('page', 1, type=int)
    
    query = db.session.query(
        Log.id.label('log_id'),
        Log.timestamp,
        Log.status,
        Student.name.label('student_name'),
        Student.student_id_number,
        Exam.subject.label('exam_subject'),
        Exam.date.label('exam_date')
    ).join(Student, Log.student_id == Student.id).join(Exam, Log.exam_id == Exam.id)

    logs_page = query.order_by(Log.timestamp.desc()).paginate(page=page, per_page=15)
    
    return render_template(
        'view_logs.html', 
        title="Authentication Logs", 
        logs_page=logs_page
    )