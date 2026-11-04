'use client';
// Peças de receita reaproveitadas nas telas: imagem com etiquetas, cartão e lista paginada.
import Link from 'next/link';
import { useState } from 'react';
import { Ilustracao } from '../ilustracoes/index.mjs';
import { numero } from '../lib/texto';
import { useApp } from './Provedor';

export function Etiquetas({ receita }) {
  return (
    <div className="etiquetas">
      <span className="etiqueta verde">0 açúcar adicionado</span>
      {receita.low_carb && <span className="etiqueta vinho">Low carb</span>}
    </div>
  );
}

// Foto da receita na lista e na página; a ilustração fica de reserva quando a foto não existe ou não carrega
// (por exemplo, sem internet, numa receita que ainda não foi aberta).
export function ImagemReceita({ receita, grande = false }) {
  const { pacote } = useApp();
  const [fotoFalhou, setFotoFalhou] = useState(false);
  const usarFoto = receita.foto && !fotoFalhou;
  return (
    <>
      <div className={`imagem${grande ? ' imagem-grande' : ''}`}>
        {usarFoto
          // eslint-disable-next-line @next/next/no-img-element
          ? <img src={`/${receita.foto}`} alt={receita.nome} loading="lazy" decoding="async" onError={() => setFotoFalhou(true)} />
          : <Ilustracao receita={receita} ingredientes={pacote.ingredientes} />}
        <Etiquetas receita={receita} />
      </div>
      {grande && usarFoto && <p className="legenda-foto">Imagem ilustrativa</p>}
    </>
  );
}

export function CartaoReceita({ receita }) {
  return (
    <Link className="cartao" href={`/receita/?id=${receita.id}`}>
      <ImagemReceita receita={receita} />
      <div className="corpo">
        <h2 className="titulo-cartao">{receita.nome}</h2>
        <p className="meta">{receita.tempo.total_min} min · {receita.nutricao.kcal} kcal · {numero(receita.nutricao.carboidratos_g)} g de carboidratos por porção</p>
      </div>
    </Link>
  );
}

// Mostra 24 por vez para não pesar no celular.
export function ListaReceitas({ receitas, porPagina = 24 }) {
  const [quantas, setQuantas] = useState(porPagina);
  return (
    <>
      <div className="lista-receitas">{receitas.slice(0, quantas).map((r) => <CartaoReceita key={r.id} receita={r} />)}</div>
      {quantas < receitas.length && (
        <button className="btn btn-secundario btn-largo" onClick={() => setQuantas((q) => q + porPagina)}>
          Ver mais receitas ({receitas.length - quantas})
        </button>
      )}
    </>
  );
}
