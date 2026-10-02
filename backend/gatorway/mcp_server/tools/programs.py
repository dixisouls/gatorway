from gatorway import catalog_queries as q

from ..deps import Deps


def register(mcp, deps: Deps) -> None:
    @mcp.tool
    def list_programs(query: str = "", level: str = "", limit: int = 20) -> dict:
        """Search SFSU degree programs by title. level is optional: undergraduate, graduate, minor, certificate or credential."""
        with deps.db() as db:
            return {"programs": q.list_programs(db, query, level, limit)}

    @mcp.tool
    def get_program(program_id: int) -> dict:
        """Details of one program."""
        with deps.db() as db:
            return q.program_detail(db, program_id) or {"error": f"program {program_id} not found"}

    @mcp.tool
    def get_roadmaps(program_id: int) -> dict:
        """Roadmaps (plans of study) of a program; the common one has is_default=true."""
        with deps.db() as db:
            return {"roadmaps": q.roadmaps_of(db, program_id)}

    @mcp.tool
    def get_requirements(program_id: int) -> dict:
        """Degree requirement sections of a program: heading, kind (core/elective/ge/other), units, notes and the courses listed."""
        with deps.db() as db:
            return {"sections": q.requirements_of(db, program_id)}
