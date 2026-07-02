import { cn } from '@/lib/utils';
import logoMark from '../assets/LOGO.svg';

export type BrandLogoProps = {
  /** Hide the "Modelbest / StaffDeck" wordmark and only render the logo mark. */
  markOnly?: boolean;
  /** Size of the square logo mark in pixels. */
  markSize?: number;
  className?: string;
  /** Extra classes applied to the wordmark wrapper (e.g. to hide it responsively). */
  wordmarkClassName?: string;
};

/** Brand logo lockup (logo mark + "Modelbest" / "StaffDeck" wordmark). Figma node 38:344. */
export default function BrandLogo({
  markOnly = false,
  markSize = 28,
  className,
  wordmarkClassName,
}: BrandLogoProps) {
  return (
    <span className={cn('flex gap-[8px] overflow-hidden p-[4px]', className)}>
      <img
        src={logoMark}
        alt="StaffDeck"
        className="shrink-0"
        style={{ width: markSize, height: markSize }}
      />
      {!markOnly && (
        <span className={cn('flex flex-col items-start gap-[2px] leading-none', wordmarkClassName)}>
          <span className="text-[12px] font-semibold leading-none text-[#0f136c] dark:text-primary">
            Modelbest
          </span>
          <strong className="text-[17px] font-semibold leading-none text-sidebar-accent-foreground">
            StaffDeck
          </strong>
        </span>
      )}
    </span>
  );
}
