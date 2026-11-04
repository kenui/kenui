'use client';
import Link from 'next/link';
import { Moldura } from '../../../componentes/Moldura';
import { useApp } from '../../../componentes/Provedor';
import { ConteudoBonus } from '../../../componentes/Bonus';

function Conteudo({ slug }) {
  const { pacote, extras } = useApp();
  if (!pacote) return null;
  const extra = extras.find((x) => x.slug === slug);
  if (!extra) {
    return (
      <div className="vazio">
        Este conteúdo não faz parte da sua compra. Se você comprou e ele não aparece, abra o app com internet ou fale com o suporte.
        <Link className="btn btn-principal" href="/bonus/">Ver meus bônus</Link>
      </div>
    );
  }
  return <ConteudoBonus bonus={extra} />;
}

export function PaginaExtra({ slug, titulo }) {
  return <Moldura titulo={titulo} ativa="inicio" voltar="/bonus/"><Conteudo slug={slug} /></Moldura>;
}
