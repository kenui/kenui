Você é o Claude e vai terminar sozinho a configuração do funil do app "Receitas Bem Leves", gerar fotos realistas das receitas e criar vídeos de anúncio. Trabalhe em português do Brasil, com linguagem simples. Use o MEU NAVEGADOR (Claude in Chrome), onde já estou logado na Hotmart, no Supabase, no Higgsfield, no GitHub, no Meta e no Gmail. Só me chame quando for indispensável.

CONTEXTO
- Código: repositório GitHub kenui/kenui, branch ccr-ca9ce95d-5i51f9, pasta receitas-bem-leves/. Leia primeiro:
  - receitas-bem-leves/docs/funil/plano-do-funil.md (seções 5 e 6 = configuração da Hotmart e do Supabase);
  - receitas-bem-leves/README.md;
  - receitas-bem-leves/docs/relatorio-fase-3.md.
- O app está no ar em https://app.dividaclara.com.br (Next.js estático no Hostinger). Banco, login e webhook ficam no Supabase, projeto mfmtdnzkgqrtcjuacpcu. A função do webhook tem endereço https://mfmtdnzkgqrtcjuacpcu.supabase.co/functions/v1/smart-function (no painel ela se chama hotmart-webhook).
- Para publicar o app: build com NEXT_PUBLIC_SUPABASE_URL e NEXT_PUBLIC_SUPABASE_ANON_KEY (a chave publishable, sb_publishable_...), depois node scripts/gerar-service-worker.mjs, zip do conteúdo de out/ e envio pelo conector da Hostinger. O passo a passo está no skill hostinger:deploy-to-hosting; use domínio app.dividaclara.com.br, usuário u629614698 e hosting_websites_deploy-static-site-archive. Nunca publique public/pacote-demo.json.
- Venda: R$ 27,90 na Hotmart. Página de vendas: https://receitas.dividaclara.com.br. Suporte: suporte@dividaclara.com.br. Rodapé: "Receitas Bem Leves · Kenui Cabral · CNPJ 52.594.756/0001-00".
- Público: brasileiros com mais de 45 anos, muitos com diabetes ou pré-diabetes, pouco à vontade com tecnologia.

REGRAS
- Chaves secretas (secret key do Supabase, chave do Resend, hottok da Hotmart, senhas) nunca aparecem no chat nem em arquivos do repositório. Copie de uma tela e cole direto no campo de segredo, sempre pelo navegador.
- Antes de qualquer ação que custe dinheiro ou créditos, que não dê para desfazer ou que publique algo para o público, me mostre o que vai fazer e espere meu ok. Isso inclui: apagar algo, mudar preço, ligar anúncio, aumentar verba e gastar créditos do Higgsfield.
- Não crie conta, não aceite termos de uso e não resolva "não sou um robô" por mim: me peça.
- Nada de promessa de saúde ("controla glicemia", "cura", "emagrece"), depoimento inventado, escassez falsa nem "de R$ X por R$ Y" falso. Nos anúncios, nunca diga nem insinue que o espectador tem diabetes. Fale de "quem corta o açúcar" e da comida. Antes de escrever textos de venda, carregue os skills voz-humana e conformidade-anuncios.

TAREFA 1: Hotmart (plano-do-funil.md, seção 5)
1. Cadastre os 3 produtos novos com garantia de 7 dias:
   - Caderno de Receitas para Imprimir, R$ 14,90, arquivo docs/produtos/caderno-de-receitas-para-imprimir.pdf;
   - Cardápio de 12 Semanas + Guia de Marmitas, R$ 47, arquivos docs/produtos/cardapio-de-12-semanas.pdf e docs/produtos/guia-de-marmitas-da-semana.pdf;
   - Cardápio de 12 Semanas, R$ 27, arquivo docs/produtos/cardapio-de-12-semanas.pdf.
   Baixe os PDFs do GitHub pelo navegador.
2. Configure o order bump (Caderno) no produto principal, com o título e a descrição do plano.
3. Configure o Funil de Vendas:
   - upsell: https://app.dividaclara.com.br/oferta/cardapio-12-semanas/
   - downsell: https://app.dividaclara.com.br/oferta/so-o-cardapio/
   - final: https://app.dividaclara.com.br/obrigado/
   - use os textos dos botões do plano.
   Se a Hotmart der um código de botões diferente do que está em componentes/PaginaOferta.jsx, troque no código e publique de novo.
4. Personalize o checkout do produto principal:
   - imagens de docs/funil/ (checkout-topo-1200x300.png, checkout-topo-celular-800x400.png, checkout-lateral-400x900.png);
   - cores #7B1E2C e #137A3D;
   - Pix em destaque e cartão parcelado ligado.
   Se a Hotmart pedir outros tamanhos, gere de novo com o script que monta essas imagens e explique o que mudou.
5. No webhook já cadastrado (URL acima), inclua os 3 produtos novos.
6. Anote o ID dos 4 produtos (principal + 3 novos).
7. Se o plano tiver recuperação automática de carrinho abandonado, ligue com os textos do plano.

TAREFA 2: Supabase (plano-do-funil.md, seção 6)
1. No SQL Editor, rode supabase/migrations/0002_produtos_extras.sql.
2. Em Edge Functions → hotmart-webhook (endereço smart-function) → Code, cole supabase/painel-hotmart-webhook.ts e publique. Confira que "Verify JWT with legacy secret" continua desligado.
3. Em Edge Functions → Secrets, crie HOTMART_PRODUTOS com os IDs da Hotmart, por exemplo:
   {"ID_APP":["app"],"ID_CADERNO":["caderno"],"ID_12_MARMITAS":["cardapio12","marmitas"],"ID_12":["cardapio12"]}
   O ID do app principal precisa estar na lista: com o segredo criado, produto fora da lista é ignorado.
4. Publique o conteúdo dos extras com node scripts/publicar-extras.mjs. Ele precisa de SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY. Peça a secret key pelo painel do Supabase para eu colar direto no terminal como variável de ambiente; ela não vai para o chat.
5. Gere uma secret key nova no Supabase, apague a antiga (sb_secret_G_Z0…, que vazou numa conversa anterior) e atualize onde ela for usada.
6. Teste com os botões de teste do webhook da Hotmart:
   - compra aprovada de cada produto: o comprador ganha o produto certo em produtos_comprados;
   - reembolso só do upsell: tira só o upsell;
   - reembolso do principal: bloqueia o app.
   Depois, apague os compradores de teste.

TAREFA 3: Fotos realistas das 500 receitas no Higgsfield (pelo navegador, SEM GASTAR CRÉDITOS)
1. Abra o Higgsfield no meu navegador. Meu plano é Ultra. Encontre e ative as gerações ilimitadas ("Unlimited") do plano. Me diga quais modelos de imagem entram no ilimitado.
2. Só gere imagens em modelo e configuração cobertos pelo ilimitado. Se o contador de créditos mudar, ou se a tela mostrar custo em créditos, pare na hora e me avise. Faça primeiro 10 imagens de teste e me mostre antes de seguir.
3. Prompt de cada foto: monte a partir dos dados da receita (conteudo/receitas/*.json), com o nome do prato, os ingredientes visíveis e o tipo de louça.
   - Estilo: fotografia de comida realista, luz natural, vista 3/4, mesa de casa brasileira, formato 4:3, sem texto e sem pessoas.
   - Nunca mostre ingrediente que a receita não tem, como açúcar polvilhado, chocolate ao leite ou pão branco.
4. Revise cada foto antes de usar. Refaça (no ilimitado) as que tiverem erro visível: comida estranha, ingrediente a mais ou mãos deformadas.
5. Converta para WebP com cerca de 800 px de largura e menos de 80 KB, salve em public/fotos/receitas/<id>.webp e preencha o campo "foto" de cada receita.
6. Ajuste o app:
   - a foto aparece no cartão da lista e na página da receita, com a ilustração SVG como reserva quando a foto não carregar;
   - escreva "Imagem ilustrativa" em letra pequena embaixo da foto, na página da receita;
   - o service worker não deve baixar as 500 fotos de uma vez: cada foto é guardada no celular quando a receita é aberta (o sw-modelo.js já trata /fotos/ assim).
   Rode o validador e os testes, faça o build, publique e confira no celular (375 px) e sem internet.
7. Faça commit e push na branch ccr-ca9ce95d-5i51f9.

TAREFA 4: Vídeos de anúncio no Higgsfield (pelo navegador, no ilimitado)
1. Carregue os skills voz-humana, conformidade-anuncios e skill-5-anuncios-virais. Antes de gerar qualquer vídeo, escreva 3 roteiros de 15 a 30 segundos, um por ângulo:
   - "pão de volta no café sem açúcar adicionado";
   - "o bolo que não amarga";
   - "o que tem no rótulo do mercado".
2. Use as telas reais do app e as fotos das receitas. Pessoas, vozes ou avatares realistas gerados por IA levam o aviso "imagem gerada por IA" no vídeo. Nada de depoimento falso nem de "antes e depois".
3. Gere só no ilimitado, com a mesma regra de parar se aparecer custo em créditos. Formatos: 9:16 (Reels e Stories) e 1:1 (feed).
4. Me mostre os vídeos e a Passada de Conformidade de cada roteiro. Não suba nada no Meta sem o meu ok.

TAREFA 5: Página de vendas (receitas.dividaclara.com.br)
1. Descubra onde a página é editada (Hostinger, construtor ou arquivo) e me diga.
2. Proponha e, com meu ok, faça estas mudanças:
   - tirar "para diabetes" da lista de objetivos;
   - corrigir o exemplo do misto quente (no app: 1 porção, 10 min, ovos, parmesão, presunto e mussarela);
   - trocar as imagens pelas fotos novas das receitas.

AO FINAL, me entregue:
- o que foi feito, com links;
- o que testou e o resultado;
- quanto crédito do Higgsfield foi gasto (deve ser zero);
- o que ainda depende de mim.
