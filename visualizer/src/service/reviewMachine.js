/**
 * Root statechart for DeepCell Label in XState.
 */
import { assign, Machine, spawn } from 'xstate';
import createProjectMachine from './projectMachine';

// TODO: refactor bucket
function createReviewMachine(projectIds, bucket) {
  return Machine(
    {
      id: 'review',
      context: {
        projectIds,
        bucket,
        projectId: projectIds[0],
        projects: {},
        judgments: {},
      },
      entry: 'spawnProjects',
      initial: 'idle',
      states: {
        idle: {},
      },
      on: {
        SET_PROJECT: { actions: 'setProject' },
        ACCEPT: { actions: ['accept', 'nextProject'] },
        REJECT: { actions: ['reject', 'nextProject'] },
      },
    },
    {
      actions: {
        spawnProjects: assign({
          projects: ({ projectIds, bucket }) =>
            Object.fromEntries(
              projectIds.map((projectId) => [
                projectId,
                // TODO: refactor buckets
                spawn(createProjectMachine(projectId, bucket)),
              ])
            ),
        }),
        setProject: assign({
          projectId: (_, { projectId }) => projectId,
        }),
        accept: assign({
          judgments: ({ judgments, projectId }) => {
            judgments[projectId] = true;
            return judgments;
          },
        }),
        reject: assign({
          judgments: ({ judgments, projectId }) => {
            judgments[projectId] = false;
            return judgments;
          },
        }),
        nextProject: assign({
          projectId: ({ judgments, projectIds, projectId }) => {
            const index = projectIds.indexOf(projectId);
            const reordered = projectIds.slice(index + 1).concat(projectIds.slice(0, index));
            return reordered.find((id) => !(id in judgments)) || projectId;
          },
        }),
      },
    }
  );
}

export default createReviewMachine;
