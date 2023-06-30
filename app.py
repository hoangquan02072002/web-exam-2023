from flask import Flask, render_template, session, request, redirect, url_for, flash
from flask_login import login_required, current_user
from mysql_db import MySQL
import mysql.connector

app = Flask(__name__)
application = app

PERMITTED_PARAMS = ["login", "password", "last_name", "first_name", "middle_name", "role_id"]
EDIT_PARAMS = ["login", "last_name", "first_name", "middle_name", "role_id"]

app.config.from_pyfile('config.py')
db = MySQL(app)

from auth import bp as bp_auth, init_login_manager, check_rights
from visits import bp as bp_visits
from book import bp as bp_books
init_login_manager(app)
app.register_blueprint(bp_auth)
app.register_blueprint(bp_visits)
app.register_blueprint(bp_books)

@app.before_request
def log_actions():
    if request.endpoint == "static":
        return
    query = """
        INSERT INTO visit_logs (user_id, path) 
        VALUES (%(user_id)s, %(path)s);
    """
    params = {
        "user_id": getattr(current_user, "id", None),
        "path": request.path,
    }

    try:
        with db.connection.cursor(named_tuple = True) as cursor:
            cursor.execute(query, params)
            db.connection.commit()
    except mysql.connector.errors.DatabaseError:
        db.connection.rollback()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/users')
def users():
    query = "SELECT users.*, roles.name as role_name FROM users LEFT JOIN roles on users.role_id=roles.id;"
    with db.connection.cursor(named_tuple = True) as cursor:
        cursor.execute(query)
        print(cursor.statement)
        db_users = cursor.fetchall()
    return render_template('users/index.html', users = db_users)

def load_roles():
    query = "SELECT * FROM roles;"
    with db.connection.cursor(named_tuple = True) as cursor:
        cursor.execute(query)
        db_roles = cursor.fetchall()
    return db_roles

@app.route('/users/new')
@login_required
@check_rights("create")
def new_user():
    return render_template('users/new.html', roles = load_roles(), user={})
        
def insert_to_db(params):
    query = """
        INSERT INTO users (login, password_hash, last_name, first_name, middle_name, role_id) 
        VALUES (%(login)s, SHA2(%(password)s, 256), %(last_name)s, %(first_name)s, %(middle_name)s, %(role_id)s);
    """
    try:
        with db.connection.cursor(named_tuple = True) as cursor:
            cursor.execute(query, params)
            db.connection.commit()
    except mysql.connector.errors.DatabaseError:
        db.connection.rollback()
        return False

    return True

def params(names_list):
    result = {}
    for name in names_list:
        result[name] = request.form.get(name) or None
    return result

@app.route('/users/create', methods=['POST'])
@login_required
@check_rights("create")
def create_user():
    if not current_user.can("create"):
        flash("Недостаточно прав для доступа к странице", "warning")
        return redirect(url_for("users"))
    cur_params = params(PERMITTED_PARAMS)
    inserted = insert_to_db(cur_params)
    print(cur_params)
    print(inserted)
    if inserted:
        flash("Пользователь успешно добавлен", "success")
        return redirect(url_for("users"))
    else:
        flash("При сохранении возникла ошибка", "danger")
        return render_template("users/new.html", roles = load_roles(), user=cur_params)

@app.route('/users/<int:user_id>/edit', methods=['GET'])
@login_required
@check_rights("edit")
def edit_user(user_id):
    edit_select = "SELECT * FROM users WHERE id = %s;"
    with db.connection.cursor(named_tuple = True) as cursor:
        cursor.execute(edit_select, (user_id,))
        user = cursor.fetchone()
        if user is None:
            flash("Пользователь не найден", "warning")
            return redirect(url_for("users"))
        
    return render_template("users/edit.html", user=user, roles=load_roles())

@app.route('/users/<int:user_id>/update', methods=['POST'])
@login_required
@check_rights("edit")
def update_user(user_id):
    cur_params = params(EDIT_PARAMS)
    if not current_user.can("assign_role"):
        del cur_params["role_id"]
    fields = ", ".join([f"{key} = %({key})s" for key in cur_params.keys()])
    cur_params["id"] = user_id
    update_query = f"UPDATE users SET {fields} WHERE id = %(id)s;"
    try:
        with db.connection.cursor(named_tuple = True) as cursor:
            cursor.execute(update_query, cur_params)
            db.connection.commit()
            flash("Пользователь успешно обновлен", "success")
    except mysql.connector.errors.DatabaseError:
        flash("При изменении возникла ошибка", "danger")
        db.connection.rollback()
        return render_template('users/edit.html', user=cur_params, roles=load_roles())
        
    return redirect(url_for("users"))
    
    
@app.route("/users/<int:user_id>")
@login_required
@check_rights("show")
def show_user(user_id):
    with db.connection.cursor(named_tuple = True) as cursor:
        query="SELECT * FROM users WHERE id = %s"
        cursor.execute(query, (user_id,))
        db_user = cursor.fetchone()
    if db_user is None:
        flash("Пользователь не найден", "danger")
        return redirect(url_for("users"))
    
    return render_template('users/show.html', user=db_user)

@app.route("/users/<int:user_id>/delete", methods=['POST'])
@login_required
@check_rights("delete")
def delete_user(user_id):
    delete_query="DELETE FROM users WHERE id = %s"
    try:
        with db.connection.cursor(named_tuple = True) as cursor:
            cursor.execute(delete_query, (user_id,))
            db.connection.commit()
            flash("Пользователь успешно удален", "success")
    except mysql.connector.errors.DatabaseError:
        flash("При удалении произошла ошибка", "danger")
        db.connection.rollback()
    return redirect(url_for("users"))