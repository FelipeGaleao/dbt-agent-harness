"""Command Line Interface for the Agentic dbt Harness."""

from __future__ import annotations

import argparse
import json
import sys
from typing import List, Optional

from harness.core.config import get_config
from harness.evals.reports import ValidationReporter
from harness.services.factory import build_harness_tool_registry


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(
        prog="harness",
        description="Agentic dbt Development Harness CLI",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # inspect
    subparsers.add_parser("inspect", help="Inspect project structure, layers, and entities")

    # models
    models_p = subparsers.add_parser("models", help="List models")
    models_p.add_argument("--layer", "-l", help="Filter by layer (e.g. trusted, staging, raw)")

    # model
    model_p = subparsers.add_parser("model", help="Inspect single model details")
    model_p.add_argument("name", help="Model name (e.g. dim_aeronaves)")

    # validate
    val_p = subparsers.add_parser("validate", help="Validate and evaluate a model")
    val_p.add_argument("name", help="Model name")
    val_p.add_argument("--layer", "-l", default="trusted", help="Architectural layer")
    val_p.add_argument("--pk", help="Primary key column for uniqueness check")

    # query
    query_p = subparsers.add_parser("query", help="Execute bounded read-only query")
    query_p.add_argument("sql", help="SQL statement (e.g. 'SELECT count(*) FROM trusted.dim_aeronaves')")
    query_p.add_argument("--limit", type=int, default=50, help="Row limit")

    # sessions
    subparsers.add_parser("sessions", help="List persistent multi-turn sessions")

    # guidelines
    subparsers.add_parser("guidelines", help="Print modeling guidelines")

    # delete
    del_p = subparsers.add_parser("delete", help="Delete a model and its associated files")
    del_p.add_argument("name", help="Model name to delete (e.g. dim_fabricantes_aeronaves)")
    del_p.add_argument("--layer", "-l", help="Optional layer filter (trusted, staging, etc.)")
    del_p.add_argument("--yes", "-y", action="store_true", help="Confirm deletion without interactive prompt")

    # agent (ADK Runtime)
    agent_p = subparsers.add_parser("agent", help="Launch interactive session with Google ADK runtime")
    agent_p.add_argument("--session", "-s", default="adk-session-001", help="Session ID")
    agent_p.add_argument("--message", "-m", help="Single instruction to execute (non-interactive)")
    agent_p.add_argument("--model", default="gemini-2.5-flash", help="Gemini model identifier")

    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        sys.exit(0)

    config = get_config()
    registry, services = build_harness_tool_registry(config)

    if args.command == "inspect":
        overview = registry.execute("discover_project")
        print("\n=== dbt Project Overview ===")
        print(f"Project Name:  {overview.get('project_name')}")
        print(f"dbt Version:   {overview.get('dbt_version')}")
        print(f"Total Models:  {overview.get('total_models')}")
        print(f"DuckDB Path:   {overview.get('database_path')}")
        print("\nArchitectural Layers:")
        for layer, m_list in overview.get("layers", {}).items():
            print(f"  • {layer:<10}: {len(m_list)} models ({', '.join(m_list)})")
        print(f"\nDiscovered Entities: {', '.join(overview.get('entities', [])) or 'None'}\n")

    elif args.command == "models":
        models = registry.execute("list_models", layer=args.layer)
        print(f"\nFound {len(models)} models" + (f" in layer '{args.layer}':" if args.layer else ":"))
        for m in models:
            print(f"  [{m['layer']:<8}] {m['name']:<30} ({m['materialized']}) - {m.get('description') or 'No description'}")
        print()

    elif args.command == "model":
        details = registry.execute("get_model_details", model_name=args.name)
        if not details:
            print(f"Error: Model '{args.name}' not found.")
            sys.exit(1)
        lineage = registry.execute("get_model_lineage", model_name=args.name)
        print(f"\n=== Model: {details['name']} ===")
        print(f"Layer:          {details['layer']}")
        print(f"Materialized:   {details['materialized']}")
        print(f"File Path:      {details['path']}")
        print(f"Description:    {details.get('description') or 'None'}")
        print(f"Upstream:       {', '.join(lineage.get('upstream', [])) or 'None'}")
        print(f"Downstream:     {', '.join(lineage.get('downstream', [])) or 'None'}")
        print("\nColumns:")
        for col_name, col in details.get("columns", {}).items():
            tests_str = f" [tests: {', '.join(col.get('tests', []))}]" if col.get("tests") else ""
            desc = f" - {col.get('description')}" if col.get("description") else ""
            print(f"  • {col_name:<30}{tests_str}{desc}")
        print()

    elif args.command == "validate":
        report_data = registry.execute(
            "validate_and_evaluate_model",
            model_name=args.name,
            layer=args.layer,
            primary_key=args.pk,
        )
        from harness.core.contracts import ValidationReport
        report = ValidationReport(**report_data)
        print("\n" + ValidationReporter.format_markdown(report))

    elif args.command == "query":
        try:
            res = registry.execute("query_database", sql=args.sql, limit=args.limit)
            cols = res["columns"]
            rows = res["rows"]
            print(f"\nExecuted in {res['execution_time_seconds']}s ({len(rows)} rows):")
            # Print table
            header = " | ".join(f"{c:<15}" for c in cols)
            print(header)
            print("-" * len(header))
            for r in rows:
                print(" | ".join(f"{str(v):<15}" for v in r))
            print()
        except Exception as e:
            print(f"Query error: {e}")
            sys.exit(1)

    elif args.command == "sessions":
        session_store = services["session_store"]
        sessions = session_store.list_sessions()
        print(f"\nTotal Sessions: {len(sessions)}")
        for s in sessions:
            print(f"  • [{s.session_id}] Status: {s.status.value:<15} Rev: {s.current_revision} Objective: {s.objective}")
        print()

    elif args.command == "guidelines":
        print("\n" + registry.execute("get_guidelines") + "\n")

    elif args.command == "delete":
        if not args.yes:
            conf = input(f"Tem certeza que deseja deletar o modelo '{args.name}'? (s/n): ").strip().lower()
            if conf not in ("s", "sim", "y", "yes"):
                print("Operação cancelada.")
                sys.exit(0)

        changes = registry.execute("delete_model", model_name=args.name, layer=args.layer)
        if not changes:
            print(f"Nenhum arquivo encontrado para o modelo '{args.name}'.")
        else:
            print(f"\nArquivos removidos para o modelo '{args.name}':")
            for c in changes:
                print(f"  ❌ [{c['action']}] {c['path']}")
            print()

    elif args.command == "agent":
        from harness.adapters.adk_runtime import ADKRuntime
        print(f"\n🤖 Inicializando Google ADK Runtime (Sessão: {args.session}, Modelo: {args.model})...")
        runtime = ADKRuntime(session_id=args.session, model=args.model, config=config)
        print("✅ ADK Runtime e ferramentas do dbt carregadas com sucesso.")

        if args.message:
            print(f"\nUser > {args.message}\nAgent > ", end="", flush=True)
            for chunk in runtime.send_message(args.message):
                print(chunk, end="", flush=True)
            print("\n")
        else:
            print("\nModo interativo iniciado. Digite 'sair' ou 'exit' para encerrar.\n")
            while True:
                try:
                    user_input = input("dbt-agent > ").strip()
                    if user_input.lower() in ("exit", "sair", "quit"):
                        print("Encerrando sessão.")
                        break
                    if not user_input:
                        continue
                    print("\nAgent > ", end="", flush=True)
                    for chunk in runtime.send_message(user_input):
                        print(chunk, end="", flush=True)
                    print("\n")
                except (KeyboardInterrupt, EOFError):
                    print("\nSessão interrompida.")
                    break


if __name__ == "__main__":
    main()

