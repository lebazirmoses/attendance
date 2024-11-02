from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_user, login_required, logout_user, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from .forms import LoginForm, AddUserForm, AttendanceFilterForm, AddChoirForm, AddAttendanceForm, ProfileForm
from .models import User, Attendance, Choir, Event
from . import db, login_manager 
from datetime import datetime, date
from uuid import uuid4

main = Blueprint("main", __name__)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@main.route('/')
def index():
    # Check if the user is authenticated
    if current_user.is_authenticated:
        return redirect(url_for('main.home'))  # Redirect to the home page if logged in
    return render_template('index.html')  # Render index page if not logged in

@main.route('/home')
def home():
    # Home page content for logged-in users
    return render_template('home.html')

@main.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and check_password_hash(user.password, form.password.data):
            login_user(user)
            flash(f"Welcome back, {user.name}!")
            return redirect(url_for("main.home"))
        else:
            flash("Invalid username or password", "danger")
    return render_template("login.html", form=form)

@main.route("/dashboard")
@login_required
def dashboard():
    # Check if the user is an organizer
    if current_user.role == "organizer":
        return render_template("organizer_dashboard.html")  # Redirect to the organizer dashboard if applicable

    # Fetch user's attendance records
    attendance_records = Attendance.query.filter_by(user_id=current_user.id).all()

    # Calculate present and absent counts
    present_count = sum(1 for record in attendance_records if record.status.lower() == 'present')
    absent_count = sum(1 for record in attendance_records if record.status.lower() == 'absent')
    total_days = len(attendance_records)
    attendance_percentage = (present_count / total_days * 100) if total_days else 0

    # Prepare attendance trends for the last 30 records
    attendance_trends = attendance_records[-30:]  # Get the last 30 records for better insights
    trend_labels = [record.date.strftime("%Y-%m-%d") for record in attendance_trends]
    trend_data = [1 if record.status.lower() == 'present' else 0 for record in attendance_trends]

    # Calculate average attendance percentage for the last 30 days
    average_attendance_percentage = sum(trend_data) / len(trend_data) * 100 if trend_data else 0

    # Fetch upcoming choir events for the user's choirs
    upcoming_events = Event.query.join(Choir.members).filter(User.id == current_user.id, Event.date >= datetime.utcnow()).order_by(Event.date).limit(5).all()

    return render_template(
        "member_dashboard.html",
        present_count=present_count,
        absent_count=absent_count,
        attendance_percentage=attendance_percentage,
        attendance_trends=attendance_trends,
        upcoming_events=upcoming_events,
        total_days=total_days,
        trend_labels=trend_labels,
        trend_data=trend_data,
        average_attendance_percentage=average_attendance_percentage  # Pass the average attendance percentage
    )

@main.route("/add_user", methods=["GET", "POST"])
@login_required
def add_user():
    # Check if the current user has the organizer role
    if current_user.role != "organizer":
        flash("You do not have permission to view this page.", "danger")
        return redirect(url_for("main.index"))

    form = AddUserForm()

    # Fetch all choirs for rendering checkboxes in the form
    form.choirs.choices = [(choir.id, choir.name) for choir in Choir.query.all()]

    # Validate the form submission
    if form.validate_on_submit():
        # Create a unique username based on the user's name
        base_username = form.name.data.lower().replace(" ", "")
        username = base_username
        counter = 1
        while User.query.filter_by(username=username).first():
            username = f"{base_username}{counter}"
            counter += 1

        password = f"{username}123"  # Default password

        # Generate a unique member_id
        member_id = str(uuid4())
        while User.query.filter_by(member_id=member_id).first():
            member_id = str(uuid4())  # Regenerate until unique

        # Create a new user object
        new_user = User(
            member_id=member_id,
            username=username,
            name=form.name.data,
            password=generate_password_hash(password),
            role=form.role.data
        )

        # Capture selected choirs from the form
        selected_choirs = request.form.getlist('choirs')
        choirs = Choir.query.filter(Choir.id.in_(selected_choirs)).all()
        new_user.choirs.extend(choirs)

        # Attempt to add the new user to the database
        try:
            db.session.add(new_user)
            db.session.commit()
            flash(f"User added successfully. Inform the user that their password is '{password}'.", "success")
            return redirect(url_for("main.view_users"))
        except Exception as e:
            db.session.rollback()  # Roll back in case of error
            flash(f"Error adding user: {str(e)}", "danger")
            return redirect(url_for("main.add_user"))

    # Render the add user form
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

def record_attendance(member_id, status):
    member = User.query.get(member_id)
    if status == 'present':
        member.attendance_days += 1
    else:
        member.absence_days += 1  # Increment absence count for absent status
    db.session.commit()


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

    # Filter by day of the week (Saturday or Sunday)
    day_filter = request.args.get('day_of_week')  # New filter for days
    if day_filter == 'saturday':
        attendance_query = attendance_query.filter(db.func.strftime('%w', Attendance.date) == '6')  # Saturday
    elif day_filter == 'sunday':
        attendance_query = attendance_query.filter(db.func.strftime('%w', Attendance.date) == '0')  # Sunday

    # Fetch attendance records
    attendance_records = attendance_query.all()
    
    # Adding day of the week to each record
    for record in attendance_records:
        record.day_of_week = record.date.strftime("%A")  # Get the day of the week

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

    day_of_week = None  # Initialize the variable for the day of the week

    if request.method == "POST":
        try:
            # Get and format date from the form
            date_str = request.form.get("date")
            date = datetime.strptime(date_str, '%Y-%m-%d').date()
            day_of_week = date.strftime("%A")  # Get the day of the week from the date
            attendance_data = request.form.to_dict()

            # Process attendance for each choir member
            for member_id, status in attendance_data.items():
                if member_id.startswith("status["):
                    member_id = int(member_id[7:-1])
                    existing_attendance = Attendance.query.filter_by(
                        user_id=member_id,
                        date=date,
                        choir_id=selected_choir_id,
                    ).first()

                    if existing_attendance:
                        existing_attendance.status = status
                    else:
                        new_attendance = Attendance(
                            user_id=member_id,
                            choir_id=selected_choir_id,
                            date=date,
                            status=status,
                            timestamp=datetime.utcnow(),
                        )
                        db.session.add(new_attendance)

            db.session.commit()
            flash("Attendance records updated successfully.", "success")
            return redirect(url_for("main.dashboard"))

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
        selected_choir_id=selected_choir_id,
        day_of_week=day_of_week,  # Corrected: Added comma here
        current_date=datetime.utcnow().date() 
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

@main.route("/attendance_count/<int:choir_id>")
@login_required
def attendance_count(choir_id):
    # Ensure the user has permission to view attendance
    if current_user.role != "organizer":
        return jsonify({"error": "Unauthorized"}), 403
    
    # Query the attendance count
    count = Attendance.query.filter_by(choir_id=choir_id).count()
    return jsonify({"count": count})

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
        if User.query.filter(User.id != current_user.id, User.username == form.username.data).first():
            flash("Username already exists.", "warning")
            return redirect(url_for("main.profile"))

        current_user.name = form.name.data
        current_user.mobile = form.mobile.data
        current_user.dob = form.dob.data
        current_user.address = form.address.data  # New field for address
        current_user.emergency_contact = form.emergency_contact.data  # New field for emergency contact

        if form.password.data:
            current_user.password = generate_password_hash(form.password.data)

        db.session.commit()
        flash("Profile updated successfully.", "success")
        return redirect(url_for("main.profile"))

    # Fetch attendance records and calculate insights
    attendance_records = Attendance.query.filter_by(user_id=current_user.id).all()
    attendance_trends = [(record.date, record.status) for record in attendance_records]  # For visualization

    return render_template(
        "profile.html",
        form=form,
        attendance_records=attendance_records,
        attendance_trends=attendance_trends,
    )   
@main.route("/reports", methods=["GET"])
@login_required
def reports():
    if current_user.role != "organizer":
        flash("You do not have permission to view this page.", "danger")
        return redirect(url_for("main.index"))

    # Fetch all attendance records
    attendance_records = Attendance.query.all()

    # Processing attendance data for aggregation
    user_attendance = {}
    choir_attendance = {}

    for record in attendance_records:
        user_id = record.user_id
        choir_id = record.choir_id
        status = record.status.lower()

        # Aggregate by user
        if user_id not in user_attendance:
            user_attendance[user_id] = {'present': 0, 'absent': 0}
        user_attendance[user_id][status] += 1

        # Aggregate by choir
        if choir_id not in choir_attendance:
            choir_attendance[choir_id] = {'present': 0, 'absent': 0}
        choir_attendance[choir_id][status] += 1

    # Prepare data for visualizations for users
    user_labels = []
    user_present_data = []
    user_absent_data = []

    for user_id, counts in user_attendance.items():
        user_labels.append(User.query.get(user_id).name)  # Assuming User has a name field
        user_present_data.append(counts['present'])
        user_absent_data.append(counts['absent'])

    # Prepare data for visualizations for choirs
    choir_labels = []
    choir_present_data = []
    choir_absent_data = []

    for choir_id, counts in choir_attendance.items():
        choir_labels.append(Choir.query.get(choir_id).name)  # Assuming Choir has a name field
        choir_present_data.append(counts['present'])
        choir_absent_data.append(counts['absent'])

    return render_template(
        "reports.html",
        attendance_records=attendance_records,
        user_labels=user_labels,
        user_present_data=user_present_data,
        user_absent_data=user_absent_data,
        choir_labels=choir_labels,
        choir_present_data=choir_present_data,
        choir_absent_data=choir_absent_data
    )

def calculate_absence_days(user_id, attendances):
    total_days = 0
    absence_days = 0
    
    # Count total days and absence days
    for attendance in attendances:
        total_days += 1
        if attendance.status.lower() == 'absent':
            absence_days += 1

    return absence_days, total_days
def update_user_attendance():
    with main.app_context():
        for user in User.query.all():
            user.attendance_days = len(user.attendances)
            user.absence_days, _ = calculate_absence_days(user.id, user.attendances)
        db.session.commit()  # Commit all changes after the loop


@main.route("/choir_dashboard/<int:choir_id>")
@login_required
def choir_dashboard(choir_id):
    choir = Choir.query.get_or_404(choir_id)
    attendance_records = Attendance.query.filter_by(choir_id=choir_id).all()
    
    # Calculate total days and attendance summary
    total_days = len(set(record.date for record in attendance_records))
    present_count = sum(1 for record in attendance_records if record.status.lower() == 'present')
    absent_count = total_days - present_count

    # Prepare data for leaderboard
    leaderboard = {}
    for record in attendance_records:
        user_id = record.user_id
        if user_id not in leaderboard:
            user = User.query.get(user_id)  # Fetch user by ID
            leaderboard[user_id] = {
                'name': user.name if user else "Unknown",  # Handle case if user is not found
                'attendance_days': 0,
                'absence_days': 0
            }
        if record.status.lower() == 'present':
            leaderboard[user_id]['attendance_days'] += 1
        else:
            leaderboard[user_id]['absence_days'] += 1

    # Sort leaderboard by attendance days
    sorted_leaderboard = sorted(leaderboard.values(), key=lambda x: x['attendance_days'], reverse=True)

    # Prepare data for line chart
    attendance_dates = sorted(set(record.date for record in attendance_records))
    present_attendance_days = [
        sum(1 for rec in attendance_records if rec.date == date and rec.status.lower() == 'present')
        for date in attendance_dates
    ]
    absent_attendance_days = [
        sum(1 for rec in attendance_records if rec.date == date and rec.status.lower() == 'absent')
        for date in attendance_dates
    ]

    # Calculate monthly attendance data
    monthly_attendance = {}
    for record in attendance_records:
        month = record.date.strftime("%Y-%m")  # Format to "YYYY-MM"
        if month not in monthly_attendance:
            monthly_attendance[month] = {'present': 0, 'absent': 0}
        if record.status.lower() == 'present':
            monthly_attendance[month]['present'] += 1
        else:
            monthly_attendance[month]['absent'] += 1

    monthly_attendance_dates = list(monthly_attendance.keys())
    monthly_attendance_days = [data['present'] for data in monthly_attendance.values()]

    # Prepare attendance summary
    attendance_summary = {
        "saturdays": sum(1 for rec in attendance_records if rec.date.weekday() == 5),
        "sundays": sum(1 for rec in attendance_records if rec.date.weekday() == 6)
    }

    return render_template("choir_dashboard.html",
                           choir=choir,
                           members=sorted_leaderboard,
                           total_days=total_days,
                           present_count=present_count,
                           absent_count=absent_count,
                           attendance_summary=attendance_summary,
                           attendance_dates=attendance_dates,
                           present_attendance_days=present_attendance_days,
                           absent_attendance_days=absent_attendance_days,
                           monthly_attendance_dates=monthly_attendance_dates,
                           monthly_attendance_days=monthly_attendance_days)

@main.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "success")
    return redirect(url_for("main.index"))