from math import ceil
import io
import csv

from flask import Blueprint, render_template, request, send_file
from flask_login import current_user, login_required
from app import db


bp = Blueprint('visits', __name__, url_prefix='/visits')

from auth import check_rights

PER_PAGE = 10

@bp.route('/stat_users')
@login_required
@check_rights("show_stat_users")
def stat_users():
    download_status = False
    if request.args.get('download_csv'):
        download_status = True
    query = '''
    SELECT users.login, count(visit_logs.path) AS count
    FROM visit_logs LEFT JOIN users ON users.id=visit_logs.user_id GROUP BY visit_logs.user_id ORDER BY count DESC
    '''
    with db.connection.cursor(named_tuple = True) as cursor:
        cursor.execute(query)
        print(cursor.statement)
        db_stat = cursor.fetchall()
    if download_status:
        f = io.BytesIO()
        f.write("N,User,Counter\n".encode("utf-8"))
        for i, row in enumerate(db_stat):
            f.write(f'{i+1},{row.login or "Non-authenticated user"},{row.count}\n'.encode("utf-8"))
        f.seek(0)
        return send_file(f, as_attachment=True, download_name="stat_users.csv", mimetype="text/csv")
        
    return render_template('visits/stat_users.html', stats = db_stat)

@bp.route('/stat')
@login_required
@check_rights("show_stat_users")
def stat():
    download_status = False
    if request.args.get('download_csv'):
        download_status = True
    query = '''
    SELECT visit_logs.path, count(visit_logs.path) AS count
    FROM visit_logs GROUP BY visit_logs.path ORDER BY count DESC
    '''
    with db.connection.cursor(named_tuple = True) as cursor:
        cursor.execute(query)
        print(cursor.statement)
        db_stat = cursor.fetchall()
    if download_status:
        f = io.BytesIO()
        f.write("N,Path,Counter\n".encode("utf-8"))
        for i, row in enumerate(db_stat):
            f.write(f'{i+1},{row.path},{row.count}\n'.encode("utf-8"))
        f.seek(0)
        return send_file(f, as_attachment=True, download_name="stat.csv", mimetype="text/csv")
        
    return render_template('visits/stat.html', stats = db_stat)


@bp.route('/logs')
@login_required
def logs():
    page = request.args.get('page', 1, type=int)
    query_counter = 'SELECT count(*) as page_count FROM visit_logs WHERE user_id=%s'
    query = '''
        SELECT visit_logs.*, users.login
        FROM visit_logs
        LEFT JOIN users ON visit_logs.user_id = users.id
        WHERE visit_logs.user_id=%s
        LIMIT %s
        OFFSET %s
        '''
    if current_user.is_admin():
        query = '''
        SELECT visit_logs.*, users.login
        FROM visit_logs
        LEFT JOIN users ON visit_logs.user_id = users.id
        LIMIT %s
        OFFSET %s
        '''
        query_counter = 'SELECT count(*) as page_count FROM visit_logs'
    
    with db.connection.cursor(named_tuple = True) as cursor:
        if current_user.is_admin():
            cursor.execute(query,(PER_PAGE, PER_PAGE * (page - 1)))
        else:
            cursor.execute(query,(current_user.id, PER_PAGE, PER_PAGE * (page - 1)))
        print(cursor.statement)
        db_logs = cursor.fetchall()

    with db.connection.cursor(named_tuple = True) as cursor:
        if current_user.is_admin():
            cursor.execute(query_counter)
        else:
            cursor.execute(query_counter, (current_user.id,))
        print(cursor.statement)
        db_counter = cursor.fetchone().page_count
    
    page_count = math.ceil(db_counter / PER_PAGE)
        
    return render_template('visits/logs.html', logs = db_logs, page = page, page_count = page_count)


