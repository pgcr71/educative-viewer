import base64
import webbrowser
from flask import Blueprint, jsonify, render_template, request, redirect, send_file, url_for
from flask_login import login_required, current_user
import natsort
import os

from .os_utility import check_code_present, load_topics, load_toc_if_exist, build_toc_render_items, \
    load_folder, build_folder_structure_for_monaco_sidebar
from .models import CurrentPath, CourseDetails
from . import db


main = Blueprint('main', __name__)
root_course_dir = os.getenv('course_dir', '.')


@main.route('/')
def index():
    return render_template('index.html')


'''
Endpoint to load the course list directory
'''
@main.route('/courses', methods=['GET', 'POST'])
@login_required
def courses():
    highlight_idx = None
    last_visited_topic = ""
    last_visited_index = 0
    course_dir = root_course_dir

    current_path_details = CurrentPath.query.filter_by(username=current_user.username).first()
    if current_path_details is not None:
        course_dir = current_path_details.last_visited_directory
        last_visited_course = current_path_details.last_visited_course
        current_course_details = CourseDetails.query.filter_by(username=current_user.username,
                                                               last_visited_course=last_visited_course).first()
        if current_course_details is not None:
            last_visited_topic = current_course_details.last_visited_topic
            last_visited_index = current_course_details.last_visited_index

    if request.method == "POST":
        if request.form.get("folder"):
            '''
            Traversing in folders
            '''
            folder = request.form.get("folder")
            course_dir = os.path.join(course_dir, folder)
            folders = natsort.natsorted(os.listdir(course_dir))
            last_visited_course = course_dir.split(os.path.sep)[-1]
            current_course_details = CourseDetails.query.filter_by(username=current_user.username,
                                                                   last_visited_course=last_visited_course).first()
            if current_course_details is not None:
                last_visited_topic = current_course_details.last_visited_topic
                last_visited_index = current_course_details.last_visited_index
            if folder + ".html" in folders:
                '''
                If topic.html is found, render the html then
                '''
                current_course_details = CourseDetails(username=current_user.username,
                                                       last_visited_course=course_dir.split(os.path.sep)[-2],
                                                       last_visited_topic=last_visited_topic,
                                                       last_visited_index=last_visited_index)
                db.session.merge(current_course_details)
                db.session.commit()
                return redirect(url_for('main.courses') + f"/{folder}")
            if folder + ".html" not in folders:
                '''
                It is a folder, traverse inside it.
                '''
                current_path_details = CurrentPath(username=current_user.username, last_visited_directory=course_dir,
                                                   last_visited_course=last_visited_course)
                db.session.merge(current_path_details)
                db.session.commit()

                '''
                If the last visited topic is present in the folder, highlight the folder.
                '''
                if last_visited_topic in folders:
                    highlight_idx = folders.index(last_visited_topic)

                '''
                If table of contents.json is present, render the html using toc
                '''
                toc = load_toc_if_exist(course_dir)
                if toc:
                    toc_items = build_toc_render_items(toc, highlight_idx)
                    return render_template("courses_toc.html", toc_items=toc_items, folder=folder)
                return render_template("courses.html", folder_list=folders, folder=folder, highlight_idx=highlight_idx)
        '''
        If above condition doesnt satisfy then Traversing out folders  but not exit the root_course_dir
        '''
        if len(root_course_dir) < len(course_dir):
            course_dir = os.path.sep.join(course_dir.split(os.path.sep)[:-1])
            folders = natsort.natsorted(load_folder(course_dir))
            last_visited_course = course_dir.split(os.path.sep)[-1]
            current_path_details = CurrentPath(username=current_user.username, last_visited_directory=course_dir,
                                               last_visited_course=last_visited_course)
            db.session.merge(current_path_details)
            db.session.commit()

            if last_visited_topic in folders:
                highlight_idx = folders.index(last_visited_topic)
            return render_template("courses.html", folder_list=folders, folder=last_visited_course,
                                   highlight_idx=highlight_idx)
    '''
    If above condition doesnt satisfy then it is a GET request
    '''
    folders = natsort.natsorted(load_folder(course_dir))
    folder = os.path.split(course_dir)[-1]
    if last_visited_topic in folders:
        highlight_idx = folders.index(last_visited_topic)
    toc = load_toc_if_exist(course_dir)
    if toc:
        toc_items = build_toc_render_items(toc, highlight_idx)
        return render_template("courses_toc.html", toc_items=toc_items, folder=folder)
    return render_template("courses.html", folder_list=folders, folder=folder, highlight_idx=highlight_idx)


'''
Endpoint to load topics.
'''
@main.route("/courses/<topics>", methods=['GET', 'POST'])
@login_required
def topics(topics):
    current_path_details = CurrentPath.query.filter_by(username=current_user.username).first()
    course_dir = current_path_details.last_visited_directory
    last_visited_course = current_path_details.last_visited_course
    current_course_details = CourseDetails.query.filter_by(username=current_user.username,
                                                           last_visited_course=last_visited_course).first()
    topic_index = current_course_details.last_visited_index
    folders = natsort.natsorted(load_folder(course_dir))

    if topics in folders:
        topic_index = int(topics.split("-")[0])
        current_course_details = CourseDetails(username=current_user.username, last_visited_course=last_visited_course,
                                               last_visited_topic=topics, last_visited_index=topic_index)
        db.session.merge(current_course_details)
        db.session.commit()
    itr = topic_index
    toc = load_toc_if_exist(course_dir)
    if toc:
        return topics_toc(topics, course_dir, toc, itr)
    topic_folders = natsort.natsorted(load_topics(course_dir))
    try:
        itr = int(topic_folders.index(topics))
    except ValueError:
        pass
    if request.method == "POST":
        if "back" in request.form and itr > 0:
            itr -= 1
        elif "next" in request.form and itr < len(topic_folders) - 1:
            itr += 1
        elif "sidebar-topic" in request.form:
            itr = int(request.form.get('sidebar-topic'))
        elif "home" in request.form:
            return redirect(url_for('main.courses'))
        elif request.form.get("code_filesystem"):
            path = f"file:///{course_dir}/{topic_folders[itr]}".replace("\\", "/")
            webbrowser.open(path)
    '''
    GET request, this is used to refresh the webpage if required    
    '''
    current_course_details = CourseDetails(username=current_user.username, last_visited_course=last_visited_course,
                                           last_visited_topic=topic_folders[itr], last_visited_index=itr)
    db.session.merge(current_course_details)
    db.session.commit()

    template_folder = "/".join(course_dir[len(root_course_dir) + 1:].split(os.path.sep))
    webpage = f"{template_folder}/{topic_folders[itr]}/{topic_folders[itr]}.html"
    is_code_present = check_code_present(course_dir, topic_folders[itr])
    rendered_html = render_template(
        "topics.html", code_present=is_code_present, webpage=webpage, folder=f"{topic_folders[itr]}",
        folder_list=topic_folders, itr=itr)
    return rendered_html


'''
Method to load the toc contained topics
'''
def topics_toc(topics, course_dir, toc, itr):
    toc_items = build_toc_render_items(toc)
    try:
        itr = next(i for i, toc_item in enumerate(toc_items) if toc_item['title'] == topics)
    except StopIteration:
        pass
    if request.method == "POST":
        if "back" in request.form and itr > 0:
            if toc_items[itr - 1]['is_category']:
                if itr - 1 != 0:
                    itr -= 1
                else:
                    itr += 1
            itr -= 1
        elif "next" in request.form and itr < len(toc_items) - 1:
            if toc_items[itr + 1]['is_category']:
                if itr + 1 != len(toc_items) - 1:
                    itr += 1
                else:
                    itr -= 1
            itr += 1
        elif "sidebar-topic" in request.form:
            itr = int(request.form.get('sidebar-topic'))
        elif "home" in request.form:
            return redirect(url_for('main.courses'))
        elif request.form.get("code_filesystem"):
            path = f"file:///{course_dir}/{toc_items[itr]['title']}".replace("\\", "/")
            webbrowser.open(path)

    '''
    GET request, this is used to refresh the webpage if required    
    '''
    last_visited_course = course_dir.split(os.path.sep)[-1]
    current_course_details = CourseDetails(username=current_user.username, last_visited_course=last_visited_course,
                                           last_visited_topic=toc_items[itr]['title'], last_visited_index=itr)
    db.session.merge(current_course_details)
    db.session.commit()

    template_folder = "/".join(course_dir[len(root_course_dir) + 1:].split(os.path.sep))
    webpage = f"{template_folder}/{toc_items[itr]['title']}/{toc_items[itr]['title']}.html"
    is_code_present = check_code_present(course_dir, toc_items[itr]['title'])
    rendered_html = render_template(
        "topics_toc.html", code_present=is_code_present, webpage=webpage, folder=f"{toc_items[itr]['title']}",
        toc_items=toc_items, itr=itr)
    return rendered_html


'''
Endpoint to load the code/quiz files in monaco editor
'''
@main.route("/courses/code/<codes>", methods=['GET', 'POST'])
@login_required
def codes(codes):
    current_path_details = CurrentPath.query.filter_by(username=current_user.username).first()
    course_dir = current_path_details.last_visited_directory
    directory_path = os.path.join(course_dir, codes)
    encoded_path = base64.b64encode(directory_path.encode()).decode()
    return render_template("monaco-editor.html", encoded_path=encoded_path)


'''
Endpoint to list all the files in monaco-sidebar
'''
@main.route('/courses/list-files')
@login_required
def list_files():
    encoded_path = request.args.get('encoded_path')
    directory_path = base64.b64decode(encoded_path.encode()).decode()
    files = build_folder_structure_for_monaco_sidebar(directory_path, directory_path)
    return jsonify(files)


'''
Endpoint to load file-content in monaco-editor
'''
@main.route('/courses/file-content/<path:filename>')
@login_required
def file_content(filename):
    encoded_path = request.args.get('encoded_path')
    directory_path = base64.b64decode(encoded_path.encode()).decode()
    filename = base64.b64decode(filename.encode()).decode()
    file_path = os.path.join(directory_path, filename)
    return send_file(file_path)


@main.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404
