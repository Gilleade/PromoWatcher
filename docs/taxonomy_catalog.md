# Catálogo de taxonomia de produtos

O catálogo oficial está em `app/products/category_catalog.csv` e sua versão
atual é `1.0.0`. Cada categoria declara família, campos de identidade, campos
de variante, unidades aceitas e conflitos rígidos.

Nesta etapa o catálogo é somente descritivo: o extrator produtivo continua
usando as categorias legadas. `taxonomy_catalog.py` oferece a tradução
explícita entre os nomes antigos e os canônicos, mas não altera registros nem
decisões automaticamente.

Mudanças futuras devem atualizar a versão, manter nomes canônicos estáveis e
incluir testes. Categorias desconhecidas não devem ser convertidas em uma
categoria genérica; elas permanecem sem resolução para revisão humana ou pela
camada de IA em modo sombra.
