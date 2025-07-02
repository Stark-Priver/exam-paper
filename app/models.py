from datetime import datetime
from app import db, login_manager
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class User(UserMixin, db.Model): # For Admins
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id_number = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    face_image_path = db.Column(db.String(200), nullable=True) # Path to the stored image
    face_embedding = db.Column(db.PickleType, nullable=True) # Storing embedding as a pickled object (e.g., numpy array)
    logs = db.relationship('Log', backref='student', lazy=True)

    def __repr__(self):
        return f'<Student {self.name} ({self.student_id_number})>'

class Exam(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    subject = db.Column(db.String(100), nullable=False)
    date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    logs = db.relationship('Log', backref='exam', lazy=True)
    # Association table for Student <-> Exam many-to-many relationship
    registered_students = db.relationship(
        'Student',
        secondary='exam_registrations',
        lazy='subquery',
        backref=db.backref('registered_for_exams', lazy=True)
    )

    def __repr__(self):
        return f'<Exam {self.subject} on {self.date}>'

# exam_registrations association table
exam_registrations = db.Table('exam_registrations',
    db.Column('student_id', db.Integer, db.ForeignKey('student.id'), primary_key=True),
    db.Column('exam_id', db.Integer, db.ForeignKey('exam.id'), primary_key=True)
)

class Log(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    exam_id = db.Column(db.Integer, db.ForeignKey('exam.id'), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    status = db.Column(db.String(50), nullable=False) # e.g., "Verified", "Not Found", "Error"

    def __repr__(self):
        return f'<Log {self.student_id} for Exam {self.exam_id} at {self.timestamp} - Status: {self.status}>'
