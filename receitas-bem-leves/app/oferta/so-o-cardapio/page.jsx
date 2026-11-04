'use client';
// Downsell (R$ 27): só o Cardápio de 12 Semanas, sem o Guia de Marmitas.
import { BotoesHotmart, PaginaOferta } from '../../../componentes/PaginaOferta';

export default function Downsell() {
  return (
    <PaginaOferta aviso="Sua compra continua aprovada. Antes de ir, uma versão menor da oferta.">
      <section className="bloco">
        <h1 className="titulo-oferta">E só o cardápio, sem as marmitas?</h1>
        <p>Muita gente não quer passar o domingo na cozinha, mas quer as 12 semanas de cardápio prontas. Por isso existe esta versão.</p>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img className="tela-unica" src="/funil/cardapio12.jpg" alt="Tela do Cardápio de 12 Semanas no app" width="375" height="760" />
        <ul className="lista-oferta">
          <li><b>12 semanas de cardápio:</b> café da manhã, lanche, almoço e jantar por 84 dias.</li>
          <li><b>Lista de compras de cada semana</b> com um toque, separada por seção do mercado.</li>
          <li>Entra no mesmo app, com o mesmo e-mail.</li>
        </ul>
        <p>O Guia de Marmitas não vem nesta versão.</p>
      </section>
      <section className="bloco caixa-preco">
        <p className="preco-oferta">R$ 27,00 <small>pagamento único</small></p>
        <p><b>Garantia de 7 dias</b> pela Hotmart.</p>
        <BotoesHotmart />
      </section>
    </PaginaOferta>
  );
}
