# Domain Docs

O MyCut usa layout **single-context**, com um vocabulário e decisões de domínio
compartilhados pelo repositório.

## Antes de explorar

- Leia `GLOSSARY.md` na raiz para conhecer os termos do domínio.
- Leia em `docs/adr/` as decisões que afetam a área em análise.

Se esses arquivos ainda não existirem, prossiga silenciosamente.
A skill `domain-modeling`, também usada por `grill-with-docs` e
`improve-codebase-architecture`, cria o glossário e os ADRs quando termos
ou decisões forem efetivamente definidos.

## Estrutura

```text
/
├── GLOSSARY.md
└── docs/adr/
    ├── 0001-<decisao>.md
    └── 0002-<decisao>.md
```

## Vocabulário

Use os termos do glossário em títulos de tickets, propostas, hipóteses e testes.
Se faltar um conceito necessário, registre a lacuna para `domain-modeling`;
avalie antes se já existe um termo equivalente.

## Conflitos com decisões

Se uma proposta contrariar um ADR existente, identifique a decisão e explique
por que sua revisão está sendo proposta, antes de tratá-la como substituída.
