import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import type { ButtonHTMLAttributes } from "react";

import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex min-h-11 touch-manipulation items-center justify-center gap-2 rounded-[14px] px-5 text-sm font-bold transition-[background-color,color,border-color,box-shadow,transform] duration-200 ease-out focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 active:scale-[.985] disabled:pointer-events-none disabled:opacity-45 disabled:shadow-none",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground shadow-[0_8px_24px_color-mix(in_srgb,var(--primary)_22%,transparent)] hover:bg-primary/92",
        secondary: "bg-secondary text-secondary-foreground hover:bg-secondary/80",
        outline: "border border-border bg-card text-foreground hover:border-primary/35 hover:bg-muted",
        ghost: "text-foreground hover:bg-muted",
        destructive: "bg-destructive text-destructive-foreground hover:bg-destructive/90",
      },
      size: { default: "h-12", icon: "size-11 p-0", sm: "h-11 px-4" },
    },
    defaultVariants: { variant: "default", size: "default" },
  },
);

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

export function Button({ className, variant, size, asChild, ...props }: ButtonProps) {
  const Component = asChild ? Slot : "button";
  return <Component className={cn(buttonVariants({ variant, size }), className)} {...props} />;
}
