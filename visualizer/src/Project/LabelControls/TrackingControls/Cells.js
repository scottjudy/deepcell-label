/**
 * Displays the selected cell and the cell under the cursor.
 */

import { Box, FormLabel } from '@mui/material';
import { useSelector } from '@xstate/react';
import { useCanvas, useLineage } from '../../ProjectContext';
import Cell from './Division/Cell';

function Cells() {
  const canvas = useCanvas();
  const hovering = useSelector(canvas, (state) => state.context.hovering);

  const lineage = useLineage();
  const selected = useSelector(lineage, (state) => state.context.selected);
  return (
    <Box display='flex'>
      <Box sx={{ display: 'flex', width: '50%', flexDirection: 'column' }}>
        <FormLabel>Selected</FormLabel>
        <Box sx={{ display: 'flex' }}>
          {selected ? (
            <Cell label={selected} />
          ) : (
            // Render hidden cell to reserve space when no cell is shown.
            <Box sx={{ display: 'flex', visibility: 'hidden' }}>
              <Cell label={1} />
            </Box>
          )}
        </Box>
      </Box>
      <Box sx={{ display: 'flex', width: '50%', flexDirection: 'column', alignItems: 'flex-end' }}>
        <FormLabel>Hovering</FormLabel>
        {hovering !== null && <Cell label={hovering} />}
      </Box>
    </Box>
  );
}

export default Cells;
