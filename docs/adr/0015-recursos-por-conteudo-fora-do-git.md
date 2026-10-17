---
status: accepted
---

# Recursos por conteúdo fora do Git

Na Q40, o usuário definiu armazenar os arquivos usados pelo projeto por conteúdo,
identificado por hash, para que um mesmo arquivo usado em vários projetos não
ocupe espaço repetido. Guardar originais, áudios, alinhamentos e versões necessárias
ao desfazer; prévias e arquivos reduzidos são derivados regeneráveis. Isso permite
reabrir o projeto sem depender da permanência dos arquivos na pasta de origem.

Mídias, áudios e dados dos projetos ficam fora do controle de versão: o repositório
é público e esses dados nunca vão para o Git. A regra se aplica ao armazenamento
de produção; esta sessão continua alterando apenas documentação de especificação.

A interface mostra o espaço ocupado por projeto e a limpeza só ocorre por escolha
do autor. O compartilhamento exige distinguir conteúdo referenciado de espaço
físico recuperável: remover um vínculo não libera um arquivo ainda usado por outro
projeto ou por um histórico preservado. O desenho deve mostrar o conteúdo
referenciado pelo projeto e o espaço que cada limpeza realmente pode liberar,
mantendo as versões até uma escolha explícita de limpeza.

A Q47 aplica a mesma retenção às exportações anteriores: MP4 e SRT incluem a
revisão nos nomes e permanecem guardados até o autor apagar. Arquivos derivados
serem regeneráveis não autoriza limpar o acervo gerenciado sem essa escolha.

A decisão troca armazenamento independente por projeto por um acervo compartilhado
com referências explícitas, reduzindo duplicação e exigindo limpeza que considere
todos os vínculos. Este registro é de planejamento e não autoriza importar mídias,
alterar arquivos existentes ou implementar o armazenamento nesta sessão.
