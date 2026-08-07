export interface NormalizedCrop {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface CropBoxData {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface ContainerData {
  width: number;
  height: number;
}

export interface CanvasData {
  left: number;
  top: number;
  width: number;
  height: number;
}

const clamp = (value: number, min: number, max: number) => Math.min(Math.max(value, min), max);

export function cropFractions(
  box: CropBoxData,
  container: ContainerData,
  canvas: CanvasData,
): NormalizedCrop {
  const left = (box.x / 100) * container.width;
  const top = (box.y / 100) * container.height;
  const width = (box.width / 100) * container.width;
  const height = (box.height / 100) * container.height;
  const x = clamp((left - canvas.left) / canvas.width, 0, 1);
  const y = clamp((top - canvas.top) / canvas.height, 0, 1);
  const widthFraction = clamp(width / canvas.width, 0, 1 - x);
  const heightFraction = clamp(height / canvas.height, 0, 1 - y);
  return { x, y, width: widthFraction, height: heightFraction };
}