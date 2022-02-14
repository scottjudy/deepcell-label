"""Flask blueprint for modular routes."""
from __future__ import absolute_import, division, print_function

import gzip
import io
import json
import timeit
import traceback

import numpy as np
from flask import (
    Blueprint,
    abort,
    current_app,
    jsonify,
    make_response,
    request,
    send_file,
)
from werkzeug.exceptions import BadRequestKeyError, HTTPException

from deepcell_label import exporters, loaders
from deepcell_label.label import Edit
from deepcell_label.models import Project

bp = Blueprint('label', __name__)  # pylint: disable=C0103


@bp.route('/health')
def health():
    """Returns success if the application is ready."""
    return jsonify({'message': 'success'}), 200


@bp.errorhandler(loaders.InvalidExtension)
def handle_invalid_extension(error):
    response = jsonify(error.to_dict())
    response.status_code = error.status_code
    return response


@bp.errorhandler(Exception)
def handle_exception(error):
    """Handle all uncaught exceptions"""
    # pass through HTTP errors
    if isinstance(error, HTTPException):
        return error

    current_app.logger.error(
        'Encountered %s: %s', error.__class__.__name__, error, exc_info=1
    )

    traceback.print_exc()
    # now you're handling non-HTTP exceptions only
    return jsonify({'error': str(error)}), 500


# TODO: send compressed data instead of octet-stream
@bp.route('/dev/raw/<project_id>')
def dev_raw(project_id):
    project = Project.get(project_id)
    if not project:
        return abort(404, description=f'project {project_id} not found')
    # Send binary data for raw image array
    raw = project.raw_array
    raw = (
        (raw - np.min(raw, axis=(0, 1, 2)))
        / (np.max(raw, axis=(0, 1, 2)) - np.min(raw, axis=(0, 1, 2)))
        * 255
    )
    # Reshape (frames, height, width, channels) to (channels, frames, height, width)
    raw = np.moveaxis(raw, -1, 0)
    raw = raw.astype('uint8')
    return send_file(io.BytesIO(raw.tobytes()), mimetype='application/octet-stream')


@bp.route('/dev/labeled/<project_id>')
def dev_labeled(project_id):
    project = Project.get(project_id)
    if not project:
        return abort(404, description=f'project {project_id} not found')
    # send binary data for label array (int16? int32?)
    labeled = project.label_array
    # Reshape (frames, height, width, features) to (features, frames, height, width)
    labeled = np.moveaxis(labeled, -1, 0)
    labeled = labeled.astype('int32')
    return send_file(io.BytesIO(labeled.tobytes()), mimetype='application/octet-stream')


@bp.route('/dev/labels/<project_id>')
def dev_labels(project_id):
    project = Project.get(project_id)
    if not project:
        return abort(404, description=f'project {project_id} not found')
    # send JSON data
    labels = project.labels.cell_info
    return labels


@bp.route('/api/raw/<token>', methods=['POST'])
def add_raw(token):
    """Add new channel to the project."""
    project = Project.get(token)
    if not project:
        return abort(404, description=f'project {token} not found')
    # Load channel from first array in attached file
    try:
        npz = np.load(request.files.get('file'))
    except BadRequestKeyError:  # could not get file from request.files
        return abort(
            400, description='Attach a new channel file in a form under the file field.'
        )
    except TypeError:
        return abort(
            400, description='Could not load the attached file. Attach an .npz file.'
        )
    channel = npz[npz.files[0]]
    # Check channel is the right shape
    expected_shape = (project.num_frames, project.width, project.height, 1)
    if channel.shape != expected_shape:
        raise ValueError(f'New channel must have shape {expected_shape}')
    # Add channel to project
    project.add_channel(channel)
    return {'numChannels': project.num_channels}


@bp.route('/dev/edit/<action>', methods=['POST'])
def dev_edit(action):
    """Edits a label image and returns the updated label image and segments in the label image."""
    start = timeit.default_timer()
    # Get arguments for action
    args = {k: json.loads(v) for k, v in request.values.to_dict().items()}
    # Separate height and width from args
    height = args['height']
    width = args['width']
    del args['height']
    del args['width']

    # Parse label and raw arrays
    if 'labels' not in request.files:
        return abort(400, description='Attach the labels.')
    else:
        labels = request.files['labels']
        labels_array = np.fromfile(labels, 'int32')
        labels_array = labels_array.reshape((height, width))
    if 'raw' in request.files:
        raw = request.files['raw']
        raw_array = np.fromfile(raw, 'uint8')
        raw_array = raw_array.reshape((height, width))
    elif action in ['watershed', 'threshold', 'autofit']:
        return abort(400, description=f'Attach a raw image to use the {action} action.')
    else:
        raw_array = None

    edit = Edit(labels_array, raw_array)
    edit.dispatch_action(action, args)

    content = gzip.compress(json.dumps(edit.labels.tolist()).encode('utf8'), 5)
    response = make_response(content)
    response.headers['Content-length'] = len(content)
    response.headers['Content-Encoding'] = 'gzip'

    current_app.logger.debug(
        'Finished action %s in %s s.',
        action,
        timeit.default_timer() - start,
    )
    return response


@bp.route('/api/undo/<token>', methods=['POST'])
def undo(token):
    start = timeit.default_timer()

    project = Project.get(token)
    if not project:
        return abort(404, description=f'project {token} not found')
    payload = project.undo()

    current_app.logger.debug(
        'Undid action for project %s finished in %s s.',
        token,
        timeit.default_timer() - start,
    )
    return jsonify(payload)


@bp.route('/api/redo/<token>', methods=['POST'])
def redo(token):
    start = timeit.default_timer()

    project = Project.get(token)
    if not project:
        return abort(404, description=f'project {token} not found')
    payload = project.redo()

    current_app.logger.debug(
        'Redid action for project %s finished in %s s.',
        token,
        timeit.default_timer() - start,
    )
    return jsonify(payload)


@bp.route('/api/project/<token>', methods=['GET'])
def get_project(token):
    """
    Retrieve data from a project already in the Project table.
    """
    start = timeit.default_timer()
    project = Project.get(token)
    if not project:
        return abort(404, description=f'project {token} not found')
    payload = project.make_first_payload()
    current_app.logger.debug(
        'Loaded project %s in %s s.', project.token, timeit.default_timer() - start
    )
    return jsonify(payload)


# @bp.route('/api/project', methods=['POST'])
# def create_project():
#     """
#     Create a new Project.
#     """
#     start = timeit.default_timer()
#     loader = loaders.get_loader(request)
#     project = Project.create(loader)
#     current_app.logger.info('Created project from %s in %s s.',
#                             loader.path, timeit.default_timer() - start)
#     return jsonify({'projectId': project.token})


@bp.route('/api/project/dropped', methods=['POST'])
def create_project_from_dropped_file():
    """
    Create a new Project from drag & dropped file.
    """
    start = timeit.default_timer()
    loader = loaders.FileLoader(request)
    project = Project.create(loader)
    current_app.logger.info(
        'Created project from %s in %s s.', loader.path, timeit.default_timer() - start
    )
    return jsonify({'projectId': project.token})


@bp.route('/api/project', methods=['POST'])
def create_project_from_url():
    """
    Create a new Project from URL.
    """
    start = timeit.default_timer()
    url_form = request.form
    loader = loaders.URLLoader(url_form)
    project = Project.create(loader)
    current_app.logger.info(
        'Created project from %s in %s s.', loader.path, timeit.default_timer() - start
    )
    return jsonify({'projectId': project.token})


@bp.route('/api/download', methods=['GET'])
def download_project():
    """
    Download a DeepCell Label project as a .npz file
    """
    id = request.args.get('id')
    project = Project.get(id)
    if not project:
        return abort(404, description=f'project {id} not found')
    format = request.args.get('format')
    exporter = exporters.Exporter(project, format)
    filestream = exporter.export()

    return send_file(filestream, as_attachment=True, attachment_filename=exporter.path)


@bp.route('/api/upload', methods=['GET', 'POST'])
def upload_project_to_s3():
    """Upload .trk/.npz data file to AWS S3 bucket."""
    start = timeit.default_timer()
    id = request.form['id']
    format = request.form['format']
    bucket = request.form['bucket']
    project = Project.get(id)
    if not project:
        return abort(404, description=f'project {id} not found')

    # Save data file and send to S3 bucket
    exporter = exporters.S3Exporter(project, format)
    exporter.export(bucket)
    # add "finished" timestamp and null out PickleType columns
    # project.finish()

    current_app.logger.debug(
        'Uploaded %s to S3 bucket %s from project %s in %s s.',
        exporter.path,
        bucket,
        id,
        timeit.default_timer() - start,
    )
    return {}
