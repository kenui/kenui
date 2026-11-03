'use client';
import Link from 'next/link';
import { Moldura } from '../../componentes/Moldura';
import { useApp } from '../../componentes/Provedor';

function ListaBonus() {
  const { pacote } = useApp();
  if (!pacote) return null;
  return (
    <>
      <p>Materiais extras que vieram com a sua compra.</p>
      <div className="cartoes-bonus">
        {pacote.bonus.map((b) => (
          <Link key={b.slug} className="cartao-bonus" href={`/bonus/${b.slug}/`}><strong>{b.titulo}</strong><span>{b.resumo}</span></Link>
        ))}
      </div>
    </>
  );
}

export default function Pagina() {
  return <Moldura titulo="Bônus" ativa="inicio" voltar="/"><ListaBonus /></Moldura>;
}
