import { ImageOff } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { cn } from "@/lib/utils";

const AVATAR_ATTEMPT_TIMEOUT_MS = 4_000;

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
  const wrapperRef = useRef<HTMLSpanElement>(null);
  const [eligible, setEligible] = useState(
    () => !lazy || typeof IntersectionObserver === "undefined",
  );

  useEffect(() => {
    if (!lazy) {
      setEligible(true);
      return;
    }
    if (eligible || typeof IntersectionObserver === "undefined") return;
    const element = wrapperRef.current;
    if (!element) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setEligible(true);
          observer.disconnect();
        }
      },
      { rootMargin: "200px" },
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, [eligible, lazy]);

  return (
    <span
      ref={wrapperRef}
      className={cn("user-avatar", className)}
      style={{ width: size, height: size }}
      aria-hidden="true"
    >
      {!sources.length ? (
        <span className="user-avatar-initial">{name[0] ?? "?"}</span>
      ) : eligible ? (
        <AvatarLoader key={sourceKey} sources={sources} size={size} />
      ) : (
        <span className="user-avatar-placeholder" />
      )}
    </span>
  );
}

function AvatarLoader({ sources, size }: { sources: string[]; size: number }) {
  const [step, setStep] = useState(0);
  const [loaded, setLoaded] = useState(false);
  const sourceIndex = Math.floor(step / 2);
  const retry = step % 2 === 1;
  const source = sources[sourceIndex] ?? null;
  const requestUrl = source ? avatarAttemptUrl(source, retry) : null;

  useEffect(() => {
    if (!requestUrl || loaded) return;
    const timeout = window.setTimeout(
      () => setStep((current) => current + 1),
      AVATAR_ATTEMPT_TIMEOUT_MS,
    );
    return () => window.clearTimeout(timeout);
  }, [loaded, requestUrl]);

  if (!requestUrl) return <ImageOff className="user-avatar-unavailable" />;
  return (
    <>
      <span className="user-avatar-placeholder" />
      <img
        key={requestUrl}
        className={loaded ? "is-loaded" : ""}
        src={requestUrl}
        width={size}
        height={size}
        loading="eager"
        decoding="async"
        alt=""
        onLoad={() => setLoaded(true)}
        onError={() => {
          setLoaded(false);
          setStep((current) => current + 1);
        }}
      />
    </>
  );
}

function avatarAttemptUrl(source: string, retry: boolean): string {
  if (!retry) return source;
  const separator = source.includes("?") ? "&" : "?";
  return `${source}${separator}avatar_retry=1`;
}
