// App 100% estático (export): roda em qualquer hospedagem, inclusive no Hostinger compartilhado.
// trailingSlash gera /receitas/index.html, que o Apache serve sem regras extras.
const config = {
  output: 'export',
  trailingSlash: true,
  images: { unoptimized: true },
  reactStrictMode: true,
};
export default config;
