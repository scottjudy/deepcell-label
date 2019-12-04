from caliban import TrackReview, ZStackReview
from flask import Flask, jsonify, render_template, request, redirect, url_for
import sys
import base64
import copy
import os
import numpy as np
import traceback
import boto3, botocore
from werkzeug.utils import secure_filename
import sqlite3
from sqlite3 import Error
import pickle
import json
import re

# Create and configure the app
application = Flask(__name__)
application.config.from_object("config")

TRACK_EXTENSIONS = set(['trk', 'trks'])
ZSTACK_EXTENSIONS = set(['npz'])



@application.route("/upload_file/<project_id>", methods=["GET", "POST"])
def upload_file(project_id):
    ''' Upload .trk/.npz data file to AWS S3 bucket.
    '''

    conn = create_connection(r"caliban.db")
    with conn:

        # Use id to grab appropriate TrackReview/ZStackReview object from database
        cur = conn.cursor()
        cur.execute("SELECT * FROM {tn} WHERE {idf}={my_id}".\
        format(tn="projects", idf="id", my_id=project_id))
        id_exists = cur.fetchone()
        state = pickle.loads(id_exists[2])

        # Call function in caliban.py to save data file and send to S3 bucket
        if "." in id_exists[1] and id_exists[1].split(".")[1].lower() in TRACK_EXTENSIONS:
            state.action_save_track()
        if "." in id_exists[1] and id_exists[1].split(".")[1].lower() in ZSTACK_EXTENSIONS:
            state.action_save_zstack()

        # Delete id and object from database
        delete_project(conn, project_id)

    return redirect("/")


@application.route("/action/<project_id>/<action_type>/<frame>", methods=["POST"])
def action(project_id, action_type, frame):
    ''' Make an edit operation to the data file and update the object
        in the database.
    '''

    # obtain 'info' parameter data sent by .js script
    info = {k: json.loads(v) for k, v in request.values.to_dict().items()}
    frame = int(frame)

    try:
        conn = create_connection(r"caliban.db")
        with conn:
            # Use id to grab appropriate TrackReview/ZStackReview object from database
            cur = conn.cursor()
            cur.execute("SELECT * FROM {tn} WHERE {idf}={my_id}".\
            format(tn="projects", idf="id", my_id=project_id))
            id_exists = cur.fetchone()
            state = pickle.loads(id_exists[2])

            # Perform edit operation on the data file
            state.action(action_type, info)
            frames_changed = state.frames_changed
            info_changed = state.info_changed

            state.frames_changed = state.info_changed = False

            # Update object in local database
            update_object(conn, (id_exists[1], state, project_id))

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)})

    if info_changed:
        tracks = state.readable_tracks
    else:
        tracks = False

    if frames_changed:
        img = state.get_frame(frame, raw=False)
        raw = state.get_frame(frame, raw=True)
        edit_arr = state.get_array(frame)

        encode = lambda x: base64.encodebytes(x.read()).decode()

        img_payload = {
            'raw': f'data:image/png;base64,{encode(raw)}',
            'segmented': f'data:image/png;base64,{encode(img)}',
            'seg_arr': edit_arr.tolist()
            }
    else:
        img_payload = False

    return jsonify({"tracks": tracks, "imgs": img_payload})

@application.route("/frame/<frame>/<project_id>")
def get_frame(frame, project_id):
    ''' Serve modes of frames as pngs. Send pngs and color mappings of
        cells to .js file.
    '''

    frame = int(frame)
    conn = create_connection(r"caliban.db")
    with conn:

        # Use id to grab appropriate TrackReview/ZStackReview object from database
        cur = conn.cursor()
        cur.execute("SELECT * FROM {tn} WHERE {idf}={my_id}".\
        format(tn="projects", idf="id", my_id=project_id))
        id_exists = cur.fetchone()
        if id_exists is None:
            return jsonify({'error': 'project_id not found'}), 404
        state = pickle.loads(id_exists[2])

        # Obtain raw, mask, and edit mode frames
        img = state.get_frame(frame, raw=False)
        raw = state.get_frame(frame, raw=True)

        # Obtain color map of the cells
        edit_arr = state.get_array(frame)

        encode = lambda x: base64.encodebytes(x.read()).decode()

        payload = {
            'raw': f'data:image/png;base64,{encode(raw)}',
            'segmented': f'data:image/png;base64,{encode(img)}',
            'seg_arr': edit_arr.tolist()
            }

        return jsonify(payload)

@application.route("/load/<filename>", methods=["POST"])
def load(filename):
    ''' Initate TrackReview/ZStackReview object and load object to database.
        Send specific attributes of the object to the .js file.
    '''

    conn = create_connection(r"caliban.db")
    print(f"Loading track at {filename}", file=sys.stderr)


    folders = re.split('__', filename)
    filename = folders[len(folders) - 1]
    subfolders = folders[2:len(folders)]

    subfolders = '/'.join(subfolders)

    input_bucket = folders[0]
    output_bucket = folders[1]

    if '.trk' in filename or '.trks' in filename:

        # Initate TrackReview object and entry in database
        track_review = TrackReview(filename, input_bucket, output_bucket, subfolders)
        project = (filename, track_review)
        project_id = create_project(conn, project)
        conn.commit()
        conn.close()

        # Send attributes to .js file
        return jsonify({
            "max_frames": track_review.max_frames,
            "tracks": track_review.readable_tracks,
            "dimensions": track_review.dimensions,
            "project_id": project_id,
            "screen_scale": track_review.scale_factor
            })

    if '.npz' in filename:

        # Initate ZStackReview object and entry in database
        zstack_review = ZStackReview(filename, input_bucket, output_bucket, subfolders)
        project = (filename, zstack_review)
        project_id = create_project(conn, project)
        conn.commit()
        conn.close()

        # Send attributes to .js file
        return jsonify({
            "max_frames": zstack_review.max_frames,
            "channel_max": zstack_review.channel_max,
            "feature_max": zstack_review.feature_max,
            "tracks": zstack_review.readable_tracks,
            "dimensions": zstack_review.dimensions,
            "project_id": project_id,
            "screen_scale": zstack_review.scale_factor
            })

@application.route('/', methods=['GET', 'POST'])
def form():
    ''' Request HTML landing page to be rendered if user requests for
        http://127.0.0.1:5000/.
    '''
    return render_template('form.html')


@application.route('/tool', methods=['GET', 'POST'])
def tool():
    ''' Request HTML caliban tool page to be rendered after user inputs
        filename in the landing page.
    '''

    filename = request.form['filename']
    print(f"{filename} is filename", file=sys.stderr)

    file = 'caliban-input__caliban-output__test__' + filename

    if '.trk' in file or '.trks' in file:
        return render_template('index_track.html', filename=file)
    if '.npz' in file:
        return render_template('index_zstack.html', filename=file)

    return "error"

@application.route('/<file>', methods=['GET', 'POST'])
def shortcut(file):
    ''' Request HTML caliban tool page to be rendered if user makes a URL
        request to access a specific data file that has been preloaded to the
        input S3 bucket (ex. http://127.0.0.1:5000/test.npz).
    '''

    if '.trk' in file or '.trks' in file:
        return render_template('index_track.html', filename=file)
    if '.npz' in file:
        return render_template('index_zstack.html', filename=file)

    return "error"

def create_connection(db_file):
    ''' Create a database connection to a SQLite database.
    '''
    conn = None
    try:
        conn = sqlite3.connect(db_file)

    except Error as e:
        print(e)

    return conn

def create_table(conn, create_table_sql):
    ''' Create a table from the create_table_sql statement.
    '''
    try:
        c = conn.cursor()
        c.execute(create_table_sql)
    except Error as e:
        print(e)


def create_project(conn, project):
    ''' Create a new project in the database table.
    '''
    sql = ''' INSERT INTO projects(filename, state)
              VALUES(?, ?) '''
    cur = conn.cursor()

    # convert object to binary data to be stored as data type BLOB
    state_data = pickle.dumps(project[1], pickle.HIGHEST_PROTOCOL)

    cur.execute(sql, (project[0], sqlite3.Binary(state_data)))
    return cur.lastrowid

def update_object(conn, project):
    ''' Update filename, state of a project.
    '''
    sql = ''' UPDATE projects
              SET filename = ? ,
                  state = ?
              WHERE id = ?'''

    # convert object to binary data to be stored as data type BLOB
    state_data = pickle.dumps(project[1], pickle.HIGHEST_PROTOCOL)

    cur = conn.cursor()
    cur.execute(sql, (project[0], sqlite3.Binary(state_data), project[2]))
    conn.commit()

def delete_project(conn, id):
    ''' Delete data object (TrackReview/ZStackReview) by id.
    '''
    sql = 'DELETE FROM projects WHERE id=?'
    cur = conn.cursor()
    cur.execute(sql, (id,))
    conn.commit()

def main():
    ''' Runs application and initiates database file if it doesn't exist.
    '''
    conn = create_connection(r"caliban.db")
    sql_create_projects_table = """ CREATE TABLE IF NOT EXISTS projects (

                                        id integer PRIMARY KEY,
                                        filename text NOT NULL,
                                        state blob NOT NULL); """
    create_table(conn, sql_create_projects_table)
    conn.commit()
    conn.close()

    application.jinja_env.auto_reload = True
    application.config['TEMPLATES_AUTO_RELOAD'] = True
    application.run('0.0.0.0', port=5000)

if __name__ == "__main__":
    main()