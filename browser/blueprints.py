"""Flask blueprint for modular routes."""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import distutils
import distutils.util
import json
import os
import re
import timeit
import traceback

from flask import Blueprint
from flask import jsonify
from flask import render_template
from flask import request
from flask import redirect
from flask import current_app
from werkzeug.exceptions import HTTPException

from helpers import is_trk_file, is_npz_file
from models import Project
from caliban import TrackEdit, ZStackEdit, BaseEdit, ChangeDisplay
from config import S3_INPUT_BUCKET, S3_OUTPUT_BUCKET

bp = Blueprint('caliban', __name__)  # pylint: disable=C0103


@bp.route('/health')
def health():
    """Returns success if the application is ready."""
    return jsonify({'message': 'success'}), 200


class InvalidExtension(Exception):
    status_code = 400

    def __init__(self, message, status_code=None, payload=None):
        Exception.__init__(self)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload

    def to_dict(self):
        rv = dict(self.payload or ())
        rv['message'] = self.message
        return rv


@bp.errorhandler(InvalidExtension)
def handle_invalid_usage(error):
    response = jsonify(error.to_dict())
    response.status_code = error.status_code
    return response


@bp.errorhandler(Exception)
def handle_exception(error):
    """Handle all uncaught exceptions"""
    # pass through HTTP errors
    if isinstance(error, HTTPException):
        return error

    current_app.logger.error('Encountered %s: %s',
                             error.__class__.__name__, error, exc_info=1)

    # now you're handling non-HTTP exceptions only
    return jsonify({'message': str(error)}), 500


@bp.route('/upload_file/<bucket>/<int:project_id>', methods=['GET', 'POST'])
def upload_file(bucket, project_id):
    """Upload .trk/.npz data file to AWS S3 bucket."""
    start = timeit.default_timer()
    project = Project.get(project_id)
    if not project:
        return jsonify({'error': 'project_id not found'}), 404

    # Call function in caliban.py to save data file and send to S3 bucket
    edit = get_edit(project)
    filename = project.path
    if is_trk_file(filename):
        edit.action_save_track(bucket)
    elif is_npz_file(filename):
        edit.action_save_zstack(bucket)

    # add "finished" timestamp and null out PickleType columns
    project.finish()

    current_app.logger.debug('Uploaded file "%s" for project "%s" in %s s.',
                             filename, project_id,
                             timeit.default_timer() - start)

    return redirect('/')


@bp.route('/edit/<int:project_id>/<action_type>', methods=['POST'])
def edit(project_id, action_type):
    """
    Edit the labeling of the project and
    update the project in the database.
    """
    start = timeit.default_timer()
    # obtain 'info' parameter data sent by .js script
    info = {k: json.loads(v) for k, v in request.values.to_dict().items()}

    # TODO: remove frame from request values in front-end
    # Frame is instead tracked by the frame column in the State column
    if 'frame' in info:
        del info['frame']

    try:
        project = Project.get(project_id)
        if not project:
            return jsonify({'error': 'project_id not found'}), 404
        edit = get_edit(project)
        payload = edit.dispatch_action(action_type, info)
        project.create_memento(action_type)
        project.update()

    except Exception as e:  # TODO: more error handling to identify problem
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

    current_app.logger.debug('Finished action %s for project %s in %s s.',
                             action_type, project_id,
                             timeit.default_timer() - start)

    return jsonify(payload)


@bp.route('/changedisplay/<int:project_id>/<display_attribute>/<int:value>', methods=['POST'])
def change_display(project_id, display_attribute, value):
    """
    Change the displayed frame, feature, or channel
    and send back the changed image data.

    Args:
        project_id (int): ID of project to change
        display_attribute (str): choice between 'frame', 'feature', or 'channel'
        value (int): index of frame, feature, or channel to display

    Returns:
        dict: contains the raw and/or labeled image data
    """
    start = timeit.default_timer()

    try:
        project = Project.get(project_id)
        if not project:
            return jsonify({'error': 'project_id not found'}), 404
        change = ChangeDisplay(project)
        payload = change.change(display_attribute, value)
        project.update()

    except Exception as e:  # TODO: more error handling to identify problem
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

    current_app.logger.debug('Changed to %s %s for project %s in %s s.',
                             display_attribute, value, project_id,
                             timeit.default_timer() - start)
    return jsonify(payload)


@bp.route('/undo/<int:project_id>', methods=['POST'])
def undo(project_id):
    start = timeit.default_timer()
    try:
        project = Project.get(project_id)
        if not project:
            return jsonify({'error': 'project_id not found'}), 404
        payload = project.undo()
    except Exception as e:  # TODO: more error handling to identify problem
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

    current_app.logger.debug('Undid action for project %s finished in %s s.',
                             project_id, timeit.default_timer() - start)
    return jsonify(payload)


@bp.route('/redo/<int:project_id>', methods=['POST'])
def redo(project_id):
    start = timeit.default_timer()
    try:
        project = Project.get(project_id)
        if not project:
            return jsonify({'error': 'project_id not found'}), 404
        payload = project.redo()
    except Exception as e:  # TODO: more error handling to identify problem
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

    current_app.logger.debug('Redid action for project %s finished in %s s.',
                             project_id, timeit.default_timer() - start)
    return jsonify(payload)


@bp.route('/load/<bucket>/<filename>', methods=['POST'])
def load(bucket, filename):
    """
    Initate TrackEdit/ZStackEdit object and load object to database.
    Send specific attributes of the object to the .js file.
    """
    start = timeit.default_timer()
    current_app.logger.info('Loading track at %s', filename)

    path = re.sub('__', '/', filename)

    # arg is 'false' which gets parsed to True if casting to bool
    rgb = request.args.get('rgb', default='false', type=str)
    rgb = bool(distutils.util.strtobool(rgb))

    if not is_trk_file(path) and not is_npz_file(path):
        ext = os.path.splitext(path)[-1]
        raise InvalidExtension(f'invalid file extension: {ext}')

    # Initate Project entry in database
    project = Project.create(path, bucket)
    project.rgb = rgb
    project.update()
    # Make payload with raw image data, labeled image data, and label tracks
    payload = project.make_payload(x=True, y=True, labels=True)
    # Add other attributes to initialize frontend variables
    payload['numFrames'] = project.num_frames
    payload['project_id'] = project.id
    payload['dimensions'] = (project.width, project.height)
    # Attributes specific to filetype
    if is_trk_file(filename):
        payload['screen_scale'] = project.scale_factor
    if is_npz_file(filename):
        payload['numChannels'] = project.num_channels
        payload['numFeatures'] = project.num_features

    current_app.logger.debug('Loaded file %s in %s s.',
                             filename, timeit.default_timer() - start)
    return jsonify(payload)


@bp.route('/', methods=['GET', 'POST'])
def form():
    """Request HTML landing page to be rendered."""
    return render_template('index.html')


@bp.route('/tool', methods=['GET', 'POST'])
def tool():
    """
    Request HTML caliban tool page to be rendered after user inputs
    filename in the landing page.
    """
    if 'filename' not in request.form:
        return redirect('/')

    filename = request.form['filename']
    current_app.logger.info('%s is filename', filename)
    new_filename = 'caliban-input__caliban-output__test__{}'.format(filename)

    settings = make_settings(new_filename)
    return render_template(
        'tool.html',
        settings=settings)


@bp.route('/<filename>', methods=['GET', 'POST'])
def shortcut(filename):
    """
    Request HTML caliban tool page to be rendered if user makes a URL
    request to access a specific data file that has been preloaded to the
    input S3 bucket (ex. http://127.0.0.1:5000/test.npz).
    """
    settings = make_settings(filename)
    return render_template(
        'tool.html',
        settings=settings)


def get_edit(project):
    """Factory for Edit objects"""
    filename = project.path
    if is_npz_file(filename):
        return ZStackEdit(project)
    elif is_trk_file(filename):
        # don't use RGB mode with track files
        return TrackEdit(project)
    return BaseEdit(project)


def make_settings(filename):
    """Returns a dictionary of settings to send to the front-end."""
    folders = re.split('__', filename)

    # TODO: better parsing when buckets are not present
    input_bucket = folders[0] if len(folders) > 1 else S3_INPUT_BUCKET
    output_bucket = folders[1] if len(folders) > 2 else S3_OUTPUT_BUCKET
    start_of_path = min(len(folders) - 1, 2)
    path = '__'.join(folders[start_of_path:])

    rgb = request.args.get('rgb', default='false', type=str)
    pixel_only = request.args.get('pixel_only', default='false', type=str)
    label_only = request.args.get('label_only', default='false', type=str)
    # TODO: uncomment to use URL parameters instead of rigid bucket formatting within filename
    # input_bucket = request.args.get('input_bucket', default=S3_INPUT_BUCKET, type=str)
    # output_bucket = request.args.get('output_bucket', default=S3_OUTPUT_BUCKET, type=str)

    if is_trk_file(filename):
        filetype = 'track'
        title = 'Tracking Tool'
    elif is_npz_file(filename):
        filetype = 'zstack'
        title = 'Z-Stack Tool'
    else:
        ext = os.path.splitext(filename)[-1]
        raise InvalidExtension(f'invalid file extension: {ext}')

    settings = {
        'filetype': filetype,
        'title': title,
        'filename': path,
        'rgb': bool(distutils.util.strtobool(rgb)),
        'pixel_only': bool(distutils.util.strtobool(pixel_only)),
        'label_only': bool(distutils.util.strtobool(label_only)),
        'input_bucket': input_bucket,
        'output_bucket': output_bucket,
    }

    return settings
