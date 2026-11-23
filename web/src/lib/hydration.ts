"use client";
import { useSyncExternalStore } from "react";
const subscribe = () => () => {};
const hydrated = () => true;
const server = () => false;
// Forms must not fall back to native submission before handlers are attached.
export function useHydrated() {
  return useSyncExternalStore(subscribe, hydrated, server);
}
