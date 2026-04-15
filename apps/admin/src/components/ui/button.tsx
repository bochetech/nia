"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "default" | "destructive" | "outline" | "ghost" | "secondary" | "link";
  size?: "default" | "sm" | "lg" | "icon";
  loading?: boolean;
}

const variantStyles = {
  default:
    "bg-primary text-primary-foreground shadow-apple-sm hover:brightness-110 active:brightness-95 active:scale-[0.98]",
  destructive:
    "bg-destructive text-destructive-foreground shadow-apple-sm hover:brightness-110 active:brightness-95 active:scale-[0.98]",
  outline:
    "border border-input bg-background shadow-apple-sm hover:bg-accent hover:text-accent-foreground active:scale-[0.98]",
  ghost:
    "hover:bg-accent/60 hover:text-accent-foreground active:bg-accent",
  secondary:
    "bg-secondary text-secondary-foreground shadow-apple-sm hover:bg-secondary/80 active:scale-[0.98]",
  link:
    "text-primary underline-offset-4 hover:underline",
};

const sizeStyles = {
  default: "h-9 px-4 py-2 text-sm",
  sm: "h-7 rounded-lg px-3 text-xs",
  lg: "h-11 rounded-xl px-8 text-base",
  icon: "h-9 w-9",
};

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "default", size = "default", loading, children, disabled, ...props }, ref) => (
    <button
      ref={ref}
      disabled={disabled || loading}
      className={cn(
        "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-lg font-medium",
        "transition-all duration-150 ease-out",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40 focus-visible:ring-offset-1",
        "disabled:pointer-events-none disabled:opacity-40",
        variantStyles[variant],
        sizeStyles[size],
        className
      )}
      {...props}
    >
      {loading && (
        <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
      )}
      {children}
    </button>
  )
);
Button.displayName = "Button";
