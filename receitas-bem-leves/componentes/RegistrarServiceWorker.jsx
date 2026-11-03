'use client';
// Registra o service worker (guarda o app no aparelho para funcionar sem internet).
import { useEffect } from 'react';

export function RegistrarServiceWorker() {
  useEffect(() => {
    if (process.env.NODE_ENV !== 'production' || !('serviceWorker' in navigator)) return;
    navigator.serviceWorker.register('/sw.js').catch(() => {});
  }, []);
  return null;
}
