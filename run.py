import click
from app import create_app, db
from app.models import User, Student, Exam, Log # Import models to ensure they are known to Flask-Migrate

app = create_app()

@app.shell_context_processor
def make_shell_context():
    return {'db': db, 'User': User, 'Student': Student, 'Exam': Exam, 'Log': Log}

@app.cli.command("create-admin")
@click.argument("username")
@click.argument("password")
def create_admin_command(username, password):
    """Creates a new admin user."""
    if User.query.filter_by(username=username).first():
        print(f"Admin user {username} already exists.")
        return
    admin = User(username=username)
    admin.set_password(password)
    db.session.add(admin)
    db.session.commit()
    print(f"Admin user {username} created successfully.")

if __name__ == '__main__':
    app.run()
