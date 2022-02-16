import { fireEvent, render } from '@testing-library/react';
import { interpret } from 'xstate';
import createArraysMachine from '../service/arraysMachine';
import createCanvasMachine from '../service/canvasMachine';
import { EventBus } from '../service/eventBus';
import createSelectMachine from '../service/selectMachine';
import createSegmentMachine from '../service/tools/segmentMachine';
import Canvas from './Canvas';

const eventBuses = {
  canvas: new EventBus('canvas'),
  image: new EventBus('image'),
  labeled: new EventBus('labeled'),
  raw: new EventBus('raw'),
  select: new EventBus('select'),
  undo: new EventBus('undo'),
  api: new EventBus('api'),
  arrays: new EventBus('arrays'),
  labels: new EventBus('labels'),
};
const context = {
  projectId: 'testId',
  bucket: 'testBucket',
  eventBuses,
  numFeatures: 2,
  numChannels: 3,
  numFrames: 2,
  width: 100,
  height: 100,
};

let mockCanvasActor = interpret(createCanvasMachine(context)).start();
let mockArraysActor = interpret(createArraysMachine(context)).start();
let mockSelectActor = interpret(createSelectMachine(context), {
  parent: { send: jest.fn() },
}).start();
let mockSegmentActor = interpret(createSegmentMachine(context), {
  parent: { send: jest.fn() },
}).start();
jest.mock('../ProjectContext', () => ({
  useArrays: () => mockArraysActor,
  useCanvas: () => mockCanvasActor,
  useSegment: () => mockSegmentActor,
  useSelect: () => mockSelectActor,
}));

jest.mock('./ComposeCanvases', () => () => 'ComposeCanvases');
jest.mock('./Labeled/LabeledCanvas', () => () => 'LabeledCanvas');
jest.mock('./Labeled/OutlineCanvas', () => () => 'OutlineCanvas');
jest.mock('./Raw/RawCanvas', () => () => 'RawCanvas');
jest.mock('./Tool/BrushCanvas', () => () => 'BrushCanvas');
jest.mock('./Tool/ThresholdCanvas', () => () => 'ThresholdCanvas');

test('canvas sends interaction to actors', () => {
  const eventsSentToCanvas = [];
  mockCanvasActor.send = (event) => eventsSentToCanvas.push(event);
  render(<Canvas />);

  fireEvent.wheel(document.getElementById('canvasBox'));
  expect(eventsSentToCanvas.length).toEqual(1);
  fireEvent.mouseDown(document.getElementById('canvasBox'));
  expect(eventsSentToCanvas.length).toEqual(2);
  fireEvent.mouseMove(document.getElementById('canvasBox'));
  expect(eventsSentToCanvas.length).toEqual(3);
  fireEvent.mouseUp(document.getElementById('canvasBox'));
  // canvas machine also listens for mouseup events in case they happen off the canvas
  expect(eventsSentToCanvas.length).toBeGreaterThanOrEqual(4);
});
