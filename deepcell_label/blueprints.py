"""Flask blueprint for modular routes."""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import gzip
import json
import timeit
import traceback

from flask import abort
from flask import Blueprint
from flask import jsonify
from flask import request
from flask import current_app
from flask import send_file
from flask import make_response
from werkzeug.exceptions import HTTPException, BadRequestKeyError
import matplotlib
import numpy as np

from deepcell_label.label import TrackEdit, ZStackEdit
from deepcell_label.models import Project
from deepcell_label import loaders
from deepcell_label import exporters


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

    current_app.logger.error('Encountered %s: %s',
                             error.__class__.__name__, error, exc_info=1)

    traceback.print_exc()
    # now you're handling non-HTTP exceptions only
    return jsonify({'error': str(error)}), 500


@bp.route('/api/raw/<token>/<int:channel>/<int:frame>', methods=['GET'])
def raw(token, channel, frame):
    project = Project.get(token)
    if not project:
        return abort(404, description=f'project {token} not found')
    png = project.get_raw_png(channel, frame)
    return send_file(png, mimetype='image/png')


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
        return abort(400, description='Attach a new channel file in a form under the file field.')
    except TypeError:
        return abort(400, description='Could not load the attached file. Attach an .npz file.')
    channel = npz[npz.files[0]]
    # Check channel is the right shape
    expected_shape = (project.num_frames, project.width, project.height, 1)
    if channel.shape != expected_shape:
        raise ValueError(f'New channel must have shape {expected_shape}')
    # Add channel to project
    project.add_channel(channel)
    return {'numChannels': project.num_channels}


@bp.route('/api/labeled/<token>/<int:feature>/<int:frame>')
def labeled(token, feature, frame):
    project = Project.get(token)
    if not project:
        return abort(404, description=f'project {token} not found')
    png = project.get_labeled_png(feature, frame)
    return send_file(png, mimetype='image/png', cache_timeout=0)


@bp.route('/api/array/<token>/<int:feature>/<int:frame>')
def array(token, feature, frame):
    """
    """
    project = Project.get(token)
    if not project:
        return jsonify({'error': f'project {token} not found'}), 404
    labeled_array = project.get_labeled_array(feature, frame)
    content = gzip.compress(json.dumps(labeled_array.tolist()).encode('utf8'), 5)
    response = make_response(content)
    response.headers['Content-length'] = len(content)
    response.headers['Content-Encoding'] = 'gzip'
    return response
    # seg_array = project.get_labeled_array(feature, frame)
    # filename = f'{token}_array_feature{feature}_frame{frame}.npy'
    # return send_file(seg_array, attachment_filename=filename, cache_timeout=0)


@bp.route('/api/semantic-labels/<project_id>/<int:feature>')
def semantic_labels(project_id, feature):
    project = Project.get(project_id)
    if not project:
        return jsonify({'error': f'project {project_id} not found'}), 404
    cell_info = project.labels.cell_info[feature]
    return cell_info


@bp.route('/api/colormap/<project_id>/<int:feature>')
def colormap(project_id, feature):
    project = Project.get(project_id)
    if not project:
        return jsonify({'error': f'project {project_id} not found'}), 404
    max_label = project.get_max_label(feature)
    colormap = matplotlib.pyplot.get_cmap('viridis', max_label)
    colors = list(map(matplotlib.colors.rgb2hex, colormap.colors))
    colors.insert(0, '#000000')  # No label (label 0) is black
    colors.append('#FFFFFF')  # New label (last label) is white
    response = make_response({'colors': colors})
    response.headers['Cache-Control'] = 'max-age=0'

    return response


@bp.route('/api/edit/<token>/<action_type>', methods=['POST'])
def edit(token, action_type):
    """
    Edit the labeling of the project and
    update the project in the database.
    """
    start = timeit.default_timer()
    # obtain 'info' parameter data sent by .js script
    info = {k: json.loads(v) for k, v in request.values.to_dict().items()}

    project = Project.get(token)
    if not project:
        return abort(404, description=f'project {token} not found')
    # TODO: remove frame/feature/channel columns from db schema? or keep them around
    # to load projects on the last edited frame
    project.frame = info['frame']
    project.feature = info['feature']
    project.channel = info['channel']
    del info['frame']
    del info['feature']
    del info['channel']

    edit = get_edit(project)
    edit.dispatch_action(action_type, info)
    project.create_memento(action_type)
    project.update()

    changed_frames = [frame.frame_id for frame in project.action.frames]
    payload = {'feature': project.feature, 'frames': changed_frames, 'labels': edit.labels_changed}

    current_app.logger.debug('Finished action %s for project %s in %s s.',
                             action_type, token,
                             timeit.default_timer() - start)
    return jsonify(payload)


@bp.route('/api/undo/<token>', methods=['POST'])
def undo(token):
    start = timeit.default_timer()

    project = Project.get(token)
    if not project:
        return abort(404, description=f'project {token} not found')
    payload = project.undo()

    current_app.logger.debug('Undid action for project %s finished in %s s.',
                             token, timeit.default_timer() - start)
    return jsonify(payload)


@bp.route('/api/redo/<token>', methods=['POST'])
def redo(token):
    start = timeit.default_timer()

    project = Project.get(token)
    if not project:
        return abort(404, description=f'project {token} not found')
    payload = project.redo()

    current_app.logger.debug('Redid action for project %s finished in %s s.',
                             token, timeit.default_timer() - start)
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
    current_app.logger.debug('Loaded project %s in %s s.',
                             project.token, timeit.default_timer() - start)
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
    current_app.logger.info('Created project from %s in %s s.',
                            loader.path, timeit.default_timer() - start)
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
    current_app.logger.info('Created project from %s in %s s.',
                            loader.path, timeit.default_timer() - start)
    return jsonify({'projectId': project.token})


@bp.route('/api/download/<token>', methods=['GET'])
def download_project(token):
    """
    Download a DeepCell Label project as a .npz file
    """
    project = Project.get(token)
    if not project:
        return abort(404, description=f'project {token} not found')

    exporter = exporters.Exporter(project)
    filestream = exporter.export()

    return send_file(filestream, as_attachment=True, attachment_filename=exporter.path)


@bp.route('/api/upload/<bucket>/<token>', methods=['GET', 'POST'])
def upload_project_to_s3(bucket, token):
    """Upload .trk/.npz data file to AWS S3 bucket."""
    start = timeit.default_timer()
    project = Project.get(token)
    if not project:
        return abort(404, description=f'project {token} not found')

    # Save data file and send to S3 bucket
    exporter = exporters.S3Exporter(project)
    exporter.export(bucket)
    # add "finished" timestamp and null out PickleType columns
    # project.finish()

    current_app.logger.debug('Uploaded %s to S3 bucket %s from project %s in %s s.',
                             exporter.path, bucket, token,
                             timeit.default_timer() - start)
    return {}


def get_edit(project):
    """Factory for Edit objects"""
    if project.is_track:
        return TrackEdit(project)
    else:
        return ZStackEdit(project)
