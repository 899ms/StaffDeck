import type { ReactNode } from 'react';

import { cn } from '@/lib/utils';

export type UnderlineTabItem<T extends string = string> = {
  value: T;
  label: ReactNode;
  disabled?: boolean;
};

export type UnderlineTabsProps<T extends string = string> = {
  items: UnderlineTabItem<T>[];
  value: T;
  onChange: (value: T) => void;
  className?: string;
  /** Extra classes for each tab button (e.g. override the default fixed width). */
  tabClassName?: string;
  'aria-label'?: string;
};

/**
 * Global underline tab bar (SD1 design: node 38:6404).
 * The active tab shows a short centered rounded indicator bar under the label.
 */
export function UnderlineTabs<T extends string = string>({
  items,
  value,
  onChange,
  className,
  tabClassName,
  'aria-label': ariaLabel,
}: UnderlineTabsProps<T>) {
  return (
    <div role="tablist" aria-label={ariaLabel} className={cn('flex items-start', className)}>
      {items.map((item) => {
        const active = item.value === value;
        return (
          <button
            key={item.value}
            type="button"
            role="tab"
            aria-selected={active}
            disabled={item.disabled}
            onClick={() => onChange(item.value)}
            className={cn(
              'relative flex w-[120px] items-start justify-center px-[16px] py-[6px] text-[14px] capitalize transition-colors outline-none',
              active
                ? 'font-medium text-[#18181A] dark:text-white'
                : 'font-normal text-[#858B9C] hover:text-[#18181A] dark:hover:text-white',
              'disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:text-[#858B9C]',
              tabClassName,
            )}
          >
            {item.label}
            {active && (
              <span
                aria-hidden="true"
                className="absolute top-[33px] left-1/2 h-[3px] w-[10px] -translate-x-1/2 rounded-[4px] bg-[#18181A] dark:bg-white"
              />
            )}
          </button>
        );
      })}
    </div>
  );
}
