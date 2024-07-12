import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
import jinja2

from .os_utility import create_dir, delete_dir

db = SQLAlchemy()
ROOT_DIR = os.path.basename(os.path.dirname(os.path.abspath(__file__)))
OS_ROOT = os.path.join(os.path.expanduser('~'), 'EducativeViewer')
DB_FILE_PATH = os.path.join(OS_ROOT, 'db.sqlite')



def create_app():
    create_dir(OS_ROOT)
    temp_folder_path = os.path.join(OS_ROOT, "temp")
    delete_dir(temp_folder_path)

    app = Flask(__name__, static_url_path='/static')
    app.config['SECRET_KEY'] = '9OLWxND4o83j4K4iuopO'
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_FILE_PATH}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['UPLOAD_FOLDER'] = temp_folder_path

    # load course dir as templates folder
    course_dir = os.getenv('course_dir', '.')
    my_loader = jinja2.ChoiceLoader([
        app.jinja_loader,
        jinja2.FileSystemLoader([f'{ROOT_DIR}/templates',
                                 f'{course_dir}']),
    ])
    app.jinja_loader = my_loader

    # set custom delimiters as html has many curly braces
    app.jinja_env.variable_start_string = '[([('
    app.jinja_env.variable_end_string = ')])]'
    app.jinja_env.block_start_string = '[([(='
    app.jinja_env.block_end_string = '=)])]'
    app.jinja_env.comment_start_string = "{[(#"
    app.jinja_env.comment_end_string = "#)]}"
    
    @app.before_request
    def create_tables():
        db.create_all()
    try:
        db.init_app(app)
    except Exception as e:
        print(e)

    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.init_app(app)

    from .models import User

    @login_manager.user_loader
    def load_user(user_id):
        # since the user_id is just the primary key of our user table, use it in the query for the user
        return User.query.get(int(user_id))

    # blueprint for auth routes in our app
    from .auth import auth as auth_blueprint
    app.register_blueprint(auth_blueprint)

    # blueprint for non-auth parts of app
    from .main import main as main_blueprint
    app.register_blueprint(main_blueprint)

    return app
