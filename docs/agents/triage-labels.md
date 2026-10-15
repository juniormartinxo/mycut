# Triage Labels

Os nomes canônicos das skills correspondem aos valores do campo nativo
`Triagem`, do tipo `select`, no projeto `jm.MYC`.

| Papel na skill | Valor em Triagem | Significado |
| --- | --- | --- |
| `needs-triage` | `needs-triage` | Precisa de avaliação |
| `needs-info` | `needs-info` | Aguarda informações |
| `ready-for-agent` | `ready-for-agent` | Especificado e pronto para um agente |
| `ready-for-human` | `ready-for-human` | Requer implementação humana |
| `wontfix` | `wontfix` | Não será executado |

## Ler e alterar a triagem

Quando uma skill disser "triage label", "apply label" ou "remove label" para
um desses cinco papéis, opere sobre o campo `Triagem`.

1. Consulte `get_project({projectKey: "jm.MYC"})` e localize o campo
   `Triagem` e a opção pelo valor exato.
2. Leia a issue. O campo sem seleção corresponde a "unlabeled"/nunca triada.
3. Para definir um papel, use
   `set_issue_field_value({issueId: <id>, fieldId: <campo>, optionIds: [<opcao>]})`.
   Mantenha exatamente uma opção. Para remover o papel, use `optionIds: []`.
4. Releia `get_issue` e verifique `fieldValues`.

O campo é a fonte de verdade; não crie rótulos duplicados nem marcadores na
descrição para esses papéis. Para listar por triagem, leia `fieldValues`
das issues retornadas e filtre pelo campo/opção; `labelIds` filtra rótulos,
não valores de campos.

As transições seguem a skill `triage`: sem valor → `needs-triage` →
`needs-info`, `ready-for-agent`, `ready-for-human` ou `wontfix`.
Quando houver resposta às informações pendentes, retorne a `needs-triage`.
A coluna de execução segue [issue-tracker.md](issue-tracker.md);
`ready-for-agent` por si só não inicia a implementação.

## Categorias

As categorias continuam usando rótulos existentes: `bug` corresponde a `Bug`;
`enhancement` corresponde a `Feature` para funcionalidade nova ou
`Improvement` para melhoria. Ao categorizar, mantenha uma dessas categorias
e preserve os demais rótulos do ticket.
