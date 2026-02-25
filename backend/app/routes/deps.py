from typing import Annotated

from fastapi import Header, HTTPException


def tenant_id_from_header(
    x_barbearia_id: Annotated[str | None, Header(alias="X-Barbearia-Id")] = None,
) -> int:
    if not x_barbearia_id:
        raise HTTPException(status_code=400, detail="X-Barbearia-Id obrigatorio.")
    try:
        return int(x_barbearia_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="X-Barbearia-Id invalido.") from exc
