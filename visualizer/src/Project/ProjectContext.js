import { useSelector } from '@xstate/react';
import React, { createContext, useContext, useEffect, useRef, useState } from 'react';

export const Context = createContext();

export const useProject = () => {
  return useReturnContext(Context);
};

function useReturnContext(contextType) {
  const context = useContext(contextType);
  if (context === undefined) {
    throw new Error(`${contextType} must be used within its appropriate parent provider`);
  }
  return context;
}

export function useSpots() {
  const project = useProject();
  const spots = useSelector(project, (state) => state.context.spotsRef);
  return spots;
}

export function useLineage() {
  const project = useProject();
  const spots = useSelector(project, (state) => state.context.lineageRef);
  return spots;
}

const emptyDivision = {
  parent: null,
  daughters: [],
  divisionFrame: null,
  parentDivisionFrame: null,
  frames: [],
};

export function useDivision(label) {
  const lineage = useLineage();
  const division = lineage[label] || emptyDivision;
  return division;
}

export function useArrays() {
  const project = useProject();
  const arrays = useSelector(project, (state) => state.context.arraysRef);
  return arrays;
}

export function useLabels() {
  const project = useProject();
  const labels = useSelector(project, (state) => state.context.labelsRef);
  return labels;
}

export function useSelect() {
  const project = useProject();
  const select = useSelector(project, (state) => state.context.selectRef);
  return select;
}

export function useTracking(label) {
  const project = useProject();
  const tracking = useSelector(project, (state) => {
    const labelMode = state.context.toolRef;
    const track = labelMode.state.context.trackRef;
    return track;
  });
  return tracking;
}

export function useApi() {
  const project = useProject();
  const api = useSelector(project, (state) => state.context.apiRef);
  return api;
}

export function useUndo() {
  const project = useProject();
  const undo = useSelector(project, (state) => state.context.undoRef);
  return undo;
}

export function useImage() {
  const project = useProject();
  const image = useSelector(project, (state) => state.context.imageRef);
  return image;
}

export function useRaw() {
  const project = useProject();
  const raw = useSelector(project, (state) => {
    const image = state.context.imageRef;
    const raw = image.state.context.rawRef;
    return raw;
  });
  return raw;
}

export function useLabeled() {
  const project = useProject();
  const labeled = useSelector(project, (state) => {
    const image = state.context.imageRef;
    const labeled = image.state.context.labeledRef;
    return labeled;
  });
  return labeled;
}

export function useFeature() {
  const project = useProject();
  const feature = useSelector(project, (state) => {
    const image = state.context.imageRef;
    const labeled = image.state.context.labeledRef;
    const features = labeled.state.context.features;
    const feature = labeled.state.context.feature;
    return features[feature];
  });
  return feature;
}

export function useChannel(channelId) {
  const project = useProject();
  const channel = useSelector(project, (state) => {
    const image = state.context.imageRef;
    const raw = image.state.context.rawRef;
    const channels = raw.state.context.channels;
    return channels[channelId];
  });
  return channel;
}

export function useLayers() {
  const project = useProject();
  const layers = useSelector(project, (state) => {
    const image = state.context.imageRef;
    const raw = image.state.context.rawRef;
    const layers = raw.state.context.layers;
    return layers;
  });
  return layers;
}

export function useComposeLayers() {
  const canvas = useCanvas();
  const width = useSelector(canvas, (state) => state.context.width);
  const height = useSelector(canvas, (state) => state.context.height);

  // keys: layer index, values: canvas with image of each layer
  const [canvases, setCanvases] = useState({});

  const canvasRef = useRef();
  const ctxRef = useRef();

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    ctx.globalCompositeOperation = 'source-over';
    ctxRef.current = ctx;
  }, [height, width]);

  useEffect(() => {
    const ctx = ctxRef.current;
    ctx.clearRect(0, 0, width, height);
    Object.values(canvases).forEach((canvas) => ctx.drawImage(canvas, 0, 0));
  });

  return [canvasRef, canvases, setCanvases];
}

export function useCanvas() {
  const project = useProject();
  const canvas = useSelector(project, (state) => state.context.canvasRef);
  return canvas;
}

export function useLabelMode() {
  const project = useProject();
  const labelMode = useSelector(project, (state) => state.context.toolRef);
  return labelMode;
}

export function useSegment() {
  const project = useProject();
  const segment = useSelector(project, (state) => {
    const tool = state.context.toolRef;
    const segment = tool.state.context.segmentRef;
    return segment;
  });
  return segment;
}

export function useTrack() {
  const project = useProject();
  const track = useSelector(project, (state) => {
    const tool = state.context.toolRef;
    const track = tool.state.context.trackRef;
    return track;
  });
  return track;
}

export function useBrush() {
  const project = useProject();
  const tool = useSelector(project, (state) => {
    const labelMode = state.context.toolRef;
    const segment = labelMode.state.context.segmentRef;
    const tools = segment.state.context.tools;
    return tools.brush;
  });
  return tool;
}

export function useThreshold() {
  const project = useProject();
  const tool = useSelector(project, (state) => {
    const labelMode = state.context.toolRef;
    const segment = labelMode.state.context.segmentRef;
    const tools = segment.state.context.tools;
    return tools.threshold;
  });
  return tool;
}

function componentToHex(c) {
  var hex = c.toString(16);
  return hex.length === 1 ? '0' + hex : hex;
}

function rgbToHex(rgb) {
  return '#' + componentToHex(rgb[0]) + componentToHex(rgb[1]) + componentToHex(rgb[2]);
}

export function useHexColormap() {
  const labels = useLabels();
  const colormap = useSelector(labels, (state) => state.context.colormap);
  return colormap.map(rgbToHex);
}

const gl2 = !!document.createElement('canvas').getContext('webgl2');
const gl = !!document.createElement('canvas').getContext('webgl');

/** Creates a reference to a canvas with an alpha channel to use with a GPU.js kernel. */
export function useAlphaKernelCanvas() {
  const project = useProject();
  const [canvas, setCanvas] = useState(document.createElement('canvas'));

  useEffect(() => {
    const canvas = document.createElement('canvas');
    if (gl2) {
      canvas.getContext('webgl2', { premultipliedAlpha: false });
    } else if (gl) {
      canvas.getContext('webgl', { premultipliedAlpha: false });
    }
    setCanvas(canvas);
  }, [project]);

  return canvas;
}

/** Creates a canvas with the same dimensions as the project. */
export function usePixelatedCanvas() {
  const [canvas] = useState(document.createElement('canvas'));

  const canvasMachine = useCanvas();
  const width = useSelector(canvasMachine, (state) => state.context.width);
  const height = useSelector(canvasMachine, (state) => state.context.height);

  useEffect(() => {
    canvas.width = width;
    canvas.height = height;
  }, [canvas, height, width]);

  return canvas;
}

/** Creates a canvas with the same resolution as the displayed canvas.. */
export function useFullResolutionCanvas() {
  const [canvas] = useState(document.createElement('canvas'));

  const canvasMachine = useCanvas();
  const sw = useSelector(canvasMachine, (state) => state.context.width);
  const sh = useSelector(canvasMachine, (state) => state.context.height);
  const scale = useSelector(canvasMachine, (state) => state.context.scale);
  const width = sw * scale * window.devicePixelRatio;
  const height = sh * scale * window.devicePixelRatio;

  useEffect(() => {
    canvas.width = width;
    canvas.height = height;
  }, [canvas, height, width]);

  return canvas;
}

function ProjectContext({ project, children }) {
  return <Context.Provider value={project}>{children}</Context.Provider>;
}

export default ProjectContext;
