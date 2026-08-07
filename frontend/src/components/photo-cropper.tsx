import Cropper from "cropperjs";
import { Check, ImagePlus, Trash2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { appConfig } from "@/config";
import { cropFractions } from "@/lib/photo-crop";
import { Button } from "@/components/ui/button";

const MAX_FILE_BYTES = 12 * 1024 * 1024;
const ALLOWED_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);

const PHOTO_ERROR_MESSAGES: Record<string, string> = {
  unsupported_image: "Подойдут только JPEG, PNG или WebP.",
  image_too_large: "Фотография должна быть не больше 12 МБ.",
  empty_image: "Файл пуст. Выберите другое фото.",
  file_too_large: "Фотография должна быть не больше 12 МБ.",
  too_many_pixels: "Слишком высокое разрешение (более 40 мегапикселей).",
  invalid_dimensions: "Файл повреждён или не является изображением.",
  image_decode_or_encode_failed: "Файл не удалось обработать. Выберите другой JPEG, PNG или WebP.",
  crop_out_of_bounds: "Не удалось кадрировать. Повторите выделение кадра.",
  crop_is_empty: "Выделенный кадр пуст. Повторите кадрирование.",
  crop_must_be_4_3: "Выделите кадр в пропорции 4:3.",
  event_photo_not_found: "Фотография недоступна. Загрузите её ещё раз.",
};

async function photoErrorMessage(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json();
    const detail = typeof body === "object" && body !== null && "detail" in body
      ? (body as { detail: unknown }).detail
      : null;
    if (typeof detail === "string") return PHOTO_ERROR_MESSAGES[detail] ?? detail;
  } catch {
    // body is not JSON; fall back to generic message
  }
  return "Не удалось обработать фотографию. Выберите другую или попробуйте ещё раз.";
}

export interface EventPhotoUpload {
  upload_id: string;
  preview_url: string;
  expires_at: string;
  width: number;
  height: number;
}

interface EventPhotoUploaderProps {
  csrfToken: string;
  value: EventPhotoUpload | null;
  onChange: (photo: EventPhotoUpload | null) => void;
}

export function EventPhotoUploader({ csrfToken, value, onChange }: EventPhotoUploaderProps) {
  const imageRef = useRef<HTMLImageElement>(null);
  const cropperRef = useRef<Cropper | null>(null);
  const objectUrlRef = useRef<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [source, setSource] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!source || !imageRef.current) return;
    cropperRef.current = new Cropper(imageRef.current, {
      aspectRatio: 4 / 3,
      viewMode: 1,
      autoCropArea: 1,
      background: false,
      responsive: true,
    });
    return () => {
      cropperRef.current?.destroy();
      cropperRef.current = null;
    };
  }, [source]);

  useEffect(() => () => {
    if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current);
  }, []);

  const chooseFile = (next?: File) => {
    if (!next) return;
    if (!ALLOWED_TYPES.has(next.type)) {
      setError("Подойдут только JPEG, PNG или WebP.");
      return;
    }
    if (next.size > MAX_FILE_BYTES) {
      setError("Фотография должна быть не больше 12 МБ.");
      return;
    }
    if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current);
    objectUrlRef.current = URL.createObjectURL(next);
    setFile(next);
    setSource(objectUrlRef.current);
    setError("");
  };

  const upload = async () => {
    const cropper = cropperRef.current;
    if (!cropper || !file) return;
    const box = cropper.getData();
    const image = cropper.getImageData();
    const normalized = cropFractions(box, image);
    if (
      !Number.isFinite(normalized.x)
      || !Number.isFinite(normalized.y)
      || normalized.width <= 0
      || normalized.height <= 0
    ) {
      setError("Выделенный кадр пуст. Повторите кадрирование.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const response = await fetch(`${appConfig.apiBaseUrl}/media/event-photo`, {
        method: "PUT",
        credentials: "include",
        headers: {
          "Content-Type": file.type,
          "X-Afisha-CSRF": csrfToken,
          "X-Afisha-Crop-X": String(normalized.x),
          "X-Afisha-Crop-Y": String(normalized.y),
          "X-Afisha-Crop-Width": String(normalized.width),
          "X-Afisha-Crop-Height": String(normalized.height),
        },
        body: file,
      });
      if (!response.ok) throw new Error(await photoErrorMessage(response));
      onChange(await response.json() as EventPhotoUpload);
      setSource(null);
      setFile(null);
    } catch (error) {
      setError(error instanceof Error && error.message
        ? error.message
        : "Не удалось обработать фотографию. Выберите другую или попробуйте ещё раз.");
    } finally {
      setBusy(false);
    }
  };

  const remove = async () => {
    if (!value) return;
    setBusy(true);
    const response = await fetch(`${appConfig.apiBaseUrl}/media/event-photos/${value.upload_id}`, {
      method: "DELETE",
      credentials: "include",
      headers: { "X-Afisha-CSRF": csrfToken },
    });
    setBusy(false);
    if (response.ok) onChange(null);
    else setError("Не удалось удалить фотографию.");
  };

  if (value) return (
    <div className="event-photo-ready">
      <img src={value.preview_url} alt="Безопасная фотография события" />
      <p><Check aria-hidden="true" /> Фотография загружена и очищена от скрытых данных.</p>
      <div className="event-photo-actions">
        <label className="file-picker compact-picker">
          <ImagePlus aria-hidden="true" /><span>Заменить</span>
          <input type="file" accept="image/jpeg,image/png,image/webp" onChange={(event) => chooseFile(event.target.files?.[0])} />
        </label>
        <Button variant="outline" disabled={busy} onClick={() => void remove()}><Trash2 /> Удалить</Button>
      </div>
      {source && <CropStage imageRef={imageRef} source={source} busy={busy} onUpload={() => void upload()} />}
      {error && <p className="form-error" role="alert">{error}</p>}
    </div>
  );

  return (
    <div className="event-photo-uploader">
      <label className="file-picker">
        <ImagePlus aria-hidden="true" />
        <span>Выбрать фотографию</span>
        <input type="file" accept="image/jpeg,image/png,image/webp" onChange={(event) => chooseFile(event.target.files?.[0])} />
      </label>
      <small>JPEG, PNG или WebP, не больше 12 МБ. Итоговый кадр — 4:3.</small>
      {source && <CropStage imageRef={imageRef} source={source} busy={busy} onUpload={() => void upload()} />}
      {error && <p className="form-error" role="alert">{error}</p>}
    </div>
  );
}

function CropStage({ imageRef, source, busy, onUpload }: { imageRef: React.RefObject<HTMLImageElement | null>; source: string; busy: boolean; onUpload: () => void }) {
  return <div className="photo-crop-editor"><div className="crop-stage"><img ref={imageRef} src={source} alt="Фотография для обрезки" /></div><Button disabled={busy} onClick={onUpload}>{busy ? "Обрабатываем…" : "Обрезать и загрузить"}</Button></div>;
}
