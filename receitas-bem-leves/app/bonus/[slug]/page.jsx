import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { PaginaBonus } from './PaginaBonus';

// As páginas são geradas no build só com o endereço e o título; o conteúdo vem do pacote protegido.
const pasta = join(process.cwd(), 'conteudo', 'bonus');
const lista = () => readdirSync(pasta).filter((f) => f.endsWith('.json')).map((f) => JSON.parse(readFileSync(join(pasta, f), 'utf8')));

export function generateStaticParams() {
  return lista().map((b) => ({ slug: b.slug }));
}

export default async function Pagina({ params }) {
  const { slug } = await params;
  const titulo = lista().find((b) => b.slug === slug)?.titulo ?? 'Bônus';
  return <PaginaBonus slug={slug} titulo={titulo} />;
}
