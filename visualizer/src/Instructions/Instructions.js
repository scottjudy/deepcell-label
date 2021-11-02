import MuiAccordion from '@material-ui/core/Accordion';
import MuiAccordionDetails from '@material-ui/core/AccordionDetails';
import MuiAccordionSummary from '@material-ui/core/AccordionSummary';
import Box from '@material-ui/core/Box';
import { withStyles } from '@material-ui/core/styles';
import Tab from '@material-ui/core/Tab';
import Tabs from '@material-ui/core/Tabs';
import Typography from '@material-ui/core/Typography';
import PropTypes from 'prop-types';
import React from 'react';
import ActionInstructions from './ActionInstructions';
import CanvasInstructions from './CanvasInstructions';
import DisplayInstructions from './DisplayInstructions';
import SelectInstructions from './SelectInstructions';
import ToolInstructions from './ToolInstructions';

function TabPanel(props) {
  const { children, value, index, ...other } = props;

  return (
    <div
      role='tabpanel'
      hidden={value !== index}
      id={`simple-tabpanel-${index}`}
      aria-labelledby={`simple-tab-${index}`}
      {...other}
    >
      {value === index && (
        <Box p={3}>
          <Typography component='div'>{children}</Typography>
        </Box>
      )}
    </div>
  );
}

TabPanel.propTypes = {
  children: PropTypes.node,
  index: PropTypes.any.isRequired,
  value: PropTypes.any.isRequired,
};

const Accordion = withStyles({
  root: {
    border: '1px solid rgba(0, 0, 0, .125)',
    boxShadow: 'none',
    '&:not(:last-child)': {
      borderBottom: 0,
    },
    '&:before': {
      display: 'none',
    },
    '&$expanded': {
      margin: 'auto',
    },
  },
  expanded: {},
})(MuiAccordion);

const AccordionSummary = withStyles({
  root: {
    backgroundColor: 'rgba(0, 0, 0, .03)',
    borderBottom: '1px solid rgba(0, 0, 0, .125)',
    marginBottom: -1,
    minHeight: 56,
    '&$expanded': {
      minHeight: 56,
    },
  },
  content: {
    '&$expanded': {
      margin: '12px 0',
    },
  },
  expanded: {},
})(MuiAccordionSummary);

const AccordionDetails = withStyles(theme => ({
  root: {
    padding: 0,
    display: 'flex',
    flexDirection: 'column',
  },
}))(MuiAccordionDetails);

export default function Instructions() {
  const [expanded, setExpanded] = React.useState(false);

  const [value, setValue] = React.useState(0);

  const handleTabChange = (event, newValue) => {
    setValue(newValue);
  };

  const toggleExpanded = () => {
    setExpanded(!expanded);
  };

  const stopExpansion = event => {
    if (event.key === ' ') {
      event.preventDefault();
    }
  };

  return (
    <div>
      <Accordion
        square
        expanded={expanded}
        onChange={toggleExpanded}
        TransitionProps={{ unmountOnExit: true }}
      >
        <AccordionSummary
          aria-controls='panel1d-content'
          id='panel1d-header'
          onKeyUp={stopExpansion}
        >
          <Typography>Instructions (Click to expand/collapse)</Typography>
        </AccordionSummary>
        <AccordionDetails>
          <Tabs value={value} onChange={handleTabChange}>
            <Tab label='Display' />
            <Tab label='Canvas' />
            <Tab label='Select Labels' />
            <Tab label='Tools' />
            <Tab label='Actions' />
          </Tabs>
          <TabPanel value={value} index={0}>
            <DisplayInstructions />
          </TabPanel>
          <TabPanel value={value} index={1}>
            <CanvasInstructions />
          </TabPanel>
          <TabPanel value={value} index={2}>
            <SelectInstructions />
          </TabPanel>
          <TabPanel value={value} index={3}>
            <ToolInstructions />
          </TabPanel>
          <TabPanel value={value} index={4}>
            <ActionInstructions />
          </TabPanel>
        </AccordionDetails>
      </Accordion>
    </div>
  );
}
