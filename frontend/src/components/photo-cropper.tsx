import { Check, ImagePlus } from "lucide-react";
import { useState } from "react";

import { appConfig } from "@/config";

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
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const chooseFile = (next?: File) => {
    if (!next || busy) return;
    if (!ALLOWED_TYPES.has(next.type)) {
      setError("Подойдут только JPEG, PNG или WebP.");
      return;
    }
    if (next.size > MAX_FILE_BYTES) {
      setError("Фотография должна быть не больше 12 МБ.");
      return;
    }
    setError("");
    void upload(next);
  };

  const upload = async (file: File) => {
    setBusy(true);
    try {
      const response = await fetch(`${appConfig.apiBaseUrl}/media/event-photo`, {
        method: "PUT",
        credentials: "include",
        headers: {
          "Content-Type": file.type,
          "X-Afisha-CSRF": csrfToken,
        },
        body: file,
      });
      if (!response.ok) throw new Error(await photoErrorMessage(response));
      const previous = value;
      const uploaded = await response.json() as EventPhotoUpload;
      onChange(uploaded);
      if (previous && previous.upload_id !== uploaded.upload_id) {
        void fetch(`${appConfig.apiBaseUrl}/media/event-photos/${previous.upload_id}`, {
          method: "DELETE",
          credentials: "include",
          headers: { "X-Afisha-CSRF": csrfToken },
        }).catch(() => undefined);
      }
    } catch (uploadError) {
      setError(uploadError instanceof Error && uploadError.message
        ? uploadError.message
        : "Не удалось обработать фотографию. Выберите другую или попробуйте ещё раз.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className={value ? "event-photo-ready" : "event-photo-uploader"}>
      {value && <>
        <img src={value.preview_url} alt="Безопасная фотография события" />
        <p><Check aria-hidden="true" /> Фотография загружена и очищена от скрытых данных.</p>
      </>}
      <div className="event-photo-actions">
        <label className="file-picker">
          {busy ? <span>Обрабатываем…</span> : <><ImagePlus aria-hidden="true" /><span>{value ? "Заменить фотографию" : "Выбрать фотографию"}</span></>}
          <input type="file" accept="image/jpeg,image/png,image/webp" disabled={busy} onChange={(event) => chooseFile(event.target.files?.[0])} />
        </label>
      </div>
      <small>JPEG, PNG или WebP, не больше 12 МБ.</small>
      {error && <p className="form-error" role="alert">{error}</p>}
    </div>
  );
}
