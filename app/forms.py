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
    # For adding a student, photo is required. For editing, it's optional.
    # We will handle this distinction in the route logic or by using two different forms if it gets complex.
    # For now, let's make it conditionally required.
    photo = FileField('Student Photo (JPG, PNG)', validators=[
        FileAllowed(current_app.config['ALLOWED_EXTENSIONS'], 'Only JPG and PNG images are allowed!')
    ])
    submit = SubmitField('Save Student')

    def __init__(self, original_student_id_number=None, *args, **kwargs):
        super(StudentForm, self).__init__(*args, **kwargs)
        self.original_student_id_number = original_student_id_number
        if not self.photo.validators: # If no validators set (e.g. during edit and no new photo)
            self.photo.validators = []

        # If creating a new student (no original_student_id_number), photo is required
        if not original_student_id_number:
            self.photo.validators.insert(0, FileRequired(message='Photo is required for new students.'))
        else: # If editing, photo is optional
            self.photo.validators.insert(0, Optional())


    def validate_student_id_number(self, student_id_number):
        # Check if student_id_number is unique, unless it's the student's current ID number (during edit)
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
