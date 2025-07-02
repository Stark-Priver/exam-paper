import os
import face_recognition
from werkzeug.utils import secure_filename
from flask import current_app

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

def process_student_image(image_input, student_id_number, source_type='fileupload'):
    """
    Saves the student's photo (from upload or capture), extracts face embedding,
    and returns image filename and embedding.
    Args:
        image_input: Can be a FileStorage object (uploaded file) or BytesIO (captured image).
        student_id_number: The student's ID number.
        source_type: 'fileupload' or 'capture'.
    Returns: (filename, face_embedding) or (None, error_message) if error or no face found.
    """
    if image_input is None:
        return None, "No image data provided."

    upload_folder = current_app.config['UPLOAD_FOLDER']
    filename = None
    image_path = None

    if source_type == 'fileupload':
        if not hasattr(image_input, 'filename') or not image_input.filename:
             return None, "Invalid file upload."
        if not allowed_file(image_input.filename):
            return None, "File type not allowed for upload."
        # Secure the original filename for uploads
        base_filename = image_input.filename.rsplit('.', 1)[0] # Get name without extension
        extension = image_input.filename.rsplit('.', 1)[1].lower()
        filename = secure_filename(f"student_{student_id_number}_{base_filename}.{extension}")
        image_path = os.path.join(upload_folder, filename)
        try:
            image_input.save(image_path)
        except Exception as e:
            return None, f"Error saving uploaded file: {str(e)}"

    elif source_type == 'capture':
        # For captured images (BytesIO), generate a filename. Assuming JPEG format from canvas.toDataURL('image/jpeg')
        filename = secure_filename(f"student_{student_id_number}_capture.jpg")
        image_path = os.path.join(upload_folder, filename)
        try:
            with open(image_path, 'wb') as f:
                f.write(image_input.getbuffer()) # BytesIO object has getbuffer()
        except Exception as e:
            return None, f"Error saving captured image: {str(e)}"
    else:
        return None, "Invalid image source type."

    if not image_path: # Should not happen if logic above is correct
        return None, "Failed to determine image path."

    try:
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
        # It's good practice to check existence before removing, even if an error occurred elsewhere.
        if os.path.exists(image_path):
            try:
                os.remove(image_path)
            except Exception as remove_e: # Log or handle remove error if necessary
                current_app.logger.error(f"Error removing image {image_path} after processing error: {remove_e}")
        return None, f"Error processing image: {str(e)}"

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
