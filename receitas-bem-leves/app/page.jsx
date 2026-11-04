'use client';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useState } from 'react';
import { Moldura } from '../componentes/Moldura';
import { ListaReceitas } from '../componentes/Receita';
import { useApp } from '../componentes/Provedor';

const DESTAQUES = [
  ['cafe_sem_pao', 'Café da manhã sem pão'],
  ['substitutos_do_pao', 'Substitutos do pão'],
  ['doces_e_bolos', 'Doces e bolos'],
  ['rapidas_15min', 'Receitas rápidas até 15 min'],
];

function Inicio() {
  const { pacote, dados, extras } = useApp();
  const router = useRouter();
  const [busca, setBusca] = useState('');
  if (!pacote) return null;
  const vistas = dados.vistas.map((id) => pacote.porId[id]).filter(Boolean).slice(0, 4);
  return (
    <>
      <form className="busca" role="search" onSubmit={(e) => { e.preventDefault(); router.push(`/receitas/?busca=${encodeURIComponent(busca)}`); }}>
        <input id="busca-inicio" type="search" placeholder="Buscar receita" aria-label="Buscar receita ou ingrediente" value={busca} onChange={(e) => setBusca(e.target.value)} autoComplete="off" />
        <button className="btn btn-principal" type="submit">Buscar</button>
      </form>
      <section className="destaques" aria-label="Destaques">
        {DESTAQUES.map(([id, nome]) => (
          <Link key={id} className="destaque" href={`/receitas/?destaque=${id}`}>
            <strong>{nome}</strong>
            <span>{pacote.receitas.filter((r) => r.destaques.includes(id)).length} receitas</span>
          </Link>
        ))}
      </section>
      <section className="bloco">
        <div className="secao-titulo"><h2>Vistas por último</h2></div>
        {vistas.length
          ? <ListaReceitas receitas={vistas} />
          : <div className="vazio">As receitas que você abrir vão aparecer aqui.<Link className="btn btn-principal" href="/receitas/">Ver todas as receitas</Link></div>}
      </section>
      <section className="bloco">
        <div className="secao-titulo"><h2>Seus bônus</h2><Link href="/bonus/">Ver todos</Link></div>
        <div className="cartoes-bonus">
          {extras.map((x) => (
            <Link key={x.slug} className="cartao-bonus" href={`/extras/${x.slug}/`}><strong>{x.titulo}</strong><span>{x.resumo}</span></Link>
          ))}
          {pacote.bonus.slice(0, 2).map((b) => (
            <Link key={b.slug} className="cartao-bonus" href={`/bonus/${b.slug}/`}><strong>{b.titulo}</strong><span>{b.resumo}</span></Link>
          ))}
        </div>
      </section>
    </>
  );
}

export default function Pagina() {
  return <Moldura titulo="Receitas Bem Leves" ativa="inicio"><Inicio /></Moldura>;
}
