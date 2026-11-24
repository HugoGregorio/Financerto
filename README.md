# FinanCerto — Etapa 3: interface gráfica

Aplicação desktop para controle de finanças pessoais, desenvolvida em Python com Tkinter e SQLite.

## Funcionalidades disponíveis

- Painel mensal com saldo, receitas e despesas.
- Gráfico de despesas agrupadas por categoria.
- Cadastro, edição e exclusão de lançamentos financeiros.
- Cadastro de categorias personalizadas.
- Histórico de movimentações com filtro por mês, tipo e texto.
- Persistência local em banco de dados SQLite.

## Requisitos

- Python 3.10 ou superior.
- Tkinter habilitado na instalação do Python (normalmente já incluído).
- Não há dependências externas de Python.

## Como executar

1. Extraia todos os arquivos para uma mesma pasta.
2. Abra um terminal nessa pasta.
3. Execute:

```bash
py app.py
```

Na primeira execução, o programa cria automaticamente o arquivo `financerto.db` e as categorias iniciais.

## Arquivos

- `app.py`: interface gráfica e fluxo de navegação.
- `database.py`: regras de persistência e operações com o SQLite.
- `schema.sql`: tabelas, restrições e índices do banco de dados.
- `test_database.py`: testes automatizados da camada de dados.
- `test_app_persistence.py`: teste de integração do formulário com o SQLite.

## Modelo de dados

`categories (1) ---- (N) transactions`

Cada categoria pode estar associada a vários lançamentos. Uma chave estrangeira composta impede associar uma despesa a uma categoria de receita, ou o contrário.

Os valores financeiros são armazenados em centavos inteiros para evitar erros de precisão de ponto flutuante. Exemplo: R$ 25,90 é armazenado como `2590`.

## Testes

Execute os testes automatizados com:

```bash
py -m unittest -v
```

Os testes utilizam um banco temporário e não alteram os dados de uso do aplicativo.

## Correção de persistência (Etapa 3.1)

O formulário apresenta o tipo do lançamento no campo `type`, enquanto a camada SQLite recebe `transaction_type`. A interface agora converte explicitamente esse campo antes de inserir ou atualizar o registro, evitando falha no salvamento.

## Observações

- A versão atual é destinada ao controle manual de receitas e despesas.
- Não realiza integração bancária, pagamentos ou transferências.
- O banco `financerto.db` contém dados locais do usuário. Não publique esse arquivo em repositórios públicos.
