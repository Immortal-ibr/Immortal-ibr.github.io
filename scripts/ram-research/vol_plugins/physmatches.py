"""Report user-space process mappings of specified physical byte offsets.

This is an attribution diagnostic, not a string carver. An empty result does
not prove the bytes were erased: pages may be unmapped, in cache, or belong to
an exited process that can no longer provide a valid process layer.
"""

from bisect import bisect_left
import json
import sys
from typing import List

from volatility3.framework import exceptions, interfaces, renderers
from volatility3.framework.configuration import requirements
from volatility3.framework.renderers import format_hints
from volatility3.plugins.windows import pslist


USER_LIMIT = 1 << 47


def parse_offsets(value: str) -> list[int]:
    offsets = sorted({int(part.strip(), 0) for part in value.split(",") if part.strip()})
    if not offsets or offsets[0] < 0:
        raise ValueError("Provide one or more nonnegative physical offsets")
    return offsets


class Physmatches(interfaces.plugins.PluginInterface):
    """Find live user-virtual mappings for exact physical offsets."""

    _required_framework_version = (2, 0, 0)

    @classmethod
    def get_requirements(cls) -> List[interfaces.configuration.RequirementInterface]:
        return [
            requirements.ModuleRequirement(
                name="kernel", description="Windows kernel", architectures=["Intel32", "Intel64"]
            ),
            requirements.PluginRequirement(name="pslist", plugin=pslist.PsList, version=(2, 0, 0)),
            requirements.StringRequirement(
                name="offsets", description="Comma-separated physical offsets (decimal or 0x hex)"
            ),
            requirements.IntRequirement(
                name="pid", description="Optional process ID", optional=True
            ),
            requirements.BooleanRequirement(
                name="audit", description="Print process-map coverage to stderr", default=False, optional=True
            ),
        ]

    def _generator(self, processes, offsets: list[int]):
        audited = {"listed": 0, "layer_ready": 0, "with_user_rows": 0,
                   "active_with_user_rows": 0, "exited_with_user_rows": 0,
                   "user_rows": 0, "hit_rows": 0, "unmapped_pids": []}
        for proc in processes:
            audited["listed"] += 1
            pid = -1
            try:
                pid = int(proc.UniqueProcessId)
                name = proc.ImageFileName.cast(
                    "string", max_length=proc.ImageFileName.vol.count, errors="replace"
                )
                status = "exited" if proc.ExitTime.QuadPart else "active"
                layer = self.context.layers[proc.add_process_layer()]
            except (exceptions.InvalidAddressException, ValueError, TypeError):
                audited["unmapped_pids"].append(pid)
                continue
            audited["layer_ready"] += 1
            had_user_row = False

            for virtual, _size, physical, mapped_size, _map_layer in layer.mapping(
                0, USER_LIMIT - 1, ignore_errors=True
            ):
                if virtual >= USER_LIMIT:
                    continue
                if not had_user_row:
                    audited["with_user_rows"] += 1
                    audited[f"{status}_with_user_rows"] += 1
                    had_user_row = True
                audited["user_rows"] += 1
                next_index = bisect_left(offsets, physical)
                while next_index < len(offsets) and offsets[next_index] < physical + mapped_size:
                    target = offsets[next_index]
                    audited["hit_rows"] += 1
                    yield (
                        0,
                        (
                            pid,
                            name,
                            status,
                            format_hints.Hex(target),
                            format_hints.Hex(virtual + target - physical),
                            format_hints.Hex(physical),
                            format_hints.Hex(mapped_size),
                        ),
                    )
                    next_index += 1
        if self.config["audit"]:
            print("Physmatches audit: " + json.dumps(audited, sort_keys=True), file=sys.stderr)

    def run(self):
        offsets = parse_offsets(self.config["offsets"])
        kernel = self.context.modules[self.config["kernel"]]
        filter_func = pslist.PsList.create_pid_filter([self.config.get("pid")])
        return renderers.TreeGrid(
            [
                ("PID", int),
                ("Process", str),
                ("Status", str),
                ("Physical hit", format_hints.Hex),
                ("Virtual hit", format_hints.Hex),
                ("Mapping physical", format_hints.Hex),
                ("Mapping size", format_hints.Hex),
            ],
            self._generator(
                pslist.PsList.list_processes(
                    context=self.context,
                    layer_name=kernel.layer_name,
                    symbol_table=kernel.symbol_table_name,
                    filter_func=filter_func,
                ),
                offsets,
            ),
        )
