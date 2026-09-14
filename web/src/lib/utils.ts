import { clsx, type ClassValue } from "clsx";

/** The console's class-merging helper (clsx-tier utility, no extra deps). */
export function cn(...inputs: ClassValue[]): string {
  return clsx(inputs);
}
