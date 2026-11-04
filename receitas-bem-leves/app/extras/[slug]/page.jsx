import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { PaginaExtra } from './PaginaExtra';

// Páginas dos produtos extras (caderno, cardápio de 12 semanas, marmitas). O build gera só o endereço e o título;
// o conteúdo vem do banco e só aparece para quem comprou.
const pasta = join(process.cwd(), 'conteudo', 'extras');
const lista = () => readdirSync(pasta).filter((f) => f.endsWith('.json')).map((f) => JSON.parse(readFileSync(join(pasta, f), 'utf8')));

export function generateStaticParams() {
  return lista().map((x) => ({ slug: x.slug }));
}

export default async function Pagina({ params }) {
  const { slug } = await params;
  const titulo = lista().find((x) => x.slug === slug)?.titulo ?? 'Conteúdo extra';
  return <PaginaExtra slug={slug} titulo={titulo} />;
}
