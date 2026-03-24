#!/usr/bin/env python3
"""
Script one-shot: migra senhas plaintext para bcrypt.

Uso:
  python scripts/migrate_senhas.py          # modo real (commit no banco)
  python scripts/migrate_senhas.py --dry-run  # apenas loga, não salva

Pré-requisitos:
  - DATABASE_URL configurada (backend/.env ou env var)
  - Executar APÓS deploy do código com hash_senha disponível
  - Criar snapshot Neon antes: neonctl branch create --name pre-bcrypt-migration
"""
import sys
import os
from pathlib import Path

# Permitir importar app.* sem instalar o pacote
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Carregar .env
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / ".env")
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.barbearia import Barbearia
from app.security import hash_senha, verificar_senha

DRY_RUN = "--dry-run" in sys.argv


def is_already_hashed(senha: str | None) -> bool:
    return bool(senha and senha.startswith("$2b$"))


def main():
    print(f"{'[DRY-RUN] ' if DRY_RUN else ''}Iniciando migração de senhas...")
    db: Session = SessionLocal()
    try:
        barbearias = db.query(Barbearia).all()
        total = len(barbearias)
        migradas = 0
        ignoradas = 0
        erros = 0

        for b in barbearias:
            if not b.senha:
                print(f"  [SKIP] id={b.id} login={b.login} — senha vazia")
                ignoradas += 1
                continue

            if is_already_hashed(b.senha):
                print(f"  [OK]   id={b.id} login={b.login} — já hasheada")
                ignoradas += 1
                continue

            try:
                if not DRY_RUN:
                    b.senha = hash_senha(b.senha)
                    db.commit()
                print(f"  [{'SIMULADO' if DRY_RUN else 'MIGRADO'}] id={b.id} login={b.login}")
                migradas += 1
            except Exception as exc:
                db.rollback()
                print(f"  [ERRO]  id={b.id} login={b.login} — {exc}")
                erros += 1

    finally:
        db.close()

    print(f"\nTotal: {total} | Migradas: {migradas} | Ignoradas: {ignoradas} | Erros: {erros}")
    if erros > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
