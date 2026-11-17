"""YAML-based workflow automation for ShortVideoCLI."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from shortvideocli.database import get_session_factory
from shortvideocli.services.projects import create_project
from shortvideocli.services.sources import create_source


def _validate_workflow(data: Any) -> dict:
    """Validate the basic structure of a workflow document."""

    if not isinstance(data, dict):
        raise ValueError("Workflow must contain a YAML mapping.")

    steps = data.get("steps")
    if not isinstance(steps, list) or not steps:
        raise ValueError("Workflow must contain a non-empty 'steps' list.")

    for index, step in enumerate(steps, start=1):
        if not isinstance(step, dict):
            raise ValueError(f"Workflow step {index} must be a mapping.")

        if not isinstance(step.get("action"), str):
            raise ValueError(f"Workflow step {index} needs an action.")

    return data


async def run_workflow_file(path: str | Path) -> list[str]:
    """Execute supported workflow steps in order.

    Supported actions:
      - project.create
      - source.add

    Each service commits its own database operation. If a later step fails,
    earlier successful steps remain saved.
    """

    workflow_path = Path(path).expanduser()

    if not workflow_path.is_file():
        raise ValueError(f"Workflow file does not exist: {workflow_path}")

    try:
        data = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML workflow: {exc}") from exc

    workflow = _validate_workflow(data)
    aliases: dict[str, str] = {}
    results: list[str] = []

    async with get_session_factory()() as session:
        for index, step in enumerate(workflow["steps"], start=1):
            action = step["action"]

            if action == "project.create":
                name = step.get("name")
                if not isinstance(name, str) or not name.strip():
                    raise ValueError(f"Step {index}: project.create requires a name.")

                project = await create_project(
                    session,
                    name=name,
                    description=step.get("description"),
                )

                alias = step.get("id")
                if alias is not None:
                    if not isinstance(alias, str) or not alias.strip():
                        raise ValueError(f"Step {index}: project id must be a non-empty string.")
                    if alias in aliases:
                        raise ValueError(f"Step {index}: duplicate project alias '{alias}'.")
                    aliases[alias] = str(project.id)

                results.append(f"Step {index}: created project '{project.name}' (ID: {project.id})")

            elif action == "source.add":
                project_reference = step.get("project")
                if not isinstance(project_reference, str):
                    raise ValueError(f"Step {index}: source.add requires a project reference.")

                project_id = aliases.get(
                    project_reference,
                    project_reference,
                )

                required_fields = ("platform", "url", "rights_note")
                missing = [
                    field
                    for field in required_fields
                    if not isinstance(step.get(field), str) or not step[field].strip()
                ]
                if missing:
                    raise ValueError(f"Step {index}: source.add is missing: " + ", ".join(missing))

                source = await create_source(
                    session,
                    project_id=project_id,
                    platform=step["platform"],
                    source_url=step["url"],
                    rights_note=step["rights_note"],
                    title=step.get("title"),
                )

                results.append(f"Step {index}: registered source '{source.source_url}'")

            else:
                raise ValueError(f"Step {index}: unsupported action '{action}'.")

    return results
