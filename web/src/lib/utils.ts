import { clsx, type ClassValue } from "clsx";

/** Conditional class joiner (the only class utility the console uses). */
export function cn(...inputs: ClassValue[]): string {
  return clsx(...inputs);
}
