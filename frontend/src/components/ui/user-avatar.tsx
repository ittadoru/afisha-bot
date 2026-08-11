import { ImageOff } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { cn } from "@/lib/utils";

interface UserAvatarProps {
  name: string;
  thumbnailUrl?: string | null;
  fallbackUrl?: string | null;
  className?: string;
  size?: number;
  lazy?: boolean;
}

export function UserAvatar({
  name,
  thumbnailUrl,
  fallbackUrl,
  className,
  size = 40,
  lazy = true,
}: UserAvatarProps) {
  const sources = useMemo(
    () =>
      [thumbnailUrl, fallbackUrl].filter(
        (value, index, all): value is string =>
          Boolean(value) && all.indexOf(value) === index,
      ),
    [fallbackUrl, thumbnailUrl],
  );
  const sourceKey = sources.join("|");
  const [sourceIndex, setSourceIndex] = useState(0);
  const [loadedSource, setLoadedSource] = useState<string | null>(null);

  useEffect(() => {
    setSourceIndex(0);
    setLoadedSource(null);
  }, [sourceKey]);

  const source = sources[sourceIndex] ?? null;
  return (
    <span
      className={cn("user-avatar", className)}
      style={{ width: size, height: size }}
      aria-hidden="true"
    >
      {!sources.length ? (
        <span className="user-avatar-initial">{name[0] ?? "?"}</span>
      ) : source ? (
        <>
          <span className="user-avatar-placeholder" />
          <img
            className={loadedSource === source ? "is-loaded" : ""}
            src={source}
            width={size}
            height={size}
            loading={lazy ? "lazy" : "eager"}
            decoding="async"
            alt=""
            onLoad={() => setLoadedSource(source)}
            onError={() => {
              setLoadedSource(null);
              setSourceIndex((index) => index + 1);
            }}
          />
        </>
      ) : (
        <ImageOff className="user-avatar-unavailable" />
      )}
    </span>
  );
}
