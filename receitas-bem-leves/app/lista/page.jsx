'use client';
import Link from 'next/link';
import { Moldura } from '../../componentes/Moldura';
import { useApp } from '../../componentes/Provedor';
import { montarLista } from '../../lib/lista';

function Lista() {
  const { pacote, dados, atualizar } = useApp();
  if (!pacote) return null;
  const { receitas, marcados } = dados.lista;
  if (!receitas.length) {
    return (
      <div className="vazio">
        Sua lista está vazia. Na página de uma receita, toque em “+ Lista de compras”, ou gere a lista de uma semana no Plano.
        <Link className="btn btn-principal" href="/plano/">Ir para o Plano</Link>
      </div>
    );
  }
  const grupos = montarLista(pacote, receitas);
  const marcar = (id, sim) => atualizar('lista', (l) => ({ ...l, marcados: sim ? [...l.marcados, id] : l.marcados.filter((x) => x !== id) }));
  return (
    <>
      <section className="bloco">
        <h3>Receitas na lista ({receitas.length})</h3>
        <p className="nota">A lista soma os ingredientes de uma receita de cada prato.</p>
        <div className="na-lista">
          {receitas.map((id) => (
            <div key={id}>
              <span>{pacote.porId[id]?.nome}</span>
              <button className="btn-texto nao-imprimir" onClick={() => atualizar('lista', (l) => ({ ...l, receitas: l.receitas.filter((x) => x !== id) }))}>Tirar</button>
            </div>
          ))}
        </div>
      </section>
      {grupos.map((g) => (
        <section key={g.secao} className="grupo-mercado">
          <h3>{g.secao}</h3>
          {g.itens.map((it) => {
            const marcado = marcados.includes(it.id);
            return (
              <div key={it.id} className={`item-compra${marcado ? ' marcado' : ''}`}>
                <input type="checkbox" id={`c-${it.id}`} checked={marcado} onChange={(e) => marcar(it.id, e.target.checked)} />
                <label htmlFor={`c-${it.id}`}>{it.texto}</label>
              </div>
            );
          })}
        </section>
      ))}
      <button className="btn btn-secundario btn-largo" onClick={() => window.print()}>Imprimir lista</button>
      <button className="btn btn-secundario btn-largo" onClick={() => atualizar('lista', { receitas: [], marcados: [] })}>Esvaziar a lista</button>
    </>
  );
}

export default function Pagina() {
  return <Moldura titulo="Lista de compras" ativa="perfil" voltar="/perfil/"><Lista /></Moldura>;
}
