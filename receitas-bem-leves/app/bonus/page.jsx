'use client';
import Link from 'next/link';
import { Moldura } from '../../componentes/Moldura';
import { useApp } from '../../componentes/Provedor';

function ListaBonus() {
  const { pacote, extras } = useApp();
  if (!pacote) return null;
  return (
    <>
      {extras.length > 0 && (
        <>
          <h2 style={{ fontSize: 26, color: 'var(--vinho)' }}>Seus produtos extras</h2>
          <div className="cartoes-bonus">
            {extras.map((x) => (
              <Link key={x.slug} className="cartao-bonus" href={`/extras/${x.slug}/`}><strong>{x.titulo}</strong><span>{x.resumo}</span></Link>
            ))}
          </div>
        </>
      )}
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
