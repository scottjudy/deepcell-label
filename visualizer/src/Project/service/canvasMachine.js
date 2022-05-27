// Manages zooming, panning, and interacting with the canvas
// Interactions sent as COORDINATES, mousedown, and mouseup events to parent
// COORDINATES event sent when the pixel below the cursor changes

// Panning interface:
// Hold space always enables click & drag to pan
// SET_PAN_ON_DRAG event configures whether click & drag alone pans the canvas
// Features that need dragging interactions,
// like drawing or creating a bounding box, should set panOnDrag to false

import { actions, assign, forwardTo, Machine, send } from 'xstate';
import { fromEventBus } from './eventBus';

const { respond } = actions;

// Pans when dragging
const panOnDragState = {
  initial: 'idle',
  states: {
    idle: {
      entry: 'resetMove',
      on: {
        mousedown: 'pressed',
        mousemove: { actions: 'computeCoordinates' },
      },
    },
    // Sends mouseup events when panning < 10 pixels
    pressed: {
      on: {
        mousemove: [
          { cond: 'moved', target: 'dragged', actions: 'pan' },
          { actions: ['updateMove', 'pan'] },
        ],
        mouseup: { target: 'idle', actions: 'sendToEventBus' },
      },
    },
    dragged: {
      on: {
        mouseup: 'idle',
        mousemove: { actions: 'pan' },
      },
    },
  },
};

const noPanState = {
  on: {
    mousedown: { actions: 'sendToEventBus' },
    mouseup: { actions: 'sendToEventBus' },
    mousemove: { actions: 'computeCoordinates' },
  },
};

const interactiveState = {
  initial: 'checkDrag',
  states: {
    checkDrag: {
      always: [{ cond: 'panOnDrag', target: 'panOnDrag' }, 'noPan'],
    },
    panOnDrag: panOnDragState,
    noPan: noPanState,
  },
  on: {
    SET_PAN_ON_DRAG: { target: '.checkDrag', actions: 'setPanOnDrag' },
  },
};

const grabState = {
  initial: 'idle',
  states: {
    idle: {
      on: {
        mousedown: { target: 'panning' },
        mousemove: { actions: 'computeCoordinates' },
      },
    },
    panning: {
      on: {
        mouseup: 'idle',
        mousemove: { actions: 'pan' },
      },
    },
  },
};

const movingState = {
  initial: 'idle',
  states: {
    idle: {},
    moving: {
      after: {
        200: 'idle',
      },
    },
  },
  on: {
    SET_POSITION: { target: '.moving', actions: 'setPosition' },
  },
};

const createCanvasMachine = ({ undoRef, eventBuses }) =>
  Machine(
    {
      id: 'canvas',
      entry: send('REGISTER_UI', { to: undoRef }),
      context: {
        // raw dimensions of image
        width: 1,
        height: 1,
        availableWidth: 1,
        availableHeight: 1,
        padding: 5,
        scale: 1, // how much the canvas is scaled to fill the available space
        zoom: 1, // how much the image is scaled within the canvas
        // position of canvas within image
        sx: 0,
        sy: 0,
        // position of cursor within image
        x: 0,
        y: 0,
        // how much the canvas has moved in the current pan
        dx: 0,
        dy: 0,
        panOnDrag: true,
      },
      invoke: [
        { id: 'eventBus', src: fromEventBus('canvas', () => eventBuses.canvas) },
        { src: fromEventBus('canvas', () => eventBuses.load) },
        { src: 'listenForMouseUp' },
        { src: 'listenForZoomHotkeys' },
        { src: 'listenForSpace' },
      ],
      on: {
        DIMENSIONS: { actions: ['setDimensions', 'resize'] },
        wheel: { actions: 'zoom' },
        ZOOM_IN: { actions: 'zoomIn' },
        ZOOM_OUT: { actions: 'zoomOut' },
        AVAILABLE_SPACE: { actions: ['setSpace', 'resize'] },
        SAVE: {
          actions: respond((ctx) => ({
            type: 'RESTORE',
            sx: ctx.sx,
            sy: ctx.sy,
            zoom: ctx.zoom,
          })),
        },
        RESTORE: { actions: ['restore', respond('RESTORED')] },
        COORDINATES: {
          cond: 'newCoordinates',
          actions: ['setCoordinates', forwardTo('eventBus')],
        },
        'keydown.Space': '.pan.grab',
        'keyup.Space': '.pan.interactive',
      },
      type: 'parallel',
      states: {
        pan: {
          initial: 'interactive',
          states: {
            interactive: interactiveState,
            grab: grabState,
          },
        },
        moving: movingState,
      },
    },
    {
      services: {
        listenForMouseUp: () => (send) => {
          const listener = (e) => send(e);
          window.addEventListener('mouseup', listener);
          return () => window.removeEventListener('mouseup', listener);
        },
        listenForSpace: () => (send) => {
          const downListener = (e) => {
            if (e.key === ' ' && !e.repeat) {
              send('keydown.Space');
            }
          };
          const upListener = (e) => {
            if (e.key === ' ') {
              send('keyup.Space');
            }
          };
          window.addEventListener('keydown', downListener);
          window.addEventListener('keyup', upListener);
          return () => {
            window.removeEventListener('keydown', downListener);
            window.removeEventListener('keyup', upListener);
          };
        },
        listenForZoomHotkeys: () => (send) => {
          const listener = (e) => {
            if (e.key === '=') {
              send('ZOOM_IN');
            }
            if (e.key === '-') {
              send('ZOOM_OUT');
            }
          };
          window.addEventListener('keydown', listener);
          return () => window.removeEventListener('keydown', listener);
        },
      },
      guards: {
        newCoordinates: (ctx, evt) => ctx.x !== evt.x || ctx.y !== evt.y,
        moved: (ctx) => Math.abs(ctx.dx) > 10 || Math.abs(ctx.dy) > 10,
        panOnDrag: (ctx) => ctx.panOnDrag,
      },
      actions: {
        setDimensions: assign({
          width: (ctx, evt) => evt.width,
          height: (ctx, evt) => evt.height,
        }),
        updateMove: assign({
          dx: (ctx, evt) => ctx.dx + evt.movementX,
          dy: (ctx, evt) => ctx.dy + evt.movementY,
        }),
        resetMove: assign({ dx: 0, dy: 0 }),
        restore: assign((_, { type, ...savedContext }) => savedContext),
        setCoordinates: assign((_, { x, y }) => ({ x, y })),
        computeCoordinates: send((ctx, evt) => {
          const { scale, zoom, width, height, sx, sy } = ctx;
          let x = Math.floor(evt.nativeEvent.offsetX / scale / zoom + sx);
          let y = Math.floor(evt.nativeEvent.offsetY / scale / zoom + sy);
          x = Math.max(0, Math.min(x, width - 1));
          y = Math.max(0, Math.min(y, height - 1));
          return { type: 'COORDINATES', x, y };
        }),
        setSpace: assign({
          availableWidth: (_, evt) => evt.width,
          availableHeight: (_, evt) => evt.height,
          padding: (_, evt) => evt.padding,
        }),
        resize: assign({
          scale: (ctx) => {
            const { width, height, availableWidth, availableHeight, padding } = ctx;
            const scaleX = (availableWidth - 2 * padding) / width;
            const scaleY = (availableHeight - 2 * padding) / height;
            // pick scale that fits both dimensions; can be less than 1
            const scale = Math.min(scaleX, scaleY);
            return scale;
          },
        }),
        setPosition: assign({
          sx: (ctx, evt) => evt.sx,
          sy: (ctx, evt) => evt.sy,
          zoom: (ctx, evt) => evt.zoom,
        }),
        pan: send((ctx, evt) => {
          const dx = (-1 * evt.movementX) / ctx.zoom / ctx.scale;
          const sx = Math.max(0, Math.min(ctx.sx + dx, ctx.width * (1 - 1 / ctx.zoom)));
          const dy = (-1 * evt.movementY) / ctx.zoom / ctx.scale;
          const sy = Math.max(0, Math.min(ctx.sy + dy, ctx.height * (1 - 1 / ctx.zoom)));
          return { type: 'SET_POSITION', sx, sy, zoom: ctx.zoom };
        }),
        zoom: send((ctx, evt) => {
          const zoomFactor = 1 + evt.deltaY / window.innerHeight;
          const newZoom = Math.max(ctx.zoom * zoomFactor, 1);
          const propX = evt.nativeEvent.offsetX / ctx.scale;
          const propY = evt.nativeEvent.offsetY / ctx.scale;

          let newSx = ctx.sx + propX * (1 / ctx.zoom - 1 / newZoom);
          newSx = Math.min(newSx, ctx.width * (1 - 1 / newZoom));
          newSx = Math.max(newSx, 0);

          let newSy = ctx.sy + propY * (1 / ctx.zoom - 1 / newZoom);
          newSy = Math.min(newSy, ctx.height * (1 - 1 / newZoom));
          newSy = Math.max(newSy, 0);

          return { type: 'SET_POSITION', zoom: newZoom, sx: newSx, sy: newSy };
        }),
        zoomIn: send((ctx) => {
          const { zoom, width, height, sx, sy } = ctx;
          const newZoom = 1.1 * zoom;
          const propX = width / 2;
          const propY = height / 2;
          const newSx = sx + propX * (1 / zoom - 1 / newZoom);
          const newSy = sy + propY * (1 / zoom - 1 / newZoom);
          return { type: 'SET_POSITION', zoom: newZoom, sx: newSx, sy: newSy };
        }),
        zoomOut: send((ctx) => {
          const { zoom, width, height, sx, sy } = ctx;
          const newZoom = Math.max(zoom / 1.1, 1);
          const propX = width / 2;
          const propY = height / 2;
          let newSx = sx + propX * (1 / zoom - 1 / newZoom);
          newSx = Math.min(newSx, width * (1 - 1 / newZoom));
          newSx = Math.max(newSx, 0);
          let newSy = sy + propY * (1 / zoom - 1 / newZoom);
          newSy = Math.min(newSy, height * (1 - 1 / newZoom));
          newSy = Math.max(newSy, 0);
          return { type: 'SET_POSITION', zoom: newZoom, sx: newSx, sy: newSy };
        }),
        setPanOnDrag: assign({ panOnDrag: (_, evt) => evt.panOnDrag }),
        sendToEventBus: forwardTo('eventBus'),
      },
    }
  );

export default createCanvasMachine;
