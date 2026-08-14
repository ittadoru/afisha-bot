import type { HTMLAttributes } from "react";

import { cn } from "@/lib/utils";

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      {...props}
      data-ui="card"
      data-material="content"
      className={cn("rounded-[16px] border border-border bg-card text-card-foreground shadow-sm", className)}
    />
  );
}

export function CardHeader({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div {...props} data-ui="card-header" className={cn("space-y-1.5 p-5", className)} />;
}

export function CardTitle({ className, ...props }: HTMLAttributes<HTMLHeadingElement>) {
  return <h3 {...props} data-ui="card-title" className={cn("text-lg font-bold", className)} />;
}

export function CardContent({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div {...props} data-ui="card-content" className={cn("p-5 pt-0", className)} />;
}
