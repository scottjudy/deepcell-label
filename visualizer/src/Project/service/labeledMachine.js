import { actions, assign, Machine, send } from 'xstate';
import { fromEventBus } from './eventBus';

const { respond } = actions;

const createLabeledMachine = ({ projectId, eventBuses }) =>
  Machine(
    {
      invoke: [
        { id: 'eventBus', src: fromEventBus('labeled', () => eventBuses.labeled) },
        { src: fromEventBus('labeled', () => eventBuses.load) },
      ],
      context: {
        projectId,
        numFeatures: 1,
        feature: 0,
        featureNames: ['feature 0'],
        labelsOpacity: [0, 0.3],
        outlineOpacity: [0.5, 1],
        highlight: true,
        outline: true,
      },
      on: {
        DIMENSIONS: { actions: 'setNumFeatures' },
        SET_FEATURE: { actions: ['setFeature', 'sendToEventBus'] },
        TOGGLE_HIGHLIGHT: { actions: 'toggleHighlight' },
        TOGGLE_OUTLINE: { actions: 'toggleOutline' },
        SET_LABELS_OPACITY: { actions: 'setLabelsOpacity' },
        SET_OUTLINE_OPACITY: { actions: 'setOutlineOpacity' },
        SAVE: { actions: 'save' },
        RESTORE: { actions: ['restore', respond('RESTORED')] },
      },
    },
    {
      actions: {
        setOutlineOpacity: assign({ outlineOpacity: (ctx, event) => event.opacity }),
        setLabelsOpacity: assign({ labelsOpacity: (ctx, event) => event.opacity }),
        setNumFeatures: assign({
          numFeatures: (ctx, evt) => evt.numFeatures,
          featureNames: (ctx, evt) => [...Array(evt.numFeatures).keys()].map((i) => `feature ${i}`),
        }),
        setFeature: assign({ feature: (_, { feature }) => feature }),
        toggleHighlight: assign({ highlight: ({ highlight }) => !highlight }),
        toggleOutline: assign({ outline: ({ outline }) => !outline }),
        save: respond(({ feature }) => ({ type: 'RESTORE', feature })),
        restore: send((_, { feature }) => ({ type: 'SET_FEATURE', feature })),
        sendToEventBus: send((c, e) => e, { to: 'eventBus' }),
      },
    }
  );

export default createLabeledMachine;
