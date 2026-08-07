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

export interface ImageData {
  naturalWidth: number;
  naturalHeight: number;
}

const clamp = (value: number, min: number, max: number) => Math.min(Math.max(value, min), max);

export function cropFractions(box: CropBoxData, image: ImageData): NormalizedCrop {
  const x = clamp(box.x / image.naturalWidth, 0, 1);
  const y = clamp(box.y / image.naturalHeight, 0, 1);
  const width = clamp(box.width / image.naturalWidth, 0, 1 - x);
  const height = clamp(box.height / image.naturalHeight, 0, 1 - y);
  return { x, y, width, height };
}