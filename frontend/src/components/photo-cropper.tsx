import Cropper from "cropperjs";
import { ArrowLeft, ImagePlus } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface PhotoCropperProps { onBack: () => void }

export function PhotoCropper({ onBack }: PhotoCropperProps) {
  const imageRef = useRef<HTMLImageElement>(null);
  const cropperRef = useRef<Cropper | null>(null);
  const objectUrlRef = useRef<string | null>(null);
  const [source, setSource] = useState<string | null>(null);
  const [cropSummary, setCropSummary] = useState<string | null>(null);

  useEffect(() => {
    if (!source || !imageRef.current) return;
    cropperRef.current = new Cropper(imageRef.current, {
      aspectRatio: 16 / 9,
      viewMode: 1,
      autoCropArea: 1,
      background: false,
      responsive: true,
    });
    return () => { cropperRef.current?.destroy(); cropperRef.current = null; };
  }, [source]);

  useEffect(() => () => {
    if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current);
  }, []);

  const chooseFile = (file?: File) => {
    if (!file) return;
    if (!file.type.startsWith("image/")) { setCropSummary("Выберите файл изображения"); return; }
    if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current);
    objectUrlRef.current = URL.createObjectURL(file);
    setSource(objectUrlRef.current);
    setCropSummary(null);
  };

  const confirmCrop = () => {
    const cropper = cropperRef.current;
    if (!cropper) return;
    const image = cropper.getImageData();
    const crop = cropper.getData(true);
    const normalized = {
      x: crop.x / image.naturalWidth,
      y: crop.y / image.naturalHeight,
      width: crop.width / image.naturalWidth,
      height: crop.height / image.naturalHeight,
    };
    setCropSummary(`Область 16:9 подготовлена: ${Math.round(normalized.width * 100)}% ширины фотографии. Сервер проверит её повторно.`);
  };

  return (
    <main className="photo-page">
      <Button variant="ghost" onClick={onBack}><ArrowLeft aria-hidden="true" /> Назад</Button>
      <Card className="photo-card">
        <CardHeader><CardTitle>Фото события</CardTitle><p>Выберите одну фотографию и кадрируйте её в формате 16:9.</p></CardHeader>
        <CardContent className="photo-content">
          <label className="file-picker">
            <ImagePlus aria-hidden="true" />
            <span>Выбрать фотографию</span>
            <input type="file" accept="image/jpeg,image/png,image/webp" onChange={(event) => chooseFile(event.target.files?.[0])} />
          </label>
          {source && <div className="crop-stage"><img ref={imageRef} src={source} alt="Фотография для обрезки" /></div>}
          {source && <Button onClick={confirmCrop}>Применить обрезку</Button>}
          {cropSummary && <p className="success-message" role="status">{cropSummary}</p>}
        </CardContent>
      </Card>
    </main>
  );
}
