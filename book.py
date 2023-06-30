from flask import *
from flask_login import *
from auth import check_rights
from app import db
from math import ceil
from werkzeug.utils import secure_filename
import mysql.connector
import os
from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, SubmitField
from bs4 import BeautifulSoup

PER_PAGE = 3
PERMITTED_PARAMS = ["title", "description", "year", "publisher", "author","page_count"]
EDIT_PARAMS = ["id","title", "description", "year", "publisher", "author","page_count"]
COVER_PARAMS = ["filename","mime","type"]
EDIT_GENRES = ["book_id","genre"]


bp = Blueprint('books', __name__, url_prefix='/books')


@bp.route('/')
def all():
    page = request.args.get('page', 1, type = int)
    query = ('SELECT * FROM books JOIN covers ON books.cover_id = covers.id_covers LIMIT %s OFFSET %s')
    with db.connection.cursor(named_tuple = True) as cursor:
        cursor.execute(query,(PER_PAGE, (page-1)*PER_PAGE))
        books_list = cursor.fetchall()
    
    query = 'SELECT COUNT(*) AS count FROM (SELECT * FROM books JOIN covers ON books.cover_id = covers.id_covers) as result'
    with db.connection.cursor(named_tuple = True) as cursor:
        cursor.execute(query)
        count = cursor.fetchone().count
    
    last_page = ceil(count/PER_PAGE)
    
    query = "SELECT users.*, roles.name as role_name FROM users LEFT JOIN roles ON users.role_id=roles.id WHERE users.id = %s;"
    with db.connection.cursor(named_tuple = True) as cursor:
        cursor.execute(query, (current_user.id,))

        db_user = cursor.fetchone()
    
    return render_template('books/books.html', user = db_user, books_list=books_list, last_page = last_page, current_page = page,bgs = load_book_genres(), genres = load_genres())

def load_genres():
    query = "SELECT * FROM genres;"
    with db.connection.cursor(named_tuple = True) as cursor:
        cursor.execute(query)
        db_genres = cursor.fetchall()
    return db_genres

def load_book_genres():
    query = "SELECT * FROM book_genre;"
    with db.connection.cursor(named_tuple = True) as cursor:
        cursor.execute(query)
        db_bg = cursor.fetchall()
    return db_bg

@bp.route('/rate')
def rate():
    page = request.args.get('page', 1, type = int)
    # get the books,reviews,covers information and calculate the average rating, sort in descending order
    query = ('SELECT books.*, AVG(reviews.rating) AS avg_rating, covers.filename FROM books LEFT JOIN reviews ON books.id = reviews.book_id LEFT JOIN covers ON books.cover_id = covers.id_covers GROUP BY books.id ORDER BY avg_rating DESC LIMIT %s OFFSET %s')
    with db.connection.cursor(named_tuple = True) as cursor:
        cursor.execute(query,(PER_PAGE, (page-1)*PER_PAGE))
        books_list = cursor.fetchall()
    # score number of books
    query = 'SELECT COUNT(*) AS count FROM (SELECT * FROM books JOIN covers ON books.cover_id = covers.id_covers) as result'
    with db.connection.cursor(named_tuple = True) as cursor:
        cursor.execute(query)
        count = cursor.fetchone().count
    
    last_page = ceil(count/PER_PAGE)
    # Find out who is the book reviewer
    query = "SELECT users.*, roles.name as role_name FROM users LEFT JOIN roles ON users.role_id=roles.id WHERE users.id = %s;"
    with db.connection.cursor(named_tuple = True) as cursor:
        cursor.execute(query, (current_user.id,))

        db_user = cursor.fetchone()
    
    return render_template('books/bookslist.html', user = db_user, books_list=books_list, last_page = last_page, current_page = page,bgs = load_book_genres(), genres = load_genres())

@bp.route('/<int:book_id>')
def show_book(book_id):
    # Get all the information from the tables books and tables covers
    query = ('SELECT * FROM (SELECT * FROM books JOIN covers ON books.cover_id = covers.id_covers) as result WHERE id = %s')
    with db.connection.cursor(named_tuple = True) as cursor:
        cursor.execute(query, (book_id,))
        book = cursor.fetchone()
    
    user_id = current_user.id
    query = ('SELECT * FROM reviews WHERE book_id = %s AND user_id = %s')
    with db.connection.cursor(named_tuple = True) as cursor:
        cursor.execute(query, (book_id,user_id))
        existing_rating = cursor.fetchone()
    
    # get all the users information from the user table and get all the information from the reviews table
    query = ('SELECT * FROM users INNER JOIN reviews ON reviews.user_id = users.id WHERE reviews.book_id = %s')
    with db.connection.cursor(named_tuple = True) as cursor:
        cursor.execute(query, (book_id,))
        login_rate = cursor.fetchall()
    
    if book is None:
        flash("There's something wrong", "danger")
        return redirect(url_for("books.all"))
    
    return render_template('books/book.html', book=book,check = existing_rating, login_rate = login_rate)

@bp.route('/<int:book_id>/rate', methods=['GET'])
def rate_book(book_id):
    query = ('SELECT * FROM books WHERE id = %s')
    with db.connection.cursor(named_tuple = True) as cursor:
        cursor.execute(query, (book_id,))
        book = cursor.fetchone()

    if not book:
        flash("Book not found.", "danger")
        return redirect(url_for('books.all'))

    return render_template('books/rate_book.html', book=book)

@bp.route('/<int:book_id>/rate', methods=['POST'])
def submit_rating(book_id):
    rating = int(request.form['rating'])
    review = request.form['review']
    user_id = current_user.id  


    query = ('INSERT INTO reviews (book_id, user_id, rating, text) VALUES (%s, %s, %s, %s)')
    with db.connection.cursor(named_tuple = True) as cursor:
        cursor.execute(query, (book_id, user_id, rating, review))
        db.connection.commit()
        flash("Rating submitted successfully.", "success")
        return redirect(url_for('books.show_book', book_id=book_id))

@bp.route('/books/<int:book_id>/edit', methods=['GET'])
@login_required
@check_rights("edit")
def edit_book(book_id):
    print(book_id)
    edit_select = "SELECT * FROM books WHERE id = %s;"
    with db.connection.cursor(named_tuple = True) as cursor:
        cursor.execute(edit_select, (book_id,))
        book = cursor.fetchone()
        if book is None:
            flash("Can't find the book you need", "warning")
            return redirect(url_for("books.all"))
        
    return render_template("books/edit_books.html", book=book,bgs = load_book_genres(), genres = load_genres())

def params(names_list):
    result = {}
    for name in names_list:
        result[name] = request.form.get(name) or None
    return result

@bp.route('/books/<int:book_id>/update', methods=['POST'])
@login_required
@check_rights("edit")
def update_book(book_id):
    print(book_id)
    delete_query="DELETE FROM book_genre WHERE book_genre.book_id =  %s "
    with db.connection.cursor(named_tuple = True) as cursor:
        cursor.execute(delete_query, (book_id,))
        db.connection.commit()

    
    genres_id = [int(genre_id) for genre_id in request.form.getlist('genre_id')]
    for genre_id in genres_id:
        query = "INSERT INTO book_genre (book_id, genre_id) VALUES (%s,%s)"
        try:
            with db.connection.cursor(named_tuple = True) as cursor:
                cursor.execute(query, (book_id,genre_id))
                db.connection.commit()
        except Exception:
            db.connection.rollback()
            return False
    
    cur_params = params(EDIT_PARAMS)
    fields = ", ".join([f"{key} = %({key})s" for key in cur_params.keys()])
    update_query = f"UPDATE books SET {fields} WHERE id = %(id)s;"
    cur_params["id"] = book_id
    try:
        with db.connection.cursor(named_tuple = True) as cursor:
            cursor.execute(update_query, cur_params)
            db.connection.commit()
            flash("Successfully updated", "success")
    except mysql.connector.errors.DatabaseError:
        flash("An error occurred while changing", "danger")
        db.connection.rollback()
        return render_template('books/edit_books.html', book=cur_params,bgs=load_book_genres(),genres = load_genres())
    
    
      
    return redirect(url_for("books.all"))

@bp.route('/new')
@login_required
@check_rights("create")
def new_book():
    return render_template('books/new.html', bgs=load_book_genres(),genres = load_genres(),books={})
        
def insert_to_db(params, cover_id):
    query = """
        INSERT INTO books (title, description, year, publisher, author, page_count, cover_id) 
        VALUES (%(title)s, %(description)s, %(year)s, %(publisher)s, %(author)s, %(page_count)s, %(cover_id)s)
    """
    
    params["cover_id"] = cover_id
    
    try:
        with db.connection.cursor(named_tuple=True) as cursor:
            cursor.execute(query, params)
            db.connection.commit()
            cursor.close()
    except mysql.connector.errors.DatabaseError:
        db.connection.rollback()
        return False

    return True

def insert_f_to_db(params):
    query = """
        INSERT INTO covers (filename, mime_type, md5_hash) 
        VALUES (%(filename)s, %(mime_type)s, %(md5_hash)s)
    """
    try:
        with db.connection.cursor(named_tuple = True) as cursor:
            cursor.execute(query, params)
    except Exception:
        db.connection.rollback()
        return False

    return True
    

@bp.route('/create', methods=['POST'])
@login_required
@check_rights("create")
def create_book():
    if not current_user.can("create"):
        flash("Insufficient rights to access the page", "warning")
        return redirect(url_for("books"))
    
    # file
    file = request.files.get('photo')
    files = {
        "filename" : file.filename,
        "mime_type" : file.mimetype,
        "md5_hash" : "aaaaa"
    }
    inserted_cover = insert_f_to_db(files)

    # get covers id
    query = "SELECT id_covers AS id FROM covers WHERE filename = %s"
    with db.connection.cursor(named_tuple=True) as cursor:
        cursor.execute(query, (file.filename,))
        result = cursor.fetchall()
    if result:
        id_value = result[0].id
    else:
        flash("Can't find book cover info", "danger")
        return redirect(url_for("books.new"))
    cur_params = params(PERMITTED_PARAMS)
    inserted = insert_to_db(cur_params,id_value)
    
    # get book id
    query = "SELECT id FROM books WHERE cover_id = %s"
    with db.connection.cursor(named_tuple=True) as cursor:
        cursor.execute(query, (id_value,))
        result = cursor.fetchall()
    if result:
        id_book = result[0].id
    else:
        flash("Can't find book info", "danger")
        return redirect(url_for("books.new_book"))
    genres_id = [int(genre_id) for genre_id in request.form.getlist('genre_id')]
    for genre_id in genres_id:
        query = "INSERT INTO book_genre (book_id, genre_id) VALUES (%s,%s)"
        try:
            with db.connection.cursor(named_tuple = True) as cursor:
                cursor.execute(query, (id_book,genre_id))
                db.connection.commit()
        except Exception:
            db.connection.rollback()
            return False
    
    if inserted and inserted_cover:
        if file:
            filename = secure_filename(file.filename)
            file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], filename))
        flash("Successfully updated", "success")
        return redirect(url_for("books.all"))
    else:
        flash("An error occurred while changing", "danger")
        return render_template("books/new.html",book=cur_params, bgs=load_book_genres(),genres = load_genres())
    
@bp.route("/<int:book_id>/delete", methods=['POST'])
@login_required
@check_rights("delete")
def delete_book(book_id):
    query = "SELECT c.filename FROM books b LEFT JOIN covers c ON b.cover_id = c.id_covers WHERE b.id = %s"
    with db.connection.cursor(named_tuple=True) as cursor:
        cursor.execute(query, (book_id,))
        result = cursor.fetchall()
        if result:
            filename = result[0].filename
            filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            os.remove(filepath)
    
    delete_query="DELETE books, covers FROM books JOIN covers ON books.cover_id = covers.id_covers WHERE books.id = %s"
    try:
        with db.connection.cursor(named_tuple = True) as cursor:
            cursor.execute(delete_query, (book_id,))
            db.connection.commit()
            flash("Book deleted successfully", "success")
    except mysql.connector.errors.DatabaseError:
        flash("An error occurred while deleting", "danger")
        db.connection.rollback()
    return redirect(url_for("books.all"))



@bp.route('/search',methods=['GET', 'POST'])
def search():
    if request.method == 'POST':
        title = request.form['title']
        year = request.form['year']
        page_count = request.form['page_count']
        author = request.form['author']
        genre = request.form['genre']
        results = filter_books(title, year, page_count, author,genre)
        return render_template('books/search.html', results=results, form=request.form,bgs=load_book_genres(),genres = load_genres())
    
    return render_template('books/books.html', results=[], form={})

def filter_books(title, year, page_count, author,genre):
    
    query = "SELECT books.*, covers.filename FROM books LEFT JOIN covers ON books.cover_id = covers.id_covers WHERE 1=1"

    if title:
        query += f" AND books.title LIKE '%{title}%'"
    if year:
        query += f" AND books.year = {year}"
    if page_count:
        query += f" AND books.page_count = {page_count}"
    if author:
        query += f" AND books.author LIKE '%{author}%'" 
    if genre:
        query += f" AND books.id IN (SELECT book_id FROM book_genre WHERE genre_id = {genre})"
        
    with db.connection.cursor(named_tuple = True) as cursor:
        cursor.execute(query)
        filtered_books= cursor.fetchall()

    return filtered_books

    