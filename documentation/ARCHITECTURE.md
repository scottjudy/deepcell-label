# DeepCell Label Architecture

DeepCell

Details on how to host these each of these

## Python backend

The backend is a Python based Flask application that

- loads files into the database and bucket
- accesses projects for the client
- edits the segmentation
- exports the project

### Loading projects

To create a DeepCell Label project, send a POST request with a form to `/api/project`. See the [DeepCell Label zip file format](LABEL_FILE_FORMAT.md#supported-input-files) for details on the form contents.

The DeepCell Label homepage uses a similar route `/api/project/dropped` that attaches a dragged and dropped file to the request.

### Accessing projects

The client fetches project data through `/api/project/<ID>`. As this route provides access to projects, the S3 bucket with project zip files can be private. The route looks up the URL for the project zip in the database, then downloads and forwards the zip file to the client.

### Editing segmentation

The client edits the segmentation image with the `/api/edit` route. The route uses an attached zip file containing the data to edit and responds with a zip file with the edited segmentation image and cells.

See [DeepCell Label zip format](LABEL_FILE_FORMAT.md#edit-and-export-zips) for how to send data to `/api/edit`.

### Exporting projects

DeepCell Label has a Submit button that sends the edited labels to the `/api/upload` route, creates a zip, and uploads the zip to an S3 bucket.

When opening a DeepCell Lable link with `download=true`, the page shows a Download button instead of Submit. The button calls `/api/download` which responds with the zip for the client to download.

See [DeepCell Label zip format](LABEL_FILE_FORMAT.md#edit-and-export-zips) for how to send data to these routes.

## Client

The client is a [React](https://reactjs.org/) based user interface with [XState](https://xstate.js.org/docs/) based state management.

### React UI

The top level component is [App.js](../visualizer/src/App.js), which provides a [NavBar](../visualizer/src/Navbar.js) and [Footer](../visualizer/src/Footer/Footer.js) for all pages and routing with [React Router](https://reactrouter.com/).

App.js routes between three pages:

- `/` shows Load, a homepage that can create project from drag-and-dropped files or example files
- `/loading` shows Loading, a page for redirecting from deepcell.org/predict that shows a loading animation or error messages
- `/project` shows Project, a page for viewing and editing projects

#### Components within Project

When viewing a project on the `/project` page, there must be a project ID provided in the `projectId` parameter.

When only one project ID is provided, we load the project with Load.js, while when multiple comma separated project IDs are provided, we load all of them with LoadReview.js, start and show a dropdown to switch between projects..

- compose canvas

### State management

The React components use hooks defined in [`ProjectContext.js`](../visualizer/src/Project/ProjectContext.js) to access and render the state.

<!-- insert diagram of spawned actors -->

The root level machine spawns child actors and sets up event buses for these actors to communicate with each other.

Here's a tree diagram of the spawned state machines. The root project state machine, and the child state machine The state machines with stars have event buses that they broadcast events on. The events they broadcast are shown in blue to the right of the state machine. The events that state machines listen to from these event buses on are shown to the left.

#### UI actors

These actors manage the interactions with the UI

- `canvasMachine`
  - interprets interactions with the canvas, like `mousemove`, `mouseup`, and `mousedown`
  - broadcasts `COORDINATES` and mouse events on its event bus
  - can switch between a panOnDrag that pans the canvas when clicking and dragging and a noPan state where the spacebar has to be held to click and drag to pan
- `hoveringMachine`
  - combines the coordinates from the canvas, the labeled array from arrays, and the cell labels from cells to detemine a list of cells under the cursor
  - broadcasts `HOVERING` events on its event bus when the hovering cells change
- `selectMachine`
  - tracks which cell is selected
  - updates the selected cell with `SELECT`, `SELECT_NEW`, `RESET`, `SELECT_PREVIOUS`, and `SELECT_NEXT` events
  - broadcasts SELECTED events on its event bus when the selected cell changes
- `imageMachine`
  - manages which time `t` of a timelapse to show
  - broadcast `T` events on its event bus when `t` changes
  - spawns `rawMachine`
    - manages which channel(s) to display
    - broadcasts `CHANNEL` events on its event bus
    - spawns an actor for each channel
    - spawns an actor for each layer in color mode
  - spawns `labeledMachine`
    - manages which segmentation to display and how to display it
    - broadcasts `FEATURE` events on its event bus
- `editMachine`
  - manages which tab of controls are open next to the canvas, such as display, segment, cells, divisions, or spots
  - for the tabs with controls to edit labels, it spawns a child actor to manage the tab that can send events to the respective labels machine to trigger an action that edits the labels, including
    - `editSegmentMachine`
    - `editCellsMachine`
    - `editDivisionsMachine`
    - each of these spawn actors for the tools it manages, and the tool actors send events to a label machine (e.g. `cellMachine`) to edit the labels

#### Labeled data

These state machine hold the labels and manage the logic to edit the labels.

- arrays
  - manages the raw image arrays and the segmentation images
  - spawns `segmentApiMachine` that communicates with the segmentation editing API on the Flask backend
- cells
  - manages the cells and how to edite them
  - edits the cells on `DELETE`, `SWAP`, `REPLACE`, and `NEW` events
- divisions
  - manage the divisions and how to edit them
  - edits the divisions on `ADD_DAUGHTER` and `REMOVE_DAUGHTER` events
  - updates divisions to stay in sync with cells when receiving `DELETE`, `SWAP`, `REPLACE`, and `NEW` events
- spots
  - manages the spots labels
  - no spots editing implemented yet

#### Data management

There are

- undo
- idb (IndexedDB)
- export

##### Undo

The undo machine keeps track of how many actions have been done, undone, or redone. It spawns a list of `uiHistoryMachine` to track an actor's state when each action starts, and it spawns a list of `labelHistoryMachine` to track the label changes caused by the actions.

An actor can send an REGISTER_UI event to the undo machine to create a `uiHistoryMachine` for that actor, or send a REGISTER_LABELS event to create a `labelHistoryMachine`.

An actor tracked with a `uiHistoryMachine` must

- respond with a RESTORE event that records its current state when it receives a SAVE event
- restore its state when it receives RESTORE event

An actor tracked with a `labelHistoryMachine` must

- send a SNAPSHOT event to the history machine when its labels are edited, containing the properties
  - edit, with a number for the action that the changes are part of
  - before, with an event that has the labels before the action
  - after, with an event that has the labels after the action
- restore its labels when receiving these before and after events

A `uiHistoryMachine` records its actor's state for every action, while `labelHistoryMachine` only records the state when it receives a snapshot from the actor.

##### IndexedDB persistence

The

Xst
