import { cn } from "@/lib/utils";

import { TextBlink } from "@/components/ui/text-blink";

type LoadingScreenProps = {
  text?: string;
  description?: string;
  className?: string;
};

function LoadingScreen({ text = "Загрузка…", description, className }: LoadingScreenProps) {
  return (
    <main className={cn("loading-screen", className)} role="status" aria-live="polite">
      <TextBlink className="loading-screen-text">{text}</TextBlink>
      {description && <p className="loading-screen-description">{description}</p>}
    </main>
  );
}

export { LoadingScreen };

export default LoadingScreen;