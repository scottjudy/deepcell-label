import { useSelector } from '@xstate/react';
import React, { useEffect, useRef } from 'react';
import { useCanvas, useFeature, useLabeled, useSelect } from '../../ProjectContext';
import { highlightImageData, opacityImageData } from '../canvasUtils';

export const LabeledCanvas = ({ className }) => {
  const canvas = useCanvas();
  const sx = useSelector(canvas, (state) => state.context.sx);
  const sy = useSelector(canvas, (state) => state.context.sy);
  const zoom = useSelector(canvas, (state) => state.context.zoom);
  const scale = useSelector(canvas, (state) => state.context.scale);
  const sw = useSelector(canvas, (state) => state.context.width);
  const sh = useSelector(canvas, (state) => state.context.height);

  const width = sw * scale * window.devicePixelRatio;
  const height = sh * scale * window.devicePixelRatio;

  const labeled = useLabeled();
  const featureIndex = useSelector(labeled, (state) => state.context.feature);
  const highlight = useSelector(labeled, (state) => state.context.highlight);
  const opacity = useSelector(labeled, (state) => state.context.opacity);

  const feature = useFeature(featureIndex);
  const labeledImage = useSelector(feature, (state) => state.context.labeledImage);
  let labeledArray = useSelector(feature, (state) => state.context.labeledArray);
  if (!labeledArray) {
    labeledArray = Array(sh).fill(Array(sw).fill(0));
  }

  const select = useSelect();
  const foreground = useSelector(select, (state) => state.context.foreground);
  const background = useSelector(select, (state) => state.context.background);

  const canvasRef = useRef();
  const ctx = useRef();
  const hiddenCanvasRef = useRef();
  const hiddenCtx = useRef();

  useEffect(() => {
    ctx.current = canvasRef.current.getContext('2d');
    ctx.current.imageSmoothingEnabled = false;
  }, [width, height]);

  useEffect(() => {
    hiddenCtx.current = hiddenCanvasRef.current.getContext('2d');
  }, [sw, sh]);

  useEffect(() => {
    hiddenCtx.current.drawImage(labeledImage, 0, 0);
    let data = hiddenCtx.current.getImageData(0, 0, sw, sh);
    if (highlight && foreground !== 0) {
      const red = [255, 0, 0, 255];
      highlightImageData(data, labeledArray, foreground, red);
    }
    opacityImageData(data, opacity);
    hiddenCtx.current.putImageData(data, 0, 0);
  }, [labeledImage, labeledArray, foreground, highlight, opacity, sh, sw]);

  useEffect(() => {
    ctx.current.save();
    ctx.current.clearRect(0, 0, width, height);
    ctx.current.drawImage(
      hiddenCanvasRef.current,
      sx,
      sy,
      sw / zoom,
      sh / zoom,
      0,
      0,
      width,
      height
    );
    ctx.current.restore();
  }, [
    labeledImage,
    labeledArray,
    foreground,
    highlight,
    opacity,
    sw,
    sh,
    sx,
    sy,
    zoom,
    width,
    height,
  ]);

  return (
    <>
      {/* hidden processing canvas */}
      <canvas id='labeled-processing' hidden={true} ref={hiddenCanvasRef} width={sw} height={sh} />
      <canvas
        id='labeled-canvas'
        ref={canvasRef}
        width={width}
        height={height}
        className={className}
      />
    </>
  );
};

export default LabeledCanvas;
