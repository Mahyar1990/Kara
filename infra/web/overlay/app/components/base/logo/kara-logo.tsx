import type { DifyLogoProps } from './dify-logo'
import { cn } from '@langgenius/dify-ui/cn'
import { basePath } from '@/utils/var'

const sizes = { small: 'h-4 w-9', medium: 'h-5.5 w-12', large: 'h-7 w-16' }

export function KaraLogo({ alt, className, size = 'medium', ...props }: DifyLogoProps) {
  return <img {...props} src={`${basePath}/kara/wordmark.svg`} width={48} height={22} alt={alt} className={cn('block object-contain [html[data-theme=dark]_&]:brightness-0 [html[data-theme=dark]_&]:invert', sizes[size || 'medium'], className)} />
}
