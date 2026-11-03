import { DM_Serif_Display, Atkinson_Hyperlegible } from 'next/font/google';
import { Provedor } from '../componentes/Provedor';
import { RegistrarServiceWorker } from '../componentes/RegistrarServiceWorker';
import './globals.css';

// As fontes são baixadas na hora do build e servidas pelo próprio app (funcionam offline).
const titulo = DM_Serif_Display({ subsets: ['latin'], weight: '400', variable: '--fonte-titulo', display: 'swap' });
const corpo = Atkinson_Hyperlegible({ subsets: ['latin'], weight: ['400', '700'], variable: '--fonte-corpo', display: 'swap' });

export const metadata = {
  title: 'Receitas Bem Leves',
  description: 'Receitas sem açúcar adicionado: pão, bolo, doce e comida do dia a dia.',
  manifest: '/manifest.webmanifest',
  icons: { icon: '/icones/icone-192.png', apple: '/icones/apple-touch-icon.png' },
  appleWebApp: { capable: true, title: 'Bem Leves', statusBarStyle: 'default' },
};

export const viewport = {
  width: 'device-width',
  initialScale: 1,
  viewportFit: 'cover',
  themeColor: '#7B1E2C',
};

export default function Layout({ children }) {
  return (
    <html lang="pt-BR" className={`${titulo.variable} ${corpo.variable}`}>
      <body>
        <Provedor>{children}</Provedor>
        <RegistrarServiceWorker />
      </body>
    </html>
  );
}
