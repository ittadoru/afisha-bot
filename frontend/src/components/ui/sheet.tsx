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
      <Dialog.Overlay className="sheet-overlay" data-ui="sheet-overlay" data-material="scrim" />
      <Dialog.Content
        {...props}
        data-ui="sheet-content"
        data-material="overlay"
        className={cn("sheet-content", className)}
      >
        <span className="sheet-grabber" data-ui="sheet-grabber" aria-hidden="true" />
        {children}
        <Dialog.Close className="sheet-close" data-ui="sheet-close" data-material="control" aria-label="Закрыть">
          <X aria-hidden="true" />
        </Dialog.Close>
      </Dialog.Content>
    </Dialog.Portal>
  );
}

export function SheetTitle({ className, ...props }: ComponentProps<typeof Dialog.Title>) {
  return <Dialog.Title {...props} data-ui="sheet-title" className={cn("sheet-title", className)} />;
}

export function SheetDescription({ className, ...props }: ComponentProps<typeof Dialog.Description>) {
  return <Dialog.Description {...props} data-ui="sheet-description" className={cn("sheet-description", className)} />;
}
