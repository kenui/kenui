'use client';
import { Moldura } from '../../../componentes/Moldura';
import { useApp } from '../../../componentes/Provedor';
import { ConteudoBonus } from '../../../componentes/Bonus';

function Conteudo({ slug }) {
  const { pacote } = useApp();
  const bonus = pacote?.bonus.find((b) => b.slug === slug);
  return bonus ? <ConteudoBonus bonus={bonus} /> : null;
}

export function PaginaBonus({ slug, titulo }) {
  return <Moldura titulo={titulo} ativa="inicio" voltar="/bonus/"><Conteudo slug={slug} /></Moldura>;
}
