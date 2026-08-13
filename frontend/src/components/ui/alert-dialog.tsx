import * as Dialog from "@radix-ui/react-dialog";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";

export function AlertDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel = "Удалить",
  busyLabel = "Сохраняем…",
  busy = false,
  onConfirm,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: ReactNode;
  description: ReactNode;
  confirmLabel?: string;
  busyLabel?: string;
  busy?: boolean;
  onConfirm: () => void;
}) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="alert-dialog-overlay" />
        <Dialog.Content className="alert-dialog-content" onEscapeKeyDown={(event) => { if (busy) event.preventDefault(); }}>
          <Dialog.Title>{title}</Dialog.Title>
          <Dialog.Description>{description}</Dialog.Description>
          <div className="alert-dialog-actions">
            <Dialog.Close asChild><Button type="button" variant="outline" disabled={busy}>Отмена</Button></Dialog.Close>
            <Button type="button" variant="destructive" disabled={busy} onClick={onConfirm}>{busy ? busyLabel : confirmLabel}</Button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
