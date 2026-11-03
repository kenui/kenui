# Receitas Bem Leves — Fase 1: proposta técnica

Status: **aprovada em 03/11/2026** (ver "Decisões aprovadas" no fim).

---

## 1. Resumo da recomendação

| Peça | Escolha | Custo mensal |
|---|---|---|
| App (PWA) | Next.js com **export estático** (`output: 'export'`), React, CSS próprio | — |
| Hospedagem do app | **Hostinger** (subdomínio, ex.: `app.seudominio.com.br`), publicado por GitHub Actions | R$ 0 (já pago) |
| Login, banco, webhook | **Supabase**: login por e-mail, Postgres com regras de acesso (RLS), Edge Function do webhook | R$ 0 no plano grátis (ver risco na seção 4) |
| Envio de e-mail | **Resend** (SMTP) com domínio próprio verificado | R$ 0 até 3.000 e-mails/mês |
| Ilustrações | SVG gerado por componentes React a partir dos dados da receita | R$ 0 (não há arquivos de imagem) |
| Uso offline | Service worker próprio + cache das receitas no aparelho | — |

Sua sugestão (Next.js + Supabase + Edge Function) é a que eu manteria. Mudo três detalhes: **export estático em vez de SSR**, **app no Hostinger em vez de Vercel**, e **e-mail por um SMTP próprio**, porque o e-mail padrão do Supabase não serve para produção.

---

## 2. Arquitetura e justificativa

```
                 ┌──────────────── Hotmart ────────────────┐
                 │  compra / reembolso / chargeback        │
                 └───────────────┬─────────────────────────┘
                                 │ POST (webhook 2.0.0, header X-HOTMART-HOTTOK)
                                 ▼
┌──────────────────────── Supabase ───────────────────────────────┐
│ Edge Function "hotmart-webhook"                                 │
│   valida hottok → grava evento → libera ou bloqueia comprador   │
│   compra aprovada → cria usuário → e-mail de boas-vindas        │
│                                                                 │
│ Auth (login por e-mail, só para quem comprou)                   │
│ Postgres:  compradores, eventos_hotmart, receitas (pacote),     │
│            dados_do_usuario (favoritos, trocas do plano)        │
│ RLS: só lê receitas quem tem status "ativo"                     │
└───────────────▲─────────────────────────────────────────────────┘
                │ HTTPS (supabase-js)
┌───────────────┴──────── Celular / computador ───────────────────┐
│ PWA estática (Hostinger)                                        │
│   telas: Início, Receitas, Favoritos, Plano, Perfil, Bônus      │
│   service worker: guarda app, fontes, fotos e pacote de receitas│
│   IndexedDB: receitas, favoritos, lista de compras, vistos      │
│   ilustrações SVG desenhadas na hora a partir dos dados         │
└─────────────────────────────────────────────────────────────────┘
```

### Por que export estático e não SSR
- O conteúdo muda só quando você publica receitas novas. Não há nada que precise ser montado no servidor a cada visita.
- Arquivos estáticos rodam em qualquer lugar, inclusive no Hostinger compartilhado, que não roda Next.js com servidor de forma confortável.
- Fica mais simples de deixar offline: o service worker guarda arquivos fixos.
- O que precisa de servidor (webhook, login, bloqueio) já fica no Supabase.

### Onde ficam as receitas (decisão importante, ver pergunta 1)
Se as 500 receitas forem embutidas nos arquivos estáticos, qualquer pessoa consegue baixá-las sem pagar, só abrindo o endereço do arquivo. Por isso recomendo:

- **Fonte da verdade no repositório**: um arquivo JSON por receita, validado pelo script da fase 2.
- **Na publicação**, um script junta tudo num pacote (cerca de 1,2 MB, ~250 KB compactado) e envia para uma tabela do Supabase protegida por RLS: só baixa quem está logado **e** com compra ativa.
- **No aparelho**, o app baixa o pacote uma vez, guarda no IndexedDB e passa a funcionar offline. Ao reconectar, confere se há versão nova.
- O app (telas, botões, estilos) continua público e estático; só o conteúdo fica protegido.

Isso exige que o repositório do projeto seja **privado** (ver pergunta 8).

### Login: link mágico + código de 6 dígitos
Problema real do público-alvo: no **iPhone**, o app instalado na tela inicial não compartilha o login com o Safari. A pessoa clica no link do e-mail, o Safari abre logado, mas o ícone na tela inicial continua pedindo login. No Android isso não acontece.

Solução que proponho, sem tela nova: o mesmo e-mail traz o botão "Entrar no app" **e** um código de 6 dígitos ("ou digite este código no app"). O Supabase já suporta os dois no mesmo e-mail. Além disso:
- `shouldCreateUser: false`: só recebe link quem já está na tabela de compradores (criado pelo webhook).
- O link abre uma página com um botão "Entrar" em vez de logar sozinho, porque alguns provedores de e-mail (Outlook, antivírus) abrem os links automaticamente e "gastam" o link antes da pessoa.
- Sessão longa (a pessoa não precisa logar de novo a cada semana).

### Bloqueio por reembolso
- Webhook marca o comprador como `bloqueado` e encerra as sessões dele.
- Na próxima vez que o aparelho estiver online, o app tenta atualizar o pacote, recebe "sem acesso", apaga as receitas guardadas e mostra a tela de login.
- Limitação honesta: um aparelho que fique **sempre offline** continua com as receitas guardadas até se conectar. Proponho que o app exija uma conferência online pelo menos a cada 30 dias.

### Uso offline
- Service worker escrito à mão (pequeno, sem biblioteca) ou Serwist; decido na fase de código pelo que ficar mais simples com o export estático.
- Guarda: telas do app, fontes, ícones, as 6 fotos e o pacote de receitas.
- As ilustrações são desenhadas pelo próprio código a partir dos dados, então não há 500 imagens para baixar: funcionam offline sem custo extra.
- Fontes DM Serif Display e Atkinson Hyperlegible (licença livre OFL) servidas pelo próprio app, não pelo Google Fonts, para funcionar offline.

### Outras escolhas
- **Busca sem acento**: com 500 receitas, um índice em memória com texto normalizado (`"pão" → "pao"`) responde instantaneamente; não precisa de biblioteca nem de servidor.
- **Modo cozinha**: Wake Lock API. Funciona no Chrome do Android; no iPhone funciona no Safari a partir do iOS 16.4 e no app instalado a partir do iOS 18.4. Onde não houver suporte, a tela mostra um aviso simples em vez de falhar.
- **Imprimir**: CSS de impressão (`@media print`) nas páginas de receita, plano e lista de compras.
- **Lista de compras**: cada ingrediente tem cadastro único com peso por medida caseira, o que permite somar "1/2 xícara + 3 colheres de sopa de farinha de amêndoas" e mostrar de volta em medida caseira, agrupado por seção do mercado.
- **Plano de 4 semanas**: arquivo de dados gerado por script a partir das receitas (sem repetir prato na mesma semana). As trocas da pessoa ficam salvas nos dados dela.

### Alternativas que considerei e descartei
- **Hostinger PHP + MySQL para login e webhook** (custo zero e sem risco de pausa): teria que escrever login por link mágico, sessões e segurança à mão. Mais código, mais risco, mais manutenção. Não compensa.
- **Firebase**: equivalente ao Supabase em custo, mas o login por link no e-mail é mais trabalhoso de personalizar em português e não tem o código de 6 dígitos pronto.
- **Vercel**: o plano grátis (Hobby) proíbe uso comercial. Para um produto pago teria que ser o plano Pro (US$ 20/mês). Não vale, porque o app é estático.
- **Netlify**: seria uma boa alternativa grátis ao Hostinger (publicação automática a cada alteração). Fica como plano B se o Hostinger der trabalho com o service worker ou com o HTTPS do subdomínio.

---

## 3. O que vai onde

| Onde | O quê |
|---|---|
| **GitHub (repositório privado)** | Código do app, receitas em JSON, cálculos nutricionais, validador, função do webhook, README |
| **GitHub Actions** | A cada publicação: roda o validador, gera o app estático, envia para o Hostinger e envia o pacote de receitas para o Supabase |
| **Hostinger** | Arquivos estáticos do app num subdomínio com HTTPS; `.htaccess` com regras de cache (o `sw.js` nunca fica em cache) |
| **Supabase** | Login, tabelas, regras de acesso, Edge Function `hotmart-webhook`, armazenamento das 6 fotos |
| **Resend** | Envio do e-mail de boas-vindas e do e-mail de login, com remetente do seu domínio (SPF/DKIM configurados no DNS do Hostinger) |
| **Hotmart** | Cadastro da URL do webhook (o caminho exato vai na fase 5: em geral fica em *Ferramentas → Webhook (API e notificações) → Cadastrar webhook*, versão 2.0.0, escolhendo o produto e os eventos) |

---

## 4. Custos e riscos

- **Supabase grátis pausa o projeto depois de 7 dias sem uso.** Com compradores entrando todo dia isso não acontece, mas numa semana sem vendas e sem acessos o login e o webhook param até alguém reativar no painel. Opções:
  - (a) Plano grátis + uma tarefa automática diária que faz uma consulta leve ao banco (R$ 0, funciona na prática, mas não é garantia oficial).
  - (b) Supabase Pro, **US$ 25/mês** (cerca de R$ 140), sem pausa, com backup diário.
  - Recomendo começar com (a) e migrar para (b) quando as vendas justificarem. Ver pergunta 2.
- **E-mail**: o SMTP padrão do Supabase só envia para membros da equipe do projeto e com limite de poucos por hora. Para clientes, um SMTP próprio é obrigatório. Resend grátis: 3.000/mês e 100/dia. Se passar de 100 vendas num dia, o plano pago custa US$ 20/mês. Alternativa: Brevo grátis (300/dia).
- **Domínio**: preciso de um domínio seu para o app e para o remetente dos e-mails (ver pergunta 3).

---

## 5. Modelo de dados

São três arquivos de dados no repositório. A receita aponta para ingredientes de um cadastro único, e é esse cadastro que permite calcular a nutrição, somar a lista de compras, agrupar por seção do mercado, validar ingredientes proibidos e escolher os enfeites da ilustração.

### 5.1 Receita (`conteudo/receitas/pao-de-frigideira.json`)

Exemplo ilustrativo. Os números de nutrição abaixo são só para mostrar o formato; os valores reais saem do cálculo da fase 2.

```json
{
  "id": "rbl-0001",
  "slug": "pao-de-frigideira",
  "nome": "Pão de frigideira",
  "descricao": "Pão macio feito em 5 minutos na frigideira, bom para sanduíche.",
  "categoria": "paes_substitutos",
  "destaques": ["substitutos_do_pao", "cafe_sem_pao", "rapidas_15min"],
  "refeicoes_do_plano": ["cafe_da_manha", "lanche"],

  "tempo": {
    "preparo_min": 3,
    "cozimento_min": 4,
    "total_min": 7
  },
  "rendimento": { "quantidade": 1, "unidade": "pão (2 fatias)" },
  "porcoes": 1,
  "porcao": { "descricao": "1 pão", "gramas": 85 },

  "ingredientes": [
    {
      "ingrediente": "ovo",
      "quantidade": 1,
      "medida": "unidade",
      "texto": "1 ovo"
    },
    {
      "ingrediente": "farinha-de-amendoas",
      "quantidade": 2,
      "medida": "colher_sopa",
      "texto": "2 colheres (sopa) de farinha de amêndoas",
      "alternativa": {
        "ingrediente": "farelo-de-aveia",
        "texto": "ou 2 colheres (sopa) de farelo de aveia",
        "observacao": "Fica um pouco mais firme e com mais carboidrato."
      }
    },
    {
      "ingrediente": "leite-integral",
      "quantidade": 1,
      "medida": "colher_sopa",
      "texto": "1 colher (sopa) de leite"
    },
    {
      "ingrediente": "fermento-quimico",
      "quantidade": 0.5,
      "medida": "colher_cha",
      "texto": "1/2 colher (chá) de fermento em pó"
    },
    {
      "ingrediente": "sal",
      "quantidade": null,
      "medida": "pitada",
      "texto": "1 pitada de sal",
      "a_gosto": true
    }
  ],

  "preparo": [
    { "texto": "Numa tigela, bata o ovo com um garfo até misturar bem." },
    { "texto": "Junte a farinha, o leite e o sal e mexa até virar uma massa lisa." },
    { "texto": "Por último, misture o fermento sem bater muito." },
    { "texto": "Aqueça uma frigideira pequena untada em fogo baixo e despeje a massa.", "aviso": "Fogo baixo para não queimar por fora." },
    { "texto": "Tampe e deixe 2 minutos. Vire e deixe mais 2 minutos.", "temporizador_min": 4 },
    { "texto": "Corte ao meio na horizontal e recheie como quiser." }
  ],
  "forno": null,

  "dicas": [
    { "tipo": "substituicao", "texto": "Sem farinha de amêndoas? Use farelo de aveia na mesma medida." },
    { "tipo": "conservacao", "texto": "Guarde na geladeira por até 2 dias e aqueça na frigideira." }
  ],

  "nutricao": {
    "por_porcao": { "kcal": 162, "carboidratos_g": 5.4 },
    "calculado_com": "ingredientes principais (sem as alternativas)",
    "fonte": "TACO 4ª ed. + USDA FoodData Central",
    "arquivo_calculo": "conteudo/nutricao/rbl-0001.json",
    "aproximado": true
  },

  "etiquetas": {
    "sem_acucar_adicionado": true,
    "low_carb": true
  },

  "ilustracao": {
    "prato_base": "pao_frigideira",
    "massa": "clara",
    "cobertura": null,
    "recheio": null,
    "enfeites": ["gergelim"],
    "louca": "auto",
    "mesa": "auto",
    "forcar": false
  },
  "foto": "fotos/pao-de-frigideira.jpg",

  "busca": { "termos_extras": ["pao rapido", "pao low carb", "pao sem farinha de trigo"] },
  "revisao": { "status": "aprovada", "observacoes": "" }
}
```

Regras sobre esse modelo:
- `etiquetas.low_carb` **não é digitado à mão**: o validador calcula (carboidratos da porção ≤ 15 g) e rejeita a receita se o arquivo disser outra coisa.
- `etiquetas.sem_acucar_adicionado` é sempre `true`; o validador confere cada ingrediente contra a lista de proibidos do cadastro.
- `nutricao.por_porcao` também é conferido: o validador refaz a conta a partir de `arquivo_calculo` e rejeita se não bater.
- `ilustracao.enfeites` é preenchido automaticamente pela tabela ingrediente → enfeite (fase 4). Só um enfeite que exista nos ingredientes é aceito. `forcar: true` permite ajustar à mão em casos raros, mas mesmo assim o validador não deixa desenhar ingrediente que a receita não tem.
- `ilustracao.louca`, `mesa` e as variações (ângulo, posição dos enfeites) saem de um sorteio com semente fixa pelo `id`: a mesma receita sempre gera o mesmo desenho, e receitas parecidas ficam diferentes.
- `foto` só existe nas 6 receitas da página de vendas. Na lista aparece a ilustração; na página da receita, a foto.

Valores possíveis:
- `categoria`: `cafe_da_manha`, `paes_substitutos`, `lanches`, `almoco_jantar`, `doces_bolos`, `ceia`
- `destaques`: `cafe_sem_pao`, `substitutos_do_pao`, `doces_e_bolos`, `rapidas_15min` (os 4 da tela Início; `rapidas_15min` é calculado pelo tempo total)
- `refeicoes_do_plano`: `cafe_da_manha`, `lanche`, `almoco`, `jantar`
- `medida`: `unidade`, `xicara`, `meia_xicara`, `colher_sopa`, `colher_cha`, `copo_americano`, `fatia`, `dente`, `ramo`, `pitada`, `g`, `ml`
- `ilustracao.massa`: `clara`, `chocolate`, `cenoura`, `banana`, `integral`
- `ilustracao.prato_base`: um dos 30 a 40 pratos base da fase 4 (`bolo_redondo`, `bolo_forma`, `bolo_caneca`, `muffin`, `cookie`, `brownie`, `pudim`, `mousse_taca`, `torta`, `pave`, `pao_forma`, `pao_frigideira`, `pao_de_queijo`, `tapioca`, `crepioca`, `panqueca_pilha`, `waffle`, `omelete`, `ovos_mexidos`, `misto_quente`, `wrap`, `sanduiche`, `salada`, `sopa`, `frango`, `carne`, `peixe`, `legumes_assados`, `arroz_graos`, `pure`, `vitamina_copo`, `picole`, `geleia_pote`, `ceia_peru`, `salpicao`...)

### 5.2 Cadastro de ingredientes (`conteudo/ingredientes.json`)

```json
{
  "id": "farinha-de-amendoas",
  "nome": "farinha de amêndoas",
  "sinonimos": ["farinha de amendoa", "amendoa moida"],
  "secao_mercado": "mercearia",
  "facil_de_achar": false,
  "alternativa_padrao": "farelo-de-aveia",
  "gramas_por_medida": {
    "xicara": 96,
    "colher_sopa": 7,
    "colher_cha": 2.3
  },
  "nutricao_100g": {
    "kcal": 571,
    "carboidratos_g": 21.4,
    "fonte": "USDA FoodData Central",
    "codigo_fonte": "FDC 2261420"
  },
  "proibido": false,
  "adocante": null,
  "enfeite": "amendoa_lascas"
}
```

- `proibido: true` marca açúcar, mel, melado, açúcar de coco, rapadura, xaropes, leite condensado comum e afins. O validador também procura essas palavras no texto livre (`texto`, `preparo`, `dicas`) para pegar, por exemplo, "polvilhe açúcar".
- `adocante`: `eritritol`, `xilitol`, `stevia`, `sucralose`, `fruta` ou `null`.
- `secao_mercado`: `hortifruti`, `padaria_cereais`, `laticinios_frios`, `carnes_ovos`, `mercearia`, `temperos`, `congelados`, `bebidas`.
- `enfeite`: liga o ingrediente à biblioteca de enfeites da fase 4; `null` entra na lista de "ingredientes sem enfeite" que você pediu.
- `gramas_por_medida` serve para duas coisas: calcular a nutrição e somar a lista de compras.

### 5.3 Cálculo nutricional para conferência (`conteudo/nutricao/rbl-0001.json`)

Gerado por script, nunca digitado. Você consegue abrir e conferir linha por linha.

```json
{
  "receita": "rbl-0001",
  "porcoes": 1,
  "linhas": [
    { "ingrediente": "ovo", "texto": "1 ovo", "gramas": 50, "kcal": 71.5, "carboidratos_g": 0.8, "fonte": "TACO 488 Ovo, de galinha, inteiro, cru" },
    { "ingrediente": "farinha-de-amendoas", "texto": "2 colheres (sopa)", "gramas": 14, "kcal": 79.9, "carboidratos_g": 3.0, "fonte": "USDA FDC 2261420" },
    { "ingrediente": "leite-integral", "texto": "1 colher (sopa)", "gramas": 15, "kcal": 9.2, "carboidratos_g": 0.7, "fonte": "TACO 457 Leite, de vaca, integral" },
    { "ingrediente": "fermento-quimico", "texto": "1/2 colher (chá)", "gramas": 2, "kcal": 1.8, "carboidratos_g": 0.9, "fonte": "TACO Fermento em pó, químico" },
    { "ingrediente": "sal", "texto": "1 pitada", "gramas": 0.5, "kcal": 0, "carboidratos_g": 0, "fonte": "TACO Sal" }
  ],
  "total": { "kcal": 162.4, "carboidratos_g": 5.4 },
  "por_porcao": { "kcal": 162, "carboidratos_g": 5.4 }
}
```

(Os números deste exemplo também são ilustrativos. Os códigos e valores da TACO serão conferidos um a um na fase 2.)

### 5.4 Dados de cada comprador (Supabase)

```
compradores        email, status (ativo | bloqueado), id_transacao_hotmart, produto, criado_em, atualizado_em
eventos_hotmart    id_evento (único, evita processar o mesmo aviso duas vezes), tipo, email, conteudo, recebido_em
dados_do_usuario   user_id, favoritos[], trocas_do_plano{}, atualizado_em
pacote_receitas    versao, conteudo (JSON), publicado_em      ← só lê quem está "ativo"
```

Últimas vistas e caixas marcadas da lista de compras ficam só no aparelho.

---

## 6. Estrutura do repositório (prevista)

```
app/                 telas (Next.js, export estático)
componentes/         interface + ilustracoes/ (pratos base e enfeites)
conteudo/
  receitas/          um JSON por receita
  ingredientes.json  cadastro único
  nutricao/          cálculos para conferência
  plano.json         cardápio de 4 semanas
  bonus/             textos dos 5 bônus
scripts/
  validar.ts         validador das regras
  calcular-nutricao.ts
  gerar-plano.ts
  folha-de-contato.ts
supabase/
  migrations/        tabelas e regras de acesso
  functions/hotmart-webhook/
public/              ícones, manifesto, fontes, sw.js, fotos
.github/workflows/   validação e publicação
README.md
```

---

## 7. Decisões que preciso de você

1. **Proteger as receitas atrás do login?** Recomendo **sim** (seção 2). Sem isso, o conteúdo pago fica baixável por qualquer pessoa.
2. **Supabase**: começar no grátis com a consulta diária automática, ou já no Pro (US$ 25/mês)? Recomendo **grátis no início**.
3. **Domínio**: qual endereço o app vai usar (ex.: `app.dividaclara.com.br` ou um domínio próprio do "Receitas Bem Leves")? E o remetente dos e-mails pode ser desse mesmo domínio? O suporte fica em `suporte@dividaclara.com.br`, como você pediu.
4. **Como contar carboidrato dos adoçantes**: a TACO e a USDA contam carboidrato total (com fibra). O eritritol aparece com ~100 g de carboidrato por 100 g, mas o corpo praticamente não absorve. Proposta: **carboidrato total, contando eritritol, stevia e sucralose como 0 g e 0 kcal, e xilitol com o valor cheio** (ele é parcialmente absorvido), com a regra escrita no arquivo de cálculo. A alternativa é contar tudo cheio, o que deixa quase nenhum doce como low carb.
5. **Favoritos e trocas do plano**: guardar só no aparelho (mais simples, mas some ao trocar de celular) ou também na conta (recomendo: uma cópia simples na conta, para não perder ao trocar de celular)?
6. **Eventos da Hotmart**: além de reembolso, chargeback e cancelamento, bloquear também em **pedido de reembolso em análise** (`PURCHASE_PROTEST`)? Recomendo **não bloquear** nesse caso, só quando o reembolso for concluído.
7. **Telas de referência**: o arquivo `telas.jpg` não chegou até mim. Ele não está no repositório nem na conversa. Pode enviar de novo ou colocar no repositório?
8. **Repositório**: este repositório (`kenui/kenui`) é o seu **repositório de perfil do GitHub**. O README dele aparece na sua página pública, e o repositório provavelmente é público, o que deixaria todas as receitas visíveis. Recomendo criar um repositório **privado** só para o app (ex.: `kenui/receitas-bem-leves`) e trabalhar nele a partir da fase 2. Se preferir continuar aqui, aviso que o README do app vai substituir o do seu perfil.

---

## Decisões aprovadas

1. Receitas protegidas atrás do login: **sim**.
2. Supabase: **plano grátis**, com consulta automática diária para não pausar.
3. Domínio: **app.dividaclara.com.br**, com e-mails saindo do mesmo domínio.
4. Carboidrato dos adoçantes: **eritritol, stevia e sucralose contam 0 g e 0 kcal; xilitol conta cheio** (2,4 kcal/g).
5. Favoritos e trocas do plano: **no aparelho e com cópia na conta**.
6. Pedido de reembolso em análise: **não bloqueia**; bloqueia só reembolso concluído, chargeback e cancelamento.
7. Telas de referência (`telas.jpg`): **ainda não recebidas**.
8. Repositório: não foi possível criar um repositório novo a partir desta sessão; o projeto fica na pasta `receitas-bem-leves/` do repositório `kenui/kenui`, sem alterar o README do perfil.
