import * as React from 'react';
import { cn } from '../../lib/utils';

const variants = {
  default: 'bg-zinc-800 text-zinc-200 hover:bg-zinc-700',
  primary: 'bg-emerald-600 text-white hover:bg-emerald-500',
  danger: 'bg-red-600 text-white hover:bg-red-500',
  ghost: 'bg-transparent text-zinc-400 hover:bg-zinc-800 hover:text-white',
  outline: 'border border-zinc-700 text-zinc-300 hover:bg-zinc-800',
};

const sizes = {
  sm: 'h-8 px-3 text-xs',
  md: 'h-10 px-4 text-sm',
  lg: 'h-12 px-6 text-base',
};

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: keyof typeof variants;
  size?: keyof typeof sizes;
}

export function Button({
  className,
  variant = 'default',
  size = 'md',
  ...props
}: ButtonProps) {
  return (
    <button
      className={cn(
        'inline-flex items-center justify-center gap-2 rounded-md font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed',
        variants[variant],
        sizes[size],
        className
      )}
      {...props}
    />
  );
}
