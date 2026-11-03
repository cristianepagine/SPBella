Migrações de tenant específicas da vertical **salon**.

Fazem parte do MESMO histórico das de `../core` (o `down_revision` de uma pode apontar para a
outra). Para criar uma aqui:

    uv run alembic -n tenant -x schema=t_studio_bella revision --autogenerate \
        --version-path migrations/tenant/spbella -m "descricao"
