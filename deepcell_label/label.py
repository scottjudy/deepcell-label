"""Classes to view and edit DeepCell Label Projects"""
from __future__ import absolute_import, division, print_function

import jsonpatch
import numpy as np
import skimage
from matplotlib.colors import Normalize
from scipy.ndimage import find_objects
from skimage import filters
from skimage.exposure import rescale_intensity
from skimage.measure import regionprops
from skimage.morphology import dilation, disk, erosion, flood, flood_fill, square
from skimage.segmentation import morphological_chan_vese, watershed


def make_segments(labels):
    """
    Returns a list of the segments in a label image.
    """
    objects = find_objects(labels)
    segments = {
        (i + 1): {
            # Does not contain
            # image coordinates (t, z, c); could be added server side or client side
            # id: likely added on client side
            'x': obj[1].start,
            'y': obj[0].start,
            'width': obj[1].stop - obj[1].start,
            'height': obj[0].stop - obj[0].start,
        }
        for i, obj in enumerate(objects)
        if obj is not None
    }
    return segments


class Edit(object):
    """
    Class for editing label images in DeepCell Label.
    Expected lifespan is a single action.

    Actions have three phases:
        1. select and edit the image currently on display
        3. make changes to the label metadata
        4. assign the image to the frame

    NOTE: Actions must directly assign changes to the frame attribute for the
    MutableNdarray class to detect the change and for the database to persist the change.
    Changes to a view of a MutableNdarray will not be detected by the original
    TODO: modify MutableNdarray class to share changed() signals from arrays view
    """

    def __init__(self, labels, raw=None):
        self.initial_labels = labels.copy()
        self.labels = labels
        self.raw = raw
        self.new_label = max(labels) + 1

    @property
    def patch(self):
        initial = make_segments(self.initial_labels)
        final = make_segments(self.labels)
        patch = jsonpatch.make_patch(initial, final)
        return patch.patch

    def clean_label(self, label):
        """Ensures that a label is a valid integer between 0 and an unused label"""
        return int(min(self.new_label, max(0, label)))

    def dispatch_action(self, action, info):
        """
        Call an action method based on an action type.

        Args:
            action (str): name of action method after "action_"
                          e.g. "handle_draw" to call "action_handle_draw"
            info (dict): key value pairs with arguments for action
        """
        attr_name = 'action_{}'.format(action)
        try:
            action_fn = getattr(self, attr_name)
            action_fn(**info)
        except AttributeError:
            raise ValueError('Invalid action "{}"'.format(action))

    def action_handle_draw(self, trace, foreground, background, brush_size):
        """
        Use a "brush" to draw in the brush value along trace locations of
        the annotated data.

        Args:
            trace (list): list of (x, y) coordinates where the brush has painted
            foreground (int): label written by the bush
            background (int): label overwritten by the brush
            brush_size (int): radius of the brush in pixels
        """
        foreground = self.clean_label(foreground)
        background = self.clean_label(background)

        image = np.copy(self.labels)
        # only overwrite the background image
        image_replaced = np.where(image == background, foreground, image)

        for loc in trace:
            x = loc[0]
            y = loc[1]
            brush_area = skimage.draw.disk(
                (y, x), brush_size, shape=(self.project.height, self.project.width)
            )
            image[brush_area] = image_replaced[brush_area]

        self.labels = image

    def action_trim_pixels(self, label, x, y):
        """
        Removes label pixels that are not connected to (x, y).

        Args:
            label (int): label to trim
            x (int): x position of seed
                              remove label that is not connect to this seed
            y (int): y position of seed
        """
        image = self.labels

        seed_point = (int(y), int(x))
        contiguous_label = flood(image=image, seed_point=seed_point)
        stray_pixels = np.logical_and(np.invert(contiguous_label), image == label)
        image_trimmed = np.where(stray_pixels, 0, image)

        self.labels = image_trimmed

    def action_flood(self, label, x, y):
        """
        Floods the region at (x, y) with the label.
        Only floods diagonally connected pixels (connectivity == 2) when label != 0.

        Args:
            label (int): label to fill region with
            x (int): x coordinate of region to flood
            y (int): y coordinate of region to flood
        """
        label = self.clean_label(label)

        image = self.labels
        # Rescale click location to corresponding location in label array
        hole_fill_seed = (int(y), int(x))
        # Check current label
        old_label = image[hole_fill_seed]

        # Flood region with label
        # helps prevents hole fill from spilling into background
        connectivity = 1 if old_label == 0 else 2
        flooded = flood_fill(image, hole_fill_seed, label, connectivity=connectivity)
        self.labels = flooded

    def action_watershed(self, label, x1, y1, x2, y2):
        """Use watershed to segment different objects"""
        # Pull the label that is being split and find a new valid label
        current_label = label
        new_label = self.new_label

        # define the bounding box to apply the transform on and select
        # appropriate sections of 3 inputs (raw, seeds, annotation mask)
        props = regionprops(np.squeeze(np.int32(self.labels == current_label)))
        top, left, bottom, right = props[0].bbox

        # Pull the 2 seed locations and store locally
        # define a new seeds labeled img the same size as raw/annotation imgs
        seeds = np.zeros(self.labels.shape)
        seeds[int(y1), int(x1)] = current_label
        seeds[int(y2), int(x2)] = new_label

        # store these subsections to run the watershed on
        raw = np.copy(self.raw[top:bottom, left:right])
        label = np.copy(self.labels[top:bottom, left:right])
        seeds = np.copy(seeds[top:bottom, left:right])

        # contrast adjust the raw image to assist the transform
        raw = rescale_intensity(raw)

        # apply watershed transform to the subsections
        results = watershed(-raw, seeds, mask=label.astype(bool))

        # did watershed effectively create a new label
        num_new_pixels = np.count_nonzero(
            np.logical_and(results == new_label, label == current_label)
        )

        # Dilate small new labels
        # New label is "brightest" so will expand over other labels and increase area
        if num_new_pixels < 5:
            results = dilation(results, disk(3))

        # watershed may only leave a few pixels of old label
        num_old_pixels = np.count_nonzero(results == current_label)
        if num_old_pixels < 5:
            # Dilate to prevent "dimmer" label from being eroded by the "brighter" label
            dilated = dilation(np.where(results == current_label, results, 0), disk(3))
            results = np.where(dilated == current_label, dilated, results)

        # Update labels where watershed changed label
        label = np.where(
            np.logical_and(results == new_label, label == current_label), results, label
        )

        # Write new labels back to original label image
        self.labels[top:bottom, left:right] = label

    def action_threshold(self, y1, x1, y2, x2, label):
        """
        Threshold the raw image for annotation prediction within the
        user-determined bounding box.

        Args:
            y1 (int): first y coordinate to bound threshold area
            x1 (int): first x coordinate to bound threshold area
            y2 (int): second y coordinate to bound threshold area
            x2 (int): second x coordinate to bound threshold area
            label (int): label drawn in threshold area
        """
        label = self.clean_label(label)
        top = min(y1, y2)
        bottom = max(y1, y2) + 1
        left = min(x1, x2)
        right = max(x1, x2) + 1

        # pull out the selection portion of the raw frame
        predict_area = self.raw_frame[top:bottom, left:right]

        # triangle threshold picked after trying a few on one dataset
        # may not be the best threshold approach for other datasets!
        # pick two thresholds to use hysteresis thresholding strategy
        threshold = filters.threshold_triangle(image=predict_area.astype('float64'))
        threshold_stringent = 1.10 * threshold

        # try to keep stray pixels from appearing
        hyst = filters.apply_hysteresis_threshold(
            image=predict_area, low=threshold, high=threshold_stringent
        )
        ann_threshold = np.where(hyst, label, 0)

        # put prediction in without overwriting
        predict_area = self.labels[top:bottom, left:right]
        safe_overlay = np.where(predict_area == 0, ann_threshold, predict_area)

        self.labels[top:bottom, left:right] = safe_overlay

    def action_active_contour(self, label, min_pixels=20, iterations=100):
        labels = np.copy(self.labels)

        # get centroid of selected label
        props = regionprops(np.where(labels == label, label, 0))[0]

        # make bounding box size to encompass some background
        box_height = props['bbox'][2] - props['bbox'][0]
        top = max(0, props['bbox'][0] - box_height // 2)
        bottom = min(self.project.height, props['bbox'][2] + box_height // 2)

        box_width = props['bbox'][3] - props['bbox'][1]
        left = max(0, props['bbox'][1] - box_width // 2)
        right = min(self.project.width, props['bbox'][3] + box_width // 2)

        # relevant region of label image to work on
        labels = labels[top:bottom, left:right]

        # use existing label as initial level set for contour calculations
        level_set = np.where(labels == label, 1, 0)

        # normalize input 2D frame data values to range [0.0, 1.0]
        adjusted_raw_frame = Normalize()(self.raw)
        predict_area = adjusted_raw_frame[top:bottom, left:right]

        # returns 1 where label is predicted to be based on contouring, 0 background
        contoured = morphological_chan_vese(
            predict_area, iterations, init_level_set=level_set
        )

        # contoured area should get original label value
        contoured_label = contoured * label
        # contours tend to fit very tightly, a small expansion here works well
        contoured_label = dilation(contoured_label, disk(3))

        # don't want to leave the original (un-contoured) label in the image
        # never overwrite other labels with new contoured label
        cond = np.logical_or(labels == label, labels == 0)
        safe_overlay = np.where(cond, contoured_label, labels)

        # label must be present in safe_overlay for this to be a valid contour result
        # very few pixels of contoured label indicate contour prediction not worth keeping
        pixel_count = np.count_nonzero(safe_overlay == label)
        if pixel_count < min_pixels:
            safe_overlay = np.copy(self.labels[top:bottom, left:right])

        # put it back in the full image so can use centroid coords for post-contour cleanup
        full_frame = np.copy(self.labels)
        full_frame[top:bottom, left:right] = safe_overlay

        # avoid automated label cleanup if centroid (flood seed point) is not the right label
        if full_frame[int(props['centroid'][0]), int(props['centroid'][1])] != label:
            image_trimmed = full_frame
        else:
            # morphology and logic used by pixel-trimming action, with object centroid as seed
            contiguous_label = flood(
                image=full_frame,
                seed_point=(int(props['centroid'][0]), int(props['centroid'][1])),
            )

            # any pixels in image_ann that have value 'label' and are NOT connected to
            # hole_fill_seed get changed to 0, all other pixels retain their original value
            image_trimmed = np.where(
                np.logical_and(np.invert(contiguous_label), full_frame == label),
                0,
                full_frame,
            )

        self.labels[top:bottom, left:right] = image_trimmed[top:bottom, left:right]

    def action_erode(self, label):
        """
        Use morphological erosion to incrementally shrink the selected label.
        """
        image = self.labels
        # Isolate the label and erode it
        masked = np.where(image == label, label, 0)
        eroded = erosion(masked, square(3))
        # Put the eroded label back in the original image
        image = np.where(image == label, eroded, image)
        self.labels = image

    def action_dilate(self, label):
        """
        Use morphological dilation to incrementally increase the selected label.
        Does not overwrite bordering labels.
        """
        image = self.labels
        masked = np.where(image == label, label, 0)
        dilated = dilation(masked, square(3))
        self.labels = np.where(
            np.logical_and(dilated == label, image == 0), dilated, image
        )
