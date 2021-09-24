import { BrowserRouter as Router, Route, Switch } from 'react-router-dom';
import Label from './Label';
import ProjectContext from './ProjectContext';
import service from './service/service';

// inspect({
//   // options
//   // url: 'https://statecharts.io/inspect', // (default)
//   iframe: false // open in new window
// });

function App() {
  return (
    <Router>
      <Switch>
        <Route path='/'>
          <ProjectContext project={service}>
            <Label />
          </ProjectContext>
        </Route>
      </Switch>
    </Router>
  );
}

export default App;
