import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const badgeVariants = cva(
  'inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide transition-colors',
  {
    variants: {
      variant: {
        default:  'border-transparent bg-primary/20 text-primary',
        critical: 'border-red-500/30 bg-red-500/15 text-red-400',
        high:     'border-orange-500/30 bg-orange-500/15 text-orange-400',
        medium:   'border-yellow-500/30 bg-yellow-500/15 text-yellow-400',
        low:      'border-green-500/30 bg-green-500/15 text-green-400',
        outline:  'border-border text-muted-foreground',
        blue:     'border-blue-500/30 bg-blue-500/15 text-blue-400',
        purple:   'border-purple-500/30 bg-purple-500/15 text-purple-400',
      },
    },
    defaultVariants: { variant: 'default' },
  },
)

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />
}

export { Badge, badgeVariants }
