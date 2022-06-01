import { useSelector } from '@xstate/react';
import React, { useCallback } from 'react';
import { useSegment } from '../../../ProjectContext';
import ToolButton from './ToolButton';

function SelectButton(props) {
  const segment = useSegment();
  const tool = useSelector(segment, (state) => state.context.tool);

  const onClick = useCallback(() => segment.send({ type: 'SET_TOOL', tool: 'select' }), [segment]);

  const tooltipText = <span>Click to select a label</span>;

  return (
    <ToolButton
      {...props}
      value='select'
      hotkey='v'
      tooltipText={tooltipText}
      selected={tool === 'select'}
      onClick={onClick}
    >
      Select
    </ToolButton>
  );
}

export default SelectButton;
