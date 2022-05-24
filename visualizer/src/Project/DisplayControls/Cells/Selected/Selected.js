import AddIcon from '@mui/icons-material/Add';
import ArrowBackIosNewIcon from '@mui/icons-material/ArrowBackIosNew';
import ArrowForwardIosIcon from '@mui/icons-material/ArrowForwardIos';
import ClearIcon from '@mui/icons-material/Clear';
import Box from '@mui/material/Box';
import IconButton from '@mui/material/IconButton';
import Tooltip from '@mui/material/Tooltip';
import { useSelector } from '@xstate/react';
import { bind } from 'mousetrap';
import React, { useEffect, useState } from 'react';
import { useHexColormap, useSelect } from '../../../ProjectContext';
import Cell from '../Cell';
import { contrast } from './utils';

function SelectedBox() {
  const select = useSelect();
  const { send } = select;
  const selected = useSelector(select, (state) => state.context.selected);

  const colormap = useHexColormap();
  const color = colormap[selected] ?? '#000000';

  useEffect(() => {
    bind('n', () => select.send('SELECT_NEW'));
    bind('[', () => select.send('SELECT_PREVIOUS'));
    bind(']', () => select.send('SELECT_NEXT'));
  }, [select]);

  const [showButtons, setShowButtons] = useState(false);
  const buttonColor = '#000000';
  const temp = contrast(color, '#000000') > contrast(color, '#FFFFFF') ? '#000000' : '#FFFFFF';

  const newTooltip = (
    <span>
      New <kbd>N</kbd>
    </span>
  );

  const resetTooltip = (
    <span>
      Reset <kbd>Esc</kbd>
    </span>
  );

  const prevTooltip = (
    <span>
      Previous <kbd>[</kbd>
    </span>
  );

  const nextTooltip = (
    <span>
      Next <kbd>]</kbd>
    </span>
  );

  return (
    <Box
      sx={{
        position: 'relative',
        // width: (theme) => theme.spacing(8),
        // height: (theme) => theme.spacing(8),
        display: 'flex',
        alignContent: 'center',
        justifyContent: 'center',
        p: 1,
      }}
      onMouseEnter={() => setShowButtons(true)}
      onMouseLeave={() => setShowButtons(false)}
    >
      {/* <Box
        sx={{
          // position: 'absolute',
          width: (theme) => theme.spacing(8),
          height: (theme) => theme.spacing(8),
          // border: (theme) => `${theme.spacing(0.5)} solid #DDDDDD`,
          display: 'flex',
          alignContent: 'center',
          justifyContent: 'center',
          // background: color,
        }}
      > */}
      <Cell cell={selected} />
      {/* </Box> */}
      {/* <Typography
          sx={{
            color: buttonColor,
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
          }}
        >
          {selected}
        </Typography> */}
      {showButtons && (
        <Tooltip title={newTooltip}>
          <IconButton
            sx={{ position: 'absolute', top: -5, left: -5 }}
            size='small'
            onClick={() => send('SELECT_NEW')}
          >
            <AddIcon sx={{ color: buttonColor }} />
          </IconButton>
        </Tooltip>
      )}
      {showButtons && (
        <Tooltip title={resetTooltip}>
          <IconButton
            sx={{ position: 'absolute', top: -5, right: -5 }}
            size='small'
            onClick={() => send('RESET')}
          >
            <ClearIcon sx={{ color: buttonColor }} />
          </IconButton>
        </Tooltip>
      )}
      {showButtons && (
        <Tooltip title={prevTooltip}>
          <IconButton
            sx={{ position: 'absolute', bottom: -5, left: -5 }}
            size='small'
            onClick={() => send('SELECT_PREVIOUS')}
          >
            <ArrowBackIosNewIcon sx={{ color: buttonColor }} />
          </IconButton>
        </Tooltip>
      )}
      {showButtons && (
        <Tooltip title={nextTooltip}>
          <IconButton
            sx={{ position: 'absolute', bottom: -5, right: -5 }}
            size='small'
            onClick={() => send('SELECT_NEXT')}
          >
            <ArrowForwardIosIcon sx={{ color: buttonColor }} />
          </IconButton>
        </Tooltip>
      )}
      {/* </Box> */}
    </Box>
  );
}

export default SelectedBox;
