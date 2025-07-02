from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileRequired
from wtforms import StringField, PasswordField, BooleanField, SubmitField, FileField, DateField, TimeField
from wtforms.validators import DataRequired, Length, EqualTo, ValidationError, Optional
from app.models import Student # Import User if needed for validation like unique username
from flask import current_app

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=4, max=20)])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Login')

class StudentForm(FlaskForm):
    student_id_number = StringField('Student ID Number', validators=[DataRequired(), Length(max=20)])
    name = StringField('Full Name', validators=[DataRequired(), Length(max=100)])
    photo = FileField('Student Photo (JPG, PNG)') # Define field without context-dependent validators initially
    submit = SubmitField('Save Student')

    def __init__(self, original_student_id_number=None, *args, **kwargs):
        super(StudentForm, self).__init__(*args, **kwargs)
        self.original_student_id_number = original_student_id_number
        
        # Dynamically add/update validators for the photo field here
        # This ensures current_app is available because __init__ is called when an app context exists
        current_photo_validators = [Optional()] # Always optional, will validate in route
        
        # Add FileAllowed validator using current_app.config
        # This must be done after super().__init__() and within an app context scenario
        if current_app:
            allowed_extensions = current_app.config.get('ALLOWED_EXTENSIONS', {'png', 'jpg', 'jpeg'})
            current_photo_validators.append(FileAllowed(allowed_extensions, 'Only JPG and PNG images are allowed!'))
        else:
            # Fallback or raise error if current_app is somehow not available, though unlikely here
            # For safety, you could define default extensions if current_app isn't found,
            # but the issue is that FileAllowed needs *some* iterable of extensions.
            # This else block is more for robustness; the core issue is delaying current_app access.
            current_photo_validators.append(FileAllowed({'png', 'jpg', 'jpeg'}, 'Only JPG and PNG images are allowed! (default)'))
            
        self.photo.validators = current_photo_validators

    def validate_student_id_number(self, student_id_number):
        if student_id_number.data != self.original_student_id_number:
            student = Student.query.filter_by(student_id_number=student_id_number.data).first()
            if student:
                raise ValidationError('This Student ID Number is already registered. Please use a different one.')

class ExamForm(FlaskForm):
    subject = StringField('Subject', validators=[DataRequired(), Length(max=100)])
    date = DateField('Date', validators=[DataRequired()], format='%Y-%m-%d')
    start_time = TimeField('Start Time', validators=[DataRequired()], format='%H:%M')
    end_time = TimeField('End Time', validators=[DataRequired()], format='%H:%M')
    submit = SubmitField('Save Exam')

    def validate_end_time(self, end_time):
        if self.start_time.data and end_time.data:
            if end_time.data <= self.start_time.data:
                raise ValidationError('End time must be after start time.')

class ExamRegistrationForm(FlaskForm):
    students = StringField('Student ID Numbers (comma-separated)', validators=[DataRequired()])
    submit = SubmitField('Update Registered Students')
