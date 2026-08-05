import Cropper from "cropperjs";
import { useEffect, useRef } from "react";

import { Button } from "@/components/ui/button";

export function AvatarCropper({ file, onCancel, onConfirm }: { file: File; onCancel: () => void; onConfirm: (blob: Blob) => void }) {
  const imageRef = useRef<HTMLImageElement>(null);
  const cropperRef = useRef<Cropper | null>(null);
  const urlRef = useRef(URL.createObjectURL(file));
  useEffect(() => {
    if (!imageRef.current) return;
    cropperRef.current = new Cropper(imageRef.current, { aspectRatio: 1, viewMode: 1, autoCropArea: 1, background: false });
    return () => { cropperRef.current?.destroy(); URL.revokeObjectURL(urlRef.current); };
  }, []);
  const confirm = () => cropperRef.current?.getCroppedCanvas({ width: 512, height: 512 }).toBlob((blob) => { if (blob) onConfirm(blob); }, "image/webp", .9);
  return <div className="avatar-cropper"><h2>Обрежьте фотографию</h2><div className="crop-stage avatar-crop-stage"><img ref={imageRef} src={urlRef.current} alt="Обрезка аватара" /></div><div className="auth-actions"><Button onClick={confirm}>Сохранить фотографию</Button><Button variant="outline" onClick={onCancel}>Отмена</Button></div></div>;
}
