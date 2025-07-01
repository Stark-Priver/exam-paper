import os
import face_recognition
from werkzeug.utils import secure_filename
from flask import current_app

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

def process_student_image(photo_file, student_id_number):
    """
    Saves the student's photo, extracts face embedding, and returns image path and embedding.
    Returns: (image_path, face_embedding) or (None, None) if error or no face found.
    """
    if photo_file is None or not photo_file.filename:
        return None, None # No file uploaded

    if allowed_file(photo_file.filename):
        filename = secure_filename(f"student_{student_id_number}_{photo_file.filename}")
        upload_folder = current_app.config['UPLOAD_FOLDER']
        image_path = os.path.join(upload_folder, filename)

        try:
            photo_file.save(image_path)

            # Load the saved image and find face encodings
            image = face_recognition.load_image_file(image_path)
            face_encodings = face_recognition.face_encodings(image)

            if face_encodings:
                # Assuming one face per photo for simplicity
                return filename, face_encodings[0]
            else:
                # No faces found, remove the saved image
                os.remove(image_path)
                return None, "No face found in the uploaded image."
        except Exception as e:
            # Handle potential errors during file saving or processing
            if os.path.exists(image_path):
                os.remove(image_path)
            return None, f"Error processing image: {str(e)}"
    else:
        return None, "File type not allowed."

def remove_student_image(image_filename):
    """Removes a student's image file."""
    if image_filename:
        upload_folder = current_app.config['UPLOAD_FOLDER']
        image_path = os.path.join(upload_folder, image_filename)
        if os.path.exists(image_path):
            try:
                os.remove(image_path)
                return True
            except Exception:
                return False
    return False
