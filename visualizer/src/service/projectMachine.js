/**
 * Root statechart for DeepCell Label in XState.
 */
import { assign, Machine, send, spawn } from 'xstate';
import { pure } from 'xstate/lib/actions';
import createApiMachine from './apiMachine';
import createArraysMachine from './arraysMachine';
import createCanvasMachine from './canvasMachine';
import { EventBus } from './eventBus';
import createImageMachine from './imageMachine';
import createLabelsMachine from './labelsMachine';
import createSelectMachine from './selectMachine';
import createToolMachine from './tools/toolMachine';
import createUndoMachine from './undoMachine';

const createProjectMachine = (
  projectId,
  { numFrames, numFeatures, numChannels, height, width },
  bucket
) =>
  Machine(
    {
      id: `${projectId}`,
      context: {
        projectId,
        numFrames,
        numFeatures,
        numChannels,
        height,
        width,
        bucket,
        eventBuses: {
          canvas: new EventBus('canvas'),
          image: new EventBus('image'),
          labeled: new EventBus('labeled'),
          raw: new EventBus('raw'),
          select: new EventBus('select'),
          undo: new EventBus('undo'),
          api: new EventBus('api'),
          arrays: new EventBus('arrays'),
          labels: new EventBus('labels'),
        },
      },
      initial: 'setUpActors',
      states: {
        setUpActors: {
          entry: 'spawnActors',
          always: 'setUpUndo',
        },
        setUpUndo: {
          entry: 'addActorsToUndo',
          always: 'idle',
        },
        idle: {},
      },
    },
    {
      actions: {
        spawnActors: assign((context) => ({
          canvasRef: spawn(createCanvasMachine(context), 'canvas'),
          imageRef: spawn(createImageMachine(context), 'image'),
          apiRef: spawn(createApiMachine(context), 'api'),
          selectRef: spawn(createSelectMachine(context), 'select'),
          toolRef: spawn(createToolMachine(context), 'tool'),
          undoRef: spawn(createUndoMachine(context), 'undo'),
          arraysRef: spawn(createArraysMachine(context), 'arrays'),
          labelsRef: spawn(createLabelsMachine(context), 'labels'),
        })),
        addActorsToUndo: pure((context) => {
          const { canvasRef, toolRef, imageRef, selectRef } = context;
          return [
            send({ type: 'ADD_ACTOR', actor: canvasRef }, { to: 'undo' }),
            send({ type: 'ADD_ACTOR', actor: imageRef }, { to: 'undo' }),
            send({ type: 'ADD_ACTOR', actor: toolRef }, { to: 'undo' }),
            send({ type: 'ADD_ACTOR', actor: selectRef }, { to: 'undo' }),
          ];
        }),
      },
    }
  );

export default createProjectMachine;
