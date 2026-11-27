"""``api:openapi:export``: an application's OpenAPI description, as JSON or YAML."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path  # noqa: TC003 — read at runtime: the console converts --output from it
from typing import TYPE_CHECKING, Annotated, Final, Literal, cast, final, override

from xtr_console import ConsoleStyle, ExitCode, Option, as_command, escape

from xtr_http_kernel.exception import InvalidArgumentError

# Imported under another name: the command's own --filter-tags parameter takes this one.
from ._open_api_document import JsonValue, for_api_gateway
from ._open_api_document import filter_tags as tagged_only
from .router_command import RouterCommand

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = ["OpenApiExportCommand"]

_NO_YAML: Final = (
    "YAML needs the PyYAML package: install it with `uv add pyyaml`, or install this "
    'package with its yaml extra, `uv add "xtr-http-kernel[yaml]"`.'
)
_NO_OPENAPI_2: Final = (
    "OpenAPI 2 is not supported: the application describes itself in OpenAPI 3; "
    "leave --spec-version out, or pass 3."
)


@as_command("api:openapi:export")
@final
class OpenApiExportCommand(RouterCommand):
    """Exports the OpenAPI description of an application."""

    __slots__ = ()

    async def __call__(  # noqa: PLR0913, PLR0911 — the command line of the command; one exit per refusal
        self,
        io: ConsoleStyle,
        *,
        app: str | None = None,
        yaml: Annotated[bool, Option(alias="-y")] = False,
        output: Annotated[Path | None, Option(alias="-o")] = None,
        spec_version: Literal["2", "3"] = "3",
        api_gateway: bool = False,
        filter_tags: list[str] | None = None,
    ) -> int:
        """Dump the OpenAPI documentation.

        The description is the one the application serves, every route its
        routes files include among it; nothing is served to build it.

        Args:
            io: Where the command writes.
            app: The application to describe, as ``package.module:app``; the
                configured one when left out.
            yaml: Dump the documentation in YAML.
            output: Write output to file.
            spec_version: OpenAPI version to use; only 3 is produced.
            api_gateway: Enable the Amazon API Gateway compatibility mode.
            filter_tags: Keep only the operations tagged with this tag; repeat
                for several.
        """
        if spec_version == "2":
            io.error(_NO_OPENAPI_2)
            return ExitCode.INVALID
        dump = _yaml_dumper() if yaml else _json
        if dump is None:
            io.warning(escape(_NO_YAML))
            return ExitCode.FAILURE
        application = self._app_or_report(io, app)
        if application is None:
            return ExitCode.INVALID
        # The framework types its description loosely; it is a JSON document.
        document: dict[str, JsonValue] = application.openapi()
        if filter_tags:
            document = tagged_only(document, filter_tags)
        if api_gateway:
            try:
                document = for_api_gateway(document)
            except InvalidArgumentError as error:
                io.error(escape(str(error)))
                return ExitCode.FAILURE
        text = dump(document)
        if output is None:
            # As it is: neither wrapped to the terminal nor read as markup.
            io.console.print(
                text, end="", markup=False, highlight=False, emoji=False, soft_wrap=True
            )
            return ExitCode.SUCCESS
        try:
            _ = await asyncio.to_thread(output.write_text, text, encoding="utf-8")
        except OSError as error:
            io.error(escape(f'Cannot write "{output}": {error.strerror or error}.'))
            return ExitCode.FAILURE
        io.success(escape(f'Data written to "{output}".'))
        return ExitCode.SUCCESS


def _json(document: dict[str, JsonValue]) -> str:
    return json.dumps(document, indent=2, ensure_ascii=False) + "\n"


def _yaml_dumper() -> Callable[[dict[str, JsonValue]], str] | None:
    """Return what writes a description as YAML, or ``None`` when PyYAML is not installed."""
    try:
        # Optional: installed with the yaml extra.
        import yaml  # noqa: PLC0415
    except ImportError:
        return None

    class _Dumper(yaml.SafeDumper):
        """Writes a value met twice in full, never as an anchor and an alias."""

        @override
        def ignore_aliases(self, data: object) -> bool:
            return True

    # The stubs leave the keyword arguments of ``dump`` untyped; these are its own.
    dump_yaml = cast("Callable[..., str]", yaml.dump)

    def dump(document: dict[str, JsonValue]) -> str:
        return dump_yaml(document, Dumper=_Dumper, sort_keys=False, allow_unicode=True)

    return dump
