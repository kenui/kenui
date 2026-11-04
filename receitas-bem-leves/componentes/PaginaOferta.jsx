'use client';
// Páginas do funil depois da compra (upsell, downsell e obrigado). Não pedem login.
// Os botões de "sim" e "não" do upsell de 1 clique vêm da própria Hotmart: o script abaixo
// monta os botões no lugar de <div id="hotmart-sales-funnel">. Configure o funil na Hotmart
// (Ferramentas > Funil de Vendas) apontando para estas páginas.
import Script from 'next/script';
import { Rodape } from './Moldura';

export function BotoesHotmart() {
  return (
    <>
      <div id="hotmart-sales-funnel" className="botoes-hotmart" />
      <Script
        src="https://checkout.hotmart.com/lib/hotmart-checkout-elements.js"
        strategy="afterInteractive"
        onLoad={() => { try { window.checkoutElements.init('salesFunnel').mount('#hotmart-sales-funnel'); } catch {} }}
      />
    </>
  );
}

export function PaginaOferta({ aviso, children }) {
  return (
    <div className="oferta">
      {aviso && <div className="faixa-aviso">{aviso}</div>}
      <main className="conteudo conteudo-oferta">
        {children}
        <Rodape />
      </main>
    </div>
  );
}
