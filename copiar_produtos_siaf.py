#!/usr/bin/env python3
"""
Cópia em lotes da tabela DSIAF006 entre duas bases SIAFLOJA.FDB.

Objetivo:
- Copiar o cadastro completo dos produtos e o estoque atual (PRO_EST).
- Não copiar notas, vendas, entradas, PDV ou histórico de movimentações.
- Evitar "Out of memory" usando lotes pequenos e commits periódicos.

SEGURANÇA:
- O modo padrão é somente validação (--modo validar).
- Faça backup das bases de origem e destino antes de usar --modo copiar.
- Por padrão, produtos já existentes no destino são preservados.
"""

from __future__ import annotations

import argparse
import getpass
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

try:
    import fdb
except ImportError as exc:
    print(
        "Biblioteca 'fdb' não encontrada.\nInstale com: py -m pip install fdb",
        file=sys.stderr,
    )
    raise SystemExit(2) from exc


TABELA = "DSIAF006"
CHAVE = "PRO_COD"


@dataclass
class Config:
    origem: str
    destino: str
    usuario: str
    senha: str
    charset: str
    lote: int
    modo: str
    confirmar: str


def identificador(nome: str) -> str:
    """Protege nomes de tabelas/campos vindos do catálogo."""
    return '"' + nome.replace('"', '""') + '"'


def conectar(dsn: str, usuario: str, senha: str, charset: str):
    return fdb.connect(
        dsn=dsn,
        user=usuario,
        password=senha,
        charset=charset,
    )


def obter_colunas(conexao, tabela: str) -> list[str]:
    sql = """
        SELECT TRIM(RF.RDB$FIELD_NAME)
        FROM RDB$RELATION_FIELDS RF
        JOIN RDB$FIELDS F
          ON F.RDB$FIELD_NAME = RF.RDB$FIELD_SOURCE
        WHERE RF.RDB$RELATION_NAME = ?
          AND F.RDB$COMPUTED_SOURCE IS NULL
        ORDER BY RF.RDB$FIELD_POSITION
    """
    cursor = conexao.cursor()
    cursor.execute(sql, (tabela.upper(),))
    return [linha[0] for linha in cursor.fetchall()]


def contar(conexao, tabela: str) -> int:
    cursor = conexao.cursor()
    cursor.execute(f"SELECT COUNT(*) FROM {identificador(tabela)}")
    return int(cursor.fetchone()[0])


def existe_campo(colunas: Sequence[str], campo: str) -> bool:
    return campo.upper() in {c.upper() for c in colunas}


def em_lotes(cursor, tamanho: int) -> Iterable[list[tuple]]:
    while True:
        linhas = cursor.fetchmany(tamanho)
        if not linhas:
            return
        yield linhas


def validar_estrutura(origem, destino) -> tuple[list[str], int, int]:
    col_origem = obter_colunas(origem, TABELA)
    col_destino = obter_colunas(destino, TABELA)

    if not col_origem:
        raise RuntimeError(f"A tabela {TABELA} não existe na origem.")
    if not col_destino:
        raise RuntimeError(f"A tabela {TABELA} não existe no destino.")

    destino_set = {c.upper() for c in col_destino}
    colunas_comuns = [c for c in col_origem if c.upper() in destino_set]

    if not existe_campo(colunas_comuns, CHAVE):
        raise RuntimeError(f"O campo-chave {CHAVE} não está disponível nas duas bases.")
    if not existe_campo(colunas_comuns, "PRO_EST"):
        raise RuntimeError("O campo PRO_EST não está disponível nas duas bases.")

    total_origem = contar(origem, TABELA)
    total_destino = contar(destino, TABELA)

    print("\n=== VALIDAÇÃO ===")
    print(f"Tabela: {TABELA}")
    print(f"Colunas na origem: {len(col_origem)}")
    print(f"Colunas no destino: {len(col_destino)}")
    print(f"Colunas compatíveis que serão copiadas: {len(colunas_comuns)}")
    print(f"Produtos na origem: {total_origem}")
    print(f"Produtos no destino antes da operação: {total_destino}")

    somente_origem = [c for c in col_origem if c.upper() not in destino_set]
    if somente_origem:
        print("\nATENÇÃO: campos existentes apenas na origem não serão copiados:")
        print(", ".join(somente_origem))

    return colunas_comuns, total_origem, total_destino


def copiar_produtos(
    origem,
    destino,
    colunas: Sequence[str],
    lote: int,
) -> tuple[int, int, int]:
    """
    Insere somente produtos inexistentes no destino, comparando pelo PRO_COD.
    Produtos já existentes são preservados, inclusive o estoque atual.
    """
    cols_sql = ", ".join(identificador(c) for c in colunas)
    marcadores = ", ".join("?" for _ in colunas)

    select_sql = f"SELECT {cols_sql} FROM {identificador(TABELA)} ORDER BY {identificador(CHAVE)}"

    # Inserção segura: só inclui se o PRO_COD ainda não existir no destino.
    insert_sql = (
        f"INSERT INTO {identificador(TABELA)} ({cols_sql}) "
        f"SELECT {marcadores} FROM RDB$DATABASE "
        f"WHERE NOT EXISTS ("
        f"SELECT 1 FROM {identificador(TABELA)} "
        f"WHERE {identificador(CHAVE)} = ?"
        f")"
    )

    indice_chave = [c.upper() for c in colunas].index(CHAVE)

    cursor_origem = origem.cursor()
    cursor_destino = destino.cursor()
    cursor_origem.execute(select_sql)

    total_lido = 0
    total_antes = contar(destino, TABELA)

    try:
        for numero_lote, linhas in enumerate(em_lotes(cursor_origem, lote), start=1):
            parametros = [tuple(linha) + (linha[indice_chave],) for linha in linhas]
            cursor_destino.executemany(insert_sql, parametros)
            destino.commit()

            total_lido += len(linhas)
            print(
                f"Lote {numero_lote}: {len(linhas)} registros processados "
                f"| total lido: {total_lido}",
                flush=True,
            )
    except Exception:
        destino.rollback()
        raise

    total_depois = contar(destino, TABELA)
    inseridos = total_depois - total_antes
    preservados = total_lido - inseridos
    return total_lido, inseridos, preservados


def ler_argumentos() -> Config:
    parser = argparse.ArgumentParser(
        description="Copia produtos da DSIAF006 entre duas bases SIAF em lotes."
    )
    parser.add_argument(
        "--origem",
        required=True,
        help=r"DSN de origem. Ex.: localhost:C:\SIAF\LOJA1\SIAFLOJA.FDB",
    )
    parser.add_argument(
        "--destino",
        required=True,
        help=r"DSN de destino. Ex.: localhost:C:\SIAF\LOJA2\SIAFLOJA.FDB",
    )
    parser.add_argument("--usuario", default="SYSDBA")
    parser.add_argument("--senha", default=None)
    parser.add_argument(
        "--charset",
        default="WIN1252",
        help="Charset da conexão. Padrão: WIN1252",
    )
    parser.add_argument(
        "--lote",
        type=int,
        default=200,
        help="Quantidade por lote. Padrão seguro: 200",
    )
    parser.add_argument(
        "--modo",
        choices=("validar", "copiar"),
        default="validar",
        help="O padrão 'validar' não altera dados.",
    )
    parser.add_argument(
        "--confirmar",
        default="",
        help="Para copiar, informe exatamente: COPIAR_DSIAF006",
    )

    args = parser.parse_args()

    senha = args.senha
    if senha is None:
        senha = getpass.getpass("Senha do Firebird: ")

    if args.lote < 1 or args.lote > 5000:
        parser.error("--lote deve estar entre 1 e 5000.")

    return Config(
        origem=args.origem,
        destino=args.destino,
        usuario=args.usuario,
        senha=senha,
        charset=args.charset,
        lote=args.lote,
        modo=args.modo,
        confirmar=args.confirmar,
    )


def main() -> int:
    cfg = ler_argumentos()

    if cfg.origem.strip().lower() == cfg.destino.strip().lower():
        print("ERRO: origem e destino não podem ser a mesma base.", file=sys.stderr)
        return 2

    origem = destino = None
    try:
        print("Conectando à base de origem...")
        origem = conectar(cfg.origem, cfg.usuario, cfg.senha, cfg.charset)

        print("Conectando à base de destino...")
        destino = conectar(cfg.destino, cfg.usuario, cfg.senha, cfg.charset)

        colunas, total_origem, total_destino = validar_estrutura(origem, destino)

        if cfg.modo == "validar":
            print("\nNenhum dado foi alterado. Validação concluída.")
            print(
                "\nPara executar após backup:\n"
                "  acrescente --modo copiar --confirmar COPIAR_DSIAF006"
            )
            return 0

        if cfg.confirmar != "COPIAR_DSIAF006":
            print(
                "\nERRO: confirmação de segurança ausente.\nUse: --confirmar COPIAR_DSIAF006",
                file=sys.stderr,
            )
            return 2

        print("\n=== INÍCIO DA CÓPIA ===")
        print(
            "Modo: inserir somente produtos que ainda não existem no destino.\n"
            "Produtos existentes não serão alterados."
        )

        lidos, inseridos, preservados = copiar_produtos(
            origem=origem,
            destino=destino,
            colunas=colunas,
            lote=cfg.lote,
        )

        print("\n=== RESULTADO ===")
        print(f"Registros lidos da origem: {lidos}")
        print(f"Produtos inseridos no destino: {inseridos}")
        print(f"Produtos já existentes e preservados: {preservados}")
        print(f"Total final no destino: {contar(destino, TABELA)}")
        print("\nCópia concluída. Valide os produtos e estoques dentro do SIAF.")
        return 0

    except Exception as exc:
        print(f"\nERRO: {exc}", file=sys.stderr)
        print(
            "Nenhuma nova tentativa deve ser feita antes de verificar o erro e confirmar o backup.",
            file=sys.stderr,
        )
        return 1
    finally:
        if origem is not None:
            origem.close()
        if destino is not None:
            destino.close()


if __name__ == "__main__":
    raise SystemExit(main())
