"""Integration checks for namespace schema boundaries."""

from sqlalchemy import inspect

from tests.conftest import test_engine


async def test_only_agent_definitions_has_namespace_id_column():
    async with test_engine.begin() as conn:
        def _columns(sync_conn, table_name: str) -> set[str]:
            return {col["name"] for col in inspect(sync_conn).get_columns(table_name)}

        agent_cols = await conn.run_sync(_columns, "agent_definitions")
        assert "namespace_id" in agent_cols

        out_of_scope_tables = [
            "mcp_definitions",
            "family_definitions",
            "skill_definitions",
            "workflow_definitions",
            "requests",
            "cases",
            "orchestration_plans",
            "runs",
            "run_nodes",
        ]
        for table_name in out_of_scope_tables:
            table_cols = await conn.run_sync(_columns, table_name)
            assert "namespace_id" not in table_cols


async def test_agent_definitions_namespace_id_index_exists():
    async with test_engine.begin() as conn:
        def _indexes(sync_conn):
            return inspect(sync_conn).get_indexes("agent_definitions")

        indexes = await conn.run_sync(_indexes)
        namespace_indexes = [
            idx for idx in indexes if "namespace_id" in idx.get("column_names", [])
        ]
        assert namespace_indexes
