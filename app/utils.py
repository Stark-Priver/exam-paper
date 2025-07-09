import os
# import face_recognition # No longer used here
from deepface import DeepFace # For face validation
from werkzeug.utils import secure_filename
from flask import current_app

# Configuration for DeepFace validation (consistent with face_rec_utils)
DEEPFACE_DETECTOR_BACKEND_FOR_VALIDATION = 'opencv'


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
        # Validate that the saved image contains a detectable face using DeepFace
        # DeepFace.extract_faces can take an image path.
        # It returns a list of face objects, each with 'facial_area' and 'confidence'.
        # If no face is detected, it might return an empty list or raise an error if enforce_detection=True.
        detected_faces = DeepFace.extract_faces(
            img_path=image_path,
            detector_backend=DEEPFACE_DETECTOR_BACKEND_FOR_VALIDATION,
            enforce_detection=False, # Don't error out if no face, just return empty list or similar
            align=False # Alignment not strictly needed for just detection
        )

        # Check if any face was detected with reasonable confidence (confidence is often 0 if not found by some backends)
        # Or simply if the list is not empty and the first entry has a face area.
        if detected_faces and detected_faces[0]['confidence'] > 0 : # Check if list is not empty and first element is a valid face
            # Image is valid and contains a face.
            # We are not returning embeddings anymore, just the filename.
            # The Student.face_embedding field will not be used or will be removed from the model.
            current_app.logger.info(f"Successfully processed and validated image: {filename}")
            return filename, "Image validated successfully" # Second element can be a success message or None
        else:
            # No faces found, remove the saved image
            if os.path.exists(image_path):
                os.remove(image_path)
            current_app.logger.warning(f"No face found in image {filename}. Image rejected and removed.")
            return None, "No face found in the uploaded image. Please provide a clearer image."
    except Exception as e:
        current_app.logger.error(f"Error during DeepFace validation for image {image_path}: {e}", exc_info=True)
        if os.path.exists(image_path):
            try:
                os.remove(image_path)
            except Exception as remove_e:
                current_app.logger.error(f"Error removing image {image_path} after processing error: {remove_e}")
        return None, f"Error processing image with DeepFace: {str(e)}"

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
