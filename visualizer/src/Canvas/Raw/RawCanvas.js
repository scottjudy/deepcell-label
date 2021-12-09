import { useSelector } from '@xstate/react';
import React from 'react';
import { useRaw } from '../../ProjectContext';
import GrayscaleCanvas from './GrayscaleCanvas';
import RGBCanvas from './RGBCanvas';

export const RawCanvas = (props) => {
  const raw = useRaw();
  const isGrayscale = useSelector(raw, (state) => state.context.isGrayscale);

  return isGrayscale ? <GrayscaleCanvas {...props} /> : <RGBCanvas {...props} />;
};

export default RawCanvas;
