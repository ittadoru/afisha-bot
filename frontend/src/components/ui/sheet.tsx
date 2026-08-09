import * as Dialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import type { ComponentProps } from "react";

import { cn } from "@/lib/utils";

export const Sheet = Dialog.Root;
export const SheetTrigger = Dialog.Trigger;
export const SheetClose = Dialog.Close;

export function SheetContent({ className, children, ...props }: ComponentProps<typeof Dialog.Content>) {
  return (
    <Dialog.Portal>
      <Dialog.Overlay className="sheet-overlay" />
      <Dialog.Content className={cn("sheet-content", className)} {...props}>
        <span className="sheet-grabber" aria-hidden="true" />
        {children}
        <Dialog.Close className="sheet-close" aria-label="Закрыть">
          <X aria-hidden="true" />
        </Dialog.Close>
      </Dialog.Content>
    </Dialog.Portal>
  );
}

export function SheetTitle({ className, ...props }: ComponentProps<typeof Dialog.Title>) {
  return <Dialog.Title className={cn("sheet-title", className)} {...props} />;
}

export function SheetDescription({ className, ...props }: ComponentProps<typeof Dialog.Description>) {
  return <Dialog.Description className={cn("sheet-description", className)} {...props} />;
}
