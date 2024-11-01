from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, login_required, logout_user, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from .forms import LoginForm, AddUserForm, AttendanceFilterForm, AddChoirForm, AddAttendanceForm, ProfileForm
from .models import User, Attendance, Choir
from . import db, login_manager 
from datetime import datetime
from uuid import uuid4

main = Blueprint("main", __name__)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@main.route("/")
def index():
    return render_template("index.html")

@main.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and check_password_hash(user.password, form.password.data):
            login_user(user)
            flash(f"Welcome back, {user.name}!")
            return redirect(url_for("main.dashboard"))
        else:
            flash("Invalid username or password", "danger")
    return render_template("login.html", form=form)

@main.route("/dashboard")
@login_required
def dashboard():
    return render_template("organizer_dashboard.html" if current_user.role == "organizer" else "member_dashboard.html")
@main.route("/add_user", methods=["GET", "POST"])



@main.route("/add_user", methods=["GET", "POST"])
@login_required
def add_user():
    if current_user.role != "organizer":
        flash("You do not have permission to view this page.", "danger")
        return redirect(url_for("main.index"))

    form = AddUserForm()
    if form.validate_on_submit():
        base_username = form.name.data.lower().replace(" ", "")
        username = base_username
        counter = 1
        while User.query.filter_by(username=username).first():
            username = f"{base_username}{counter}"
            counter += 1

        password = f"{username}123"
        
        # Generate a unique member_id
        member_id = str(uuid4())
        while User.query.filter_by(member_id=member_id).first():
            member_id = str(uuid4())  # Regenerate until unique

        new_user = User(
            member_id=member_id,
            username=username,
            name=form.name.data,
            password=generate_password_hash(password),
            role=form.role.data
        )

        # Add selected choirs to the new user
        selected_choirs = form.choirs.data
        new_user.choirs.extend(selected_choirs)

        try:
            db.session.add(new_user)
            db.session.commit()
            flash(f"User added successfully. Inform the user that their password is '{password}'.", "success")
            return redirect(url_for("main.view_users"))
        except Exception as e:
            db.session.rollback()
            flash(f"Error adding user: {str(e)}", "danger")
            return redirect(url_for("main.add_user"))

    return render_template("add_user.html", form=form)


@main.route("/view_users", methods=["GET"])
@login_required
def view_users():
    if current_user.role != "organizer":
        flash("You do not have permission to view this page.", "danger")
        return redirect(url_for("main.index"))

    # Filter users by role and search by name
    role_filter = request.args.get('role')
    name_search = request.args.get('search')
    users_query = User.query

    if role_filter:
        users_query = users_query.filter_by(role=role_filter)
    if name_search:
        users_query = users_query.filter(User.name.ilike(f"%{name_search}%"))

    users = users_query.all()

    return render_template("view_users.html", users=users)


@main.route("/edit_user/<int:user_id>", methods=["GET", "POST"])
@login_required
def edit_user(user_id):
    if current_user.role != "organizer":
        flash("You do not have permission to view this page.", "danger")
        return redirect(url_for("main.index"))

    user = User.query.get_or_404(user_id)
    form = ProfileForm(obj=user)

    if form.validate_on_submit():
        # Check for unique username
        if User.query.filter(User.username != user.username, User.username == form.username.data).first():
            flash("Username already exists.", "warning")
            return redirect(url_for("main.edit_user", user_id=user.id))

        # Update user details
        user.username = form.username.data
        if form.password.data:  # Update password only if provided
            user.password = generate_password_hash(form.password.data)
        user.name = form.name.data
        user.role = form.role.data

        # Update choirs association
        user.choirs = form.choirs.data

        db.session.commit()
        flash("User updated successfully.", "success")
        return redirect(url_for("main.view_users"))

    return render_template("edit_user.html", form=form, user=user)

@main.route("/view_attendance", methods=["GET"])
@login_required
def view_attendance():
    if current_user.role != "organizer":
        flash("You do not have permission to view this page.", "danger")
        return redirect(url_for("main.index"))

    # Fetch all attendance records with users and choirs
    attendance_query = Attendance.query.join(User).join(Choir)

    # Filter by choir
    choir_filter = request.args.get('choir_id', type=int)
    if choir_filter:
        attendance_query = attendance_query.filter(Attendance.choir_id == choir_filter)

    # Filter by date
    date_filter = request.args.get('date')
    if date_filter:
        attendance_query = attendance_query.filter(Attendance.date == date_filter)

    # Fetch attendance records
    attendance_records = attendance_query.all()
    
    # Fetch choirs for filtering
    choirs = Choir.query.all()
    
    return render_template("view_attendance.html", records=attendance_records, choirs=choirs)

@main.route("/add_attendance", methods=["GET", "POST"])
@login_required
def add_attendance():
    # Check if the current user has permission
    if current_user.role != "organizer":
        flash("You do not have permission to view this page.", "danger")
        return redirect(url_for("main.index"))

    # Fetch all choirs for selection
    choirs = Choir.query.all()
    selected_choir_id = request.args.get('choir_id', type=int)
    members = []
    form = AddAttendanceForm()

    # Fetch members of the selected choir if a choir is selected
    if selected_choir_id:
        choir = Choir.query.get(selected_choir_id)
        if choir:
            members = choir.members
            for member in members:
                attendance_record = Attendance.query.filter_by(
                    user_id=member.id,
                    choir_id=selected_choir_id,
                    date=datetime.utcnow().date()
                ).first()
                member.attendance_status = attendance_record.status if attendance_record else None
        else:
            flash("Choir not found.", "danger")
            return redirect(url_for("main.add_attendance"))

    if request.method == "POST":
        try:
            # Get and format date from the form
            date_str = request.form.get("date")
            date = datetime.strptime(date_str, '%Y-%m-%d').date()
            attendance_data = request.form.to_dict()

            # Process attendance for each choir member
            for member_id, status in attendance_data.items():
                if member_id.startswith("status["):
                    # Extract member ID
                    member_id = int(member_id[7:-1])
                    existing_attendance = Attendance.query.filter_by(
                        user_id=member_id,
                        date=date,
                        choir_id=selected_choir_id
                    ).first()

                    if existing_attendance:
                        # Update existing attendance
                        existing_attendance.status = status
                    else:
                        # Create new attendance record
                        new_attendance = Attendance(
                            user_id=member_id,
                            choir_id=selected_choir_id,
                            date=date,
                            status=status,
                            timestamp=datetime.utcnow()
                        )
                        db.session.add(new_attendance)

            db.session.commit()
            flash("Attendance records updated successfully.", "success")
            return redirect(url_for("main.view_attendance", choir_id=selected_choir_id, date=date_str))

        except ValueError:
            flash("Invalid date format. Please use YYYY-MM-DD.", "danger")
        except Exception as e:
            db.session.rollback()
            flash(f"An error occurred: {str(e)}", "danger")

    # Render the attendance form
    return render_template(
        "add_attendance.html",
        choirs=choirs,
        members=members,
        form=form,
        selected_choir_id=selected_choir_id
    )

@main.route("/delete_user/<int:user_id>", methods=["POST"])
@login_required
def delete_user(user_id):
    if current_user.role != "organizer":
        flash("You do not have permission to perform this action.", "danger")
        return redirect(url_for("main.index"))
    
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    flash("User deleted successfully.", "success")
    return redirect(url_for("main.view_users"))

@main.route("/add_choir", methods=["GET", "POST"])
@login_required
def add_choir():
    if current_user.role != "organizer":
        flash("You do not have permission to view this page.", "danger")
        return redirect(url_for("main.index"))

    form = AddChoirForm()
    if form.validate_on_submit():
        new_choir = Choir(name=form.name.data)

        try:
            db.session.add(new_choir)
            db.session.commit()
            flash("Choir added successfully!", "success")
            return redirect(url_for("main.view_choirs"))
        except Exception as e:
            db.session.rollback()
            flash(f"An error occurred: {str(e)}", "danger")
    return render_template("add_choir.html", form=form)


@main.route("/view_choirs")
@login_required
def view_choirs():
    if current_user.role != "organizer":
        flash("You do not have permission to view this page.", "danger")
        return redirect(url_for("main.index"))

    choirs = Choir.query.all()
    return render_template("view_choirs.html", choirs=choirs)
@main.route("/edit_choir/<int:choir_id>", methods=["GET", "POST"])
@login_required
def edit_choir(choir_id):
    if current_user.role != "organizer":
        flash("You do not have permission to view this page.", "danger")
        return redirect(url_for("main.index"))

    choir = Choir.query.get_or_404(choir_id)
    form = AddChoirForm(obj=choir)

    if form.validate_on_submit():
        # Update choir name
        choir.name = form.name.data

        # Update members if needed
        selected_members = form.members.data
        choir.members = User.query.filter(User.id.in_(selected_members)).all()

        db.session.commit()
        flash("Choir updated successfully.", "success")
        return redirect(url_for("main.view_choirs"))

    # For pre-filling the form, also get current members
    form.members.choices = [(user.id, user.name) for user in User.query.all()]
    current_member_ids = [member.id for member in choir.members]
    form.members.data = current_member_ids

    return render_template("edit_choir.html", form=form, choir=choir)


@main.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    form = ProfileForm(obj=current_user)

    if form.validate_on_submit():
        # Check for unique username
        if User.query.filter(User.id != current_user.id, User.username == form.username.data).first():
            flash("Username already exists.", "warning")
            return redirect(url_for("main.profile"))

        # Update user details
        current_user.name = form.name.data
        current_user.mobile = form.mobile.data
        current_user.dob = form.dob.data

        # Update password only if provided
        if form.password.data:
            current_user.password = generate_password_hash(form.password.data)

        db.session.commit()
        flash("Profile updated successfully.", "success")
        return redirect(url_for("main.profile"))

    # Fetch the user's attendance records
    attendance_records = Attendance.query.filter_by(user_id=current_user.id).all()

    return render_template("profile.html", form=form, attendance_records=attendance_records)


@main.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "success")
    return redirect(url_for("main.index"))