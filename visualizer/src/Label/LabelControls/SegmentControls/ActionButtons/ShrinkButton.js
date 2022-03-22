import React, { useCallback } from 'react';
import { useSegment } from '../../../../ProjectContext';
import ActionButton from './ActionButton';

function ShrinkButton(props) {
  const segment = useSegment();
  const onClick = useCallback(() => segment.send('ERODE'), [segment]);
  const tooltipText = (
    <span>
      Contracts a label by one pixel <kbd>Q</kbd>
    </span>
  );

  return (
    <ActionButton {...props} tooltipText={tooltipText} onClick={onClick} hotkey='q'>
      Shrink
    </ActionButton>
  );
}

export default ShrinkButton;
