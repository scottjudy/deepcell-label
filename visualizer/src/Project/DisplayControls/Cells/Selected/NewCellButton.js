import AddIcon from '@mui/icons-material/Add';
import IconButton from '@mui/material/IconButton';
import Tooltip from '@mui/material/Tooltip';
import React from 'react';
import { useSelect } from '../../../ProjectContext';

function NewCellButton({ sx }) {
  const select = useSelect();

  const tooltip = (
    <span>
      New <kbd>N</kbd>
    </span>
  );

  return (
    <Tooltip title={tooltip}>
      <IconButton sx={sx} size='small' onClick={() => select.send('SELECT_NEW')}>
        <AddIcon />
      </IconButton>
    </Tooltip>
  );
}

export default NewCellButton;
