"""CLI administrativa do SPBella.

    uv run python -m app.cli db init
    uv run python -m app.cli tenants create --slug studio-ana --name "Studio Ana" --country BR \\
        --owner-email ana@exemplo.com --owner-name "Ana"
    uv run python -m app.cli tenants migrate --all
    uv run python -m app.cli tenants list
    uv run python -m app.cli tenants seed-demo
"""

import argparse
import sys

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.provisioning import (
    DEMO_PASSWORD,
    ProvisioningError,
    create_tenant,
    init_database,
    list_tenants,
    migrate_tenants,
    seed_demo,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="spbella", description="Administração do SPBella")
    groups = parser.add_subparsers(dest="group", required=True)

    db = groups.add_parser("db", help="banco principal").add_subparsers(
        dest="command", required=True
    )
    db.add_parser("init", help="cria o papel da aplicação e aplica as migrações do public")

    tenants = groups.add_parser("tenants", help="salões").add_subparsers(
        dest="command", required=True
    )
    create = tenants.add_parser("create", help="cria um salão com o usuário dono")
    create.add_argument("--slug", required=True, help="identificador na URL, ex.: studio-ana")
    create.add_argument("--name", required=True, help="nome do salão")
    create.add_argument("--country", required=True, choices=["BR", "PY"])
    create.add_argument("--owner-email", required=True)
    create.add_argument("--owner-name", required=True)
    create.add_argument(
        "--timezone", help="padrão: America/Sao_Paulo (BR) ou America/Asuncion (PY)"
    )
    create.add_argument("--locale", choices=["pt-BR", "es"], help="padrão: pelo país")
    create.add_argument("--currency", choices=["BRL", "PYG"], help="padrão: pelo país")
    create.add_argument(
        "--dsn-ref", help="variável de ambiente do banco dedicado, ex.: TENANT_DSN_STUDIO_ANA"
    )

    migrate = tenants.add_parser("migrate", help="aplica as migrações nos salões")
    target = migrate.add_mutually_exclusive_group(required=True)
    target.add_argument("--all", action="store_true", help="todos os salões")
    target.add_argument("--slug", action="append", help="um salão (pode repetir)")

    tenants.add_parser("list", help="lista os salões e a versão do banco de cada um")
    tenants.add_parser("seed-demo", help="cria salões de demonstração (fora de produção)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    settings = get_settings()
    configure_logging(settings.log_level)

    try:
        if args.group == "db" and args.command == "init":
            init_database(settings)
            print("Banco principal pronto.")

        elif args.command == "create":
            created = create_tenant(
                settings,
                slug=args.slug,
                name=args.name,
                country=args.country,
                owner_email=args.owner_email,
                owner_name=args.owner_name,
                dsn_ref=args.dsn_ref,
                locale=args.locale,
                timezone=args.timezone,
                currency=args.currency,
            )
            print(f"Salão criado: {created.tenant.slug} (schema {created.tenant.schema})")
            print(f"Acesso do dono: {created.owner_email}")
            print(f"Senha provisória (aparece só agora): {created.owner_password}")

        elif args.command == "migrate":
            results = migrate_tenants(settings, None if args.all else args.slug)
            for r in results:
                status = f"ERRO {r.error}" if r.error else "ok"
                print(f"{r.slug:<30} {r.before or '-'} -> {r.after or '-'}  {status}")
            failed = [r for r in results if r.error]
            print(f"{len(results) - len(failed)} ok, {len(failed)} com erro.")
            return 1 if failed else 0

        elif args.command == "list":
            for t in list_tenants(settings):
                where = t["dsn_ref"] or "principal"
                print(
                    f"{t['slug']:<30} {t['country']}  {t['status']:<12} "
                    f"versão {t['revision'] or '-':<20} banco {where}"
                )

        elif args.command == "seed-demo":
            created = seed_demo(settings)
            for c in created:
                print(f"Demonstração criada: {c.tenant.slug}  login {c.owner_email}")
            if created:
                print(f"Senha de todos os usuários de demonstração: {DEMO_PASSWORD}")
            else:
                print("Os salões de demonstração já existem.")

    except ProvisioningError as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
