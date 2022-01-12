"""
Classes to load external data from URLs into a DeepCell Label Project.
Loads or creates raw_array, label_array, cell_ids, and cell_info.
"""

import io
import json
import pathlib
import tarfile
import tempfile
import zipfile

import numpy as np
import requests
from PIL import Image
from tifffile import TiffFile

from deepcell_label.labelmaker import LabelInfoMaker
from deepcell_label.utils import reshape

DCL_AXES = 'ZYXC'


class Loader:
    """
    Interface for loading files into DeepCell Label.
    """

    def __init__(self):
        self.path = ''
        self.labeled_path = ''
        self.raw_array = None
        self.label_array = None
        self.cell_info = None
        self.cell_ids = None

    @property
    def is_tracking(self):
        """Tracking project when either the labels or raw are .trk."""
        return (self.labeled_path and is_trk(self.labeled_path)) or is_trk(self.path)

    def add_semantic_labels(self):
        label_maker = LabelInfoMaker(self.label_array, tracking=True)
        self.cell_ids = label_maker.cell_ids
        if self.cell_info is None:
            self.cell_info = label_maker.cell_info

    def load_combined(self, data):
        """
        Loads image data into the Loader based on the file extension.
        """
        label_array = None
        # Load arrays
        if is_npz(self.path):
            raw_array = load_raw_npz(data)
            label_array = load_labeled_npz(data)
        elif is_trk(self.path):
            raw_array = load_raw_trk(data)
            label_array = load_labeled_trk(data)
        elif is_png(self.path):
            raw_array = load_png(data)
        elif is_tiff(self.path):
            raw_array = load_tiff(data)
        elif is_zip(self.path):
            raw_array = load_zip(data)
        else:
            ext = pathlib.Path(self.path).suffix
            raise InvalidExtension('invalid file extension: {}'.format(ext))

        # Reshape or create arrays
        raw_array = reshape(raw_array, self.input_axes, self.output_axes)
        if label_array is None:
            # Substitute channels dimension with one feature
            shape = (*raw_array.shape[:-1], 1)
            label_array = np.zeros(shape)
        else:
            label_array = reshape(label_array, self.input_axes, self.output_axes)

        self.raw_array = raw_array
        self.label_array = label_array

    def load_raw(self, data):
        if is_npz(self.path):
            raw_array = load_raw_npz(data)
        elif is_trk(self.path):
            raw_array = load_raw_trk(data)
        elif is_png(self.path):
            raw_array = load_png(data)
        elif is_tiff(self.path):
            raw_array = load_tiff(data)
        elif is_zip(self.path):
            raw_array = load_zip(data)
        else:
            ext = pathlib.Path(self.path).suffix
            raise InvalidExtension('invalid file extension: {}'.format(ext))

        self.raw_array = reshape(raw_array, self.input_axes, self.output_axes)

    def load_labeled(self, data):
        if is_npz(self.labeled_path):
            label_array = load_labeled_npz(data)
            if label_array is None:
                label_array = load_npz(data)
        elif is_trk(self.labeled_path):
            label_array = load_labeled_trk(data)
        elif is_png(self.labeled_path):
            label_array = load_png(data)
        elif is_tiff(self.labeled_path):
            label_array = load_tiff(data)
        elif is_zip(self.labeled_path):
            label_array = load_zip(data)
        else:
            ext = pathlib.Path(self.labeled_path).suffix
            raise InvalidExtension('invalid file extension: {}'.format(ext))

        self.label_array = reshape(label_array, 'CZYX', self.output_axes)


class FileLoader(Loader):
    """
    Loader implementation for files sent in a request, like a drag-and-dropped file.
    """

    def __init__(self, request):
        super(FileLoader, self).__init__()
        file_ = request.files.get('file')
        self.input_axes = request.form['axes'] if 'axes' in request.form else DCL_AXES
        self.output_axes = DCL_AXES
        self.data = file_.stream.read()
        self.path = file_.filename
        self.source = 'dropped'
        self.load()

    def load(self):
        label_array = None
        # Load arrays
        if is_npz(self.path):
            raw_array = load_raw_npz(self.data)
            label_array = load_labeled_npz(self.data)
        elif is_png(self.path):
            raw_array = load_png(self.data)
        elif is_tiff(self.path):
            raw_array = load_tiff(self.data)
        elif is_trk(self.path):
            raw_array = load_raw_trk(self.data)
            label_array = load_labeled_trk(self.data)
            self.cell_info = load_lineage_trk(self.data)
        else:
            ext = pathlib.Path(self.path).suffix
            raise InvalidExtension('Invalid file extension: {}'.format(ext))

        # Reshape or create arrays
        raw_array = reshape(raw_array, self.input_axes, self.output_axes)
        if label_array is None:
            # Substitute channels dimension with one feature
            shape = (*raw_array.shape[:-1], 1)
            label_array = np.zeros(shape)
        else:
            label_array = reshape(label_array, self.input_axes, self.output_axes)

        self.raw_array = raw_array
        self.label_array = label_array

        self.add_semantic_labels()


class URLLoader(Loader):
    """
    Loader implementation for downloading files from URLs.
    """

    def __init__(self, url_form):
        super(URLLoader, self).__init__()
        self.source = 's3'
        self.path = url_form['url']
        self.labeled_path = (
            url_form['labeled_url'] if 'labeled_url' in url_form else None
        )
        self.input_axes = url_form['axes'] if 'axes' in url_form else DCL_AXES
        self.output_axes = DCL_AXES

        self.load()

    def load(self):
        data = requests.get(self.path).content
        if self.labeled_path is None:
            self.load_combined(data)
            if is_trk(self.path):
                self.cell_info = load_lineage_trk(data)
        else:
            labeled_data = requests.get(self.labeled_path).content
            self.load_raw(data)
            self.load_labeled(labeled_data)
            if is_trk(self.labeled_path):
                self.cell_info = load_lineage_trk(labeled_data)

        self.add_semantic_labels()


def is_npz(url):
    return pathlib.Path(url).suffix in {'.npz'}


def is_trk(url):
    return pathlib.Path(url).suffix in {'.trk', '.trks'}


def is_png(url):
    return pathlib.Path(url).suffix in {'.png'}


def is_tiff(url):
    return pathlib.Path(url).suffix in {'.tiff', '.tif'}


def is_zip(url):
    return pathlib.Path(url).suffix in {'.zip'}


def load_npz(data):
    """Returns the first array in an npz."""
    npz = np.load(io.BytesIO(data))
    return npz[npz.files[0]]


def load_raw_npz(data):
    """
    Returns raw image array from an NPZ file.
    """
    npz = np.load(io.BytesIO(data))

    # standard names for image (X) and labeled (y)
    if 'X' in npz.files:
        return npz['X']
    # alternate names 'raw' and 'annotated'
    elif 'raw' in npz.files:
        return npz['raw']
    # if filenames are different, try to load them anyways
    else:
        return npz[npz.files[0]]


def load_labeled_npz(data):
    """
    Returns labeled image array from an NPZ file.
    Returns None when the labeled image array is not present.
    """
    npz = np.load(io.BytesIO(data))

    # Look for label filenames
    if 'y' in npz.files:
        return npz['y']
    elif 'annotated' in npz.files:
        return npz['annotated']
    elif len(npz.files) > 1:
        return npz[npz.files[1]]


def load_raw_trk(data):
    """Load a raw image data from a .trk file."""
    with tempfile.NamedTemporaryFile() as temp:
        temp.write(data)
        with tarfile.open(temp.name, 'r') as trks:
            with io.BytesIO() as array_file:
                array_file.write(trks.extractfile('raw.npy').read())
                array_file.seek(0)
                return np.load(array_file)


def load_labeled_trk(data):
    """Load a labeled image data from a .trk file."""
    with tempfile.NamedTemporaryFile() as temp:
        temp.write(data)
        with tarfile.open(temp.name, 'r') as trks:
            with io.BytesIO() as array_file:
                array_file.write(trks.extractfile('tracked.npy').read())
                array_file.seek(0)
                return np.load(array_file)


def load_lineage_trk(data):
    """Loads a lineage JSON from a .trk file."""
    with tempfile.NamedTemporaryFile() as temp:
        temp.write(data)
        with tarfile.open(temp.name, 'r') as trks:
            try:
                trk_data = trks.getmember('lineages.json')
            except KeyError:
                try:
                    trk_data = trks.getmember('lineage.json')
                except KeyError:
                    raise ValueError('Invalid .trk file, no lineage data found.')

            lineages = json.loads(trks.extractfile(trk_data).read().decode())
            lineages = lineages if isinstance(lineages, list) else [lineages]

            # JSON only allows strings as keys, so convert them back to ints
            for i, tracks in enumerate(lineages):
                lineages[i] = {int(k): v for k, v in tracks.items()}

            # Track files have only one feature and one lineage
            if len(lineages) != 1:
                raise ValueError('Input file has multiple trials/lineages.')
            return {0: lineages[0]}


def load_png(data):
    """Returns image array from a PNG file."""
    image = Image.open(io.BytesIO(data), formats=['PNG'])
    # Luminance should add channel dimension at end
    if image.mode == 'L':
        array = np.array(image)
        array = np.expand_dims(array, -1)
    else:
        # Create three RGB channels
        # Handles RGB, RGBA, P modes
        array = np.array(image.convert('RGB'))
    # Add frame dimension at start
    array = np.expand_dims(array, 0)
    return array


def load_tiff(data):
    """Returns image array from a TIFF file."""
    # return np.asarray(imageio.imread(data))
    return TiffFile(io.BytesIO(data)).asarray()


def load_zip(data):
    """
    Loads a series of image arrays from a zip of TIFFs.
    Treats separate TIFFs as channels.
    """
    zip_file = zipfile.ZipFile(io.BytesIO(data), 'r')
    channels = [
        load_tiff(zip_file.open(item).read())
        for item in zip_file.filelist
        if not str(item.filename).startswith('__MACOSX/')
        and is_tiff(str(item.filename))
    ]
    return np.array(channels)


class InvalidExtension(Exception):
    status_code = 415

    def __init__(self, message, status_code=None, payload=None):
        Exception.__init__(self)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload

    def to_dict(self):
        rv = dict(self.payload or ())
        rv['error'] = self.message
        return rv
