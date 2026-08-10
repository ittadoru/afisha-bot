import { cn } from "@/lib/utils";

import { TextBlink } from "@/components/ui/text-blink";

type LoadingScreenProps = {
  variant?: "screen" | "section" | "overlay";
  className?: string;
};

function LoadingScreen({ variant = "screen", className }: LoadingScreenProps) {
  return (
    <div className={cn("loading-screen", `loading-screen--${variant}`, className)} role="status" aria-live="polite" aria-busy="true">
      <TextBlink className="loading-screen-text">Ургъула…</TextBlink>
    </div>
  );
}

export { LoadingScreen };

export default LoadingScreen;
