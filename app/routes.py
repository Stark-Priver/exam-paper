from flask import Blueprint, render_template, redirect, url_for, flash, request, Response, current_app
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

def initialize_camera():
    """
    Initializes the global camera object if not already initialized.
    Tries common camera indices (0, -1, 1).
    Logs success or failure.
    Returns:
        bool: True if camera is initialized or was already initialized, False on failure.
    """
    global camera
    if camera is None:
        camera_indices_to_try = [0, -1, 1, 2] # Common indices
        for index in camera_indices_to_try:
            try:
                current_app.logger.info(f"Attempting to initialize camera at index {index}...")
                cap = cv2.VideoCapture(index)
                if cap.isOpened():
                    camera = cap
                    current_app.logger.info(f"Camera initialized successfully at index {index}.")
                    # Optional: Set camera properties for performance/consistency
                    # camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                    # camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                    # camera.set(cv2.CAP_PROP_FPS, 15) # Lower FPS can reduce CPU load
                    return True
            except Exception as e:
                current_app.logger.error(f"Exception trying to open camera at index {index}: {e}")
                if cap: # Ensure it's released if opened but then failed
                    cap.release()
        current_app.logger.error("All default camera indices failed. Camera could not be initialized.")
        camera = None # Ensure camera is None if all attempts fail
        return False
    return True # Camera was already initialized

def release_camera():
    """
    Releases the global camera object if it's currently initialized.
    Also clears face recognition caches associated with a live session.
    """
    global camera
    if camera is not None:
        current_app.logger.info("Releasing camera resource.")
        camera.release()
        camera = None
        # Clear caches as they are relevant to a live camera session
        clear_face_cache()
        clear_recent_logs_cache() # Clears all recently logged students across exams
        current_app.logger.info("Face cache and recent logs cache cleared.")

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

# Student Management Routes
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
        # Check if student ID number is being changed and if it's unique
        if student.student_id_number != form.student_id_number.data:
            existing_student = Student.query.filter_by(student_id_number=form.student_id_number.data).first()
            if existing_student:
                flash('That Student ID Number is already taken by another student.', 'danger')
                return render_template('edit_student.html', title='Edit Student', form=form, student=student)

        student.name = form.name.data
        student.student_id_number = form.student_id_number.data

        if form.photo.data: # If a new photo was uploaded
            # Remove old image first
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
        # Photo field is not pre-filled, user uploads a new one if they want to change it

    return render_template('edit_student.html', title='Edit Student', form=form, student=student)

@bp.route('/delete_student/<int:student_id>', methods=['POST']) # Should be POST for deletion
@login_required
def delete_student(student_id):
    student = Student.query.get_or_404(student_id)
    if student.face_image_path:
        remove_student_image(student.face_image_path)
    db.session.delete(student)
    db.session.commit()
    flash('Student deleted successfully.', 'success')
    return redirect(url_for('main.manage_students'))

# Exam Management Routes
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
    form = ExamForm(obj=exam) # Pre-populate form with exam data

    if form.validate_on_submit():
        exam.subject = form.subject.data
        exam.date = form.date.data
        exam.start_time = form.start_time.data
        exam.end_time = form.end_time.data
        db.session.commit()
        flash('Exam updated successfully!', 'success')
        return redirect(url_for('main.manage_exams'))

    # For GET request, form is already populated by obj=exam
    # If WTForms < 2.1, you might need:
    # elif request.method == 'GET':
    #     form.subject.data = exam.subject
    #     form.date.data = exam.date
    #     form.start_time.data = exam.start_time
    #     form.end_time.data = exam.end_time

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

# Facial Recognition and Authentication Routes

@bp.route('/refresh_face_cache', methods=['POST'])
@login_required
def refresh_face_cache():
    count = load_known_faces_from_db()
    # Also clear recent logs for all exams as faces might have changed
    clear_recent_logs_cache()
    if count > 0:
        return {"status": "success", "message": f"Known faces cache refreshed. {count} faces loaded.", "faces_loaded": count}, 200
    else:
        return {"status": "warning", "message": "No faces found in DB or error loading.", "faces_loaded": 0}, 200


@bp.route('/select_exam_for_auth')
@login_required
def select_exam_for_auth():
    # Release camera if it was somehow left open from a previous session
    # release_camera() # Better to release when navigating away from live_auth page
    exams = get_active_or_upcoming_exams()
    return render_template('select_exam_for_auth.html', exams=exams, title="Select Exam")

def generate_frames(exam_id):
    global camera
    if not initialize_camera() or camera is None:
        current_app.logger.error("Camera not initialized for generate_frames.")
        # Yield a placeholder image or error message
        img = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.putText(img, "Camera Error", (50, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (255,255,255), 2)
        _, buffer = cv2.imencode('.jpg', img)
        frame = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        return

    frame_skip = 0 # Process every Nth frame; 0 for no skip
    frame_count = 0

    while True:
        success, frame = camera.read()
        if not success:
            current_app.logger.warning("Failed to grab frame from camera.")
            # Could try to re-initialize camera here, or just break
            # For now, let's break. User might need to restart session.
            break

        frame_count += 1
        if frame_skip > 0 and frame_count % (frame_skip + 1) != 1:
            # Encode and yield the raw frame without processing if skipping
            _, buffer = cv2.imencode('.jpg', frame)
            raw_frame_bytes = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + raw_frame_bytes + b'\r\n')
            continue

        # Convert the image from BGR color (which OpenCV uses) to RGB color
        rgb_frame = frame[:, :, ::-1]

        # Find faces and log them (logging happens inside this function)
        # recognized_data is a list: [{'name': str, 'student_id': int/None, 'box': (t,r,b,l)}, ...]
        recognized_data = find_and_log_recognized_faces(rgb_frame, exam_id)

        # Draw rectangles and names on the original BGR frame
        for data in recognized_data:
            top, right, bottom, left = data['box']
            name = data['name']
            student_id = data['student_id']

            color = (0, 255, 0) if student_id else (0, 0, 255) # Green for known, Red for unknown

            # Draw a box around the face
            cv2.rectangle(frame, (left, top), (right, bottom), color, 2)

            # Draw a label with a name below the face
            cv2.rectangle(frame, (left, bottom - 25), (right, bottom), color, cv2.FILLED)
            font = cv2.FONT_HERSHEY_DUPLEX
            cv2.putText(frame, name, (left + 6, bottom - 6), font, 0.8, (255, 255, 255), 1)

            # Optional: Display a temporary "Welcome" message on screen for verified users
            # This is tricky to manage statefully across frames in a simple way here.
            # Better to rely on the log and maybe a separate notification system if needed.

        # Encode the frame in JPEG format
        try:
            ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70]) # Quality 0-100
            if not ret:
                current_app.logger.error("cv2.imencode failed")
                continue
            frame_bytes = buffer.tobytes()
        except Exception as e:
            current_app.logger.error(f"Error encoding frame: {e}")
            continue

        # Yield the output frame in the byte format
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

    current_app.logger.info("generate_frames loop ended. Releasing camera in this context if needed.")
    # release_camera() # Releasing camera here might be too soon if live_auth page is still active
                     # Or if user navigates away and back. Better to manage camera release carefully.


@bp.route('/live_auth/<int:exam_id>')
@login_required
def live_auth(exam_id):
    exam = Exam.query.get_or_404(exam_id)

    # Load known faces from DB into cache when starting a session for this exam
    # This populates CACHED_KNOWN_FACES in face_rec_utils
    faces_loaded_count = load_known_faces_from_db()
    if faces_loaded_count == 0:
        flash('No student face data found in the database. Please register students with photos.', 'warning')
    else:
        flash(f'{faces_loaded_count} student face profiles loaded for recognition.', 'info')

    # Clear any "recently logged" data for this specific exam session when starting
    clear_recent_logs_cache(exam_id=exam_id)

    # initialize_camera() should be called before generate_frames is used by video_feed
    # It's implicitly called by generate_frames if camera is None

    return render_template('live_auth.html', exam=exam, title=f"Live Auth: {exam.subject}")

@bp.route('/video_feed/<int:exam_id>')
@login_required
def video_feed(exam_id):
    # Video streaming route. This will be called by the <img> tag.
    # Ensure exam_id is valid if necessary, though live_auth already checks.
    exam = Exam.query.get_or_404(exam_id) # Ensure exam context
    if not exam:
         # This case should ideally not be hit if live_auth is the entry point
        return "Exam not found", 404

    return Response(generate_frames(exam_id),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@bp.route('/stop_video_feed', methods=['POST'])
@login_required
def stop_video_feed():
    # This route can be called by JavaScript when navigating away from live_auth page
    # or explicitly by a "stop session" button.
    release_camera()
    flash("Camera session ended and resources released.", "info")
    return {"status": "success", "message": "Camera released."}, 200

# Log Viewing Route
@bp.route('/view_logs')
@login_required
def view_logs():
    page = request.args.get('page', 1, type=int)

    # Base query - select specific columns to be more explicit and potentially efficient
    query = db.session.query(
        Log.id.label('log_id'),
        Log.timestamp,
        Log.status,
        Student.name.label('student_name'),
        Student.student_id_number,
        Exam.subject.label('exam_subject'),
        Exam.date.label('exam_date')
    ).join(Student, Log.student_id == Student.id).join(Exam, Log.exam_id == Exam.id)

    # TODO: Add filtering based on request.args if filter controls are added to the template
    # Example:
    # filter_date_str = request.args.get('filter_date')
    # if filter_date_str:
    #     try:
    #         filter_date = datetime.strptime(filter_date_str, '%Y-%m-%d').date()
    #         query = query.filter(db.func.date(Log.timestamp) == filter_date) # Or Exam.date
    #     except ValueError:
    #         flash("Invalid date format for filtering.", "warning")
    # filter_exam_id = request.args.get('filter_exam_id')
    # if filter_exam_id:
    #     query = query.filter(Log.exam_id == filter_exam_id)
    # filter_student_id = request.args.get('filter_student_id')
    # if filter_student_id:
    #     query = query.filter(Log.student_id == filter_student_id)

    logs_page = query.order_by(Log.timestamp.desc()).paginate(page=page, per_page=15) # 15 logs per page

    # For filter dropdowns - if implementing them
    # available_exams = Exam.query.order_by(Exam.date.desc()).all()
    # available_students = Student.query.order_by(Student.name).all()

    return render_template(
        'view_logs.html',
        title="Authentication Logs",
        logs_page=logs_page
        # available_exams=available_exams, # Uncomment if using filters
        # available_students=available_students # Uncomment if using filters
    )
