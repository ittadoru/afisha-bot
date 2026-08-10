import { TextBlink } from "@/components/ui/text-blink";

export default function TextBlinkDemo() {
  return (
    <div className="flex min-h-64 w-full items-center justify-center bg-background">
      <TextBlink className="text-4xl text-muted-foreground">Ургъула…</TextBlink>
    </div>
  );
}
