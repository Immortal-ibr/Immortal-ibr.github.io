"""Inspect VAD metadata retained by a process found in a pool scan."""

from itertools import islice

from volatility3.framework import exceptions, interfaces, renderers
from volatility3.framework.configuration import requirements
from volatility3.plugins.windows import pslist, psscan, vadinfo


class PsScanVad(interfaces.plugins.PluginInterface):
    _required_framework_version = (2, 0, 0)

    @classmethod
    def get_requirements(cls):
        return [
            requirements.ModuleRequirement(
                name="kernel", description="Windows kernel", architectures=["Intel32", "Intel64"]
            ),
            requirements.IntRequirement(name="pid", description="Scanned process ID"),
        ]

    def _generator(self):
        kernel = self.context.modules[self.config["kernel"]]
        selected = psscan.PsScan.scan_processes(
            self.context,
            kernel.layer_name,
            kernel.symbol_table_name,
            filter_func=pslist.PsList.create_pid_filter([self.config["pid"]]),
        )
        for proc in selected:
            try:
                root = proc.get_vad_root()
                root_address = int(root.vol.offset)
                count = 0
                private_count = 0
                file_count = 0
                lowest = None
                highest = None
                for vad in islice(vadinfo.VadInfo.list_vads(proc), 100001):
                    count += 1
                    start = int(vad.get_start())
                    end = int(vad.get_end())
                    lowest = start if lowest is None else min(lowest, start)
                    highest = end if highest is None else max(highest, end)
                    private_count += int(bool(vad.get_private_memory()))
                    file_count += int(bool(vad.get_file_name()))
                status = "OK" if count <= 100000 else "traversal limit"
                yield (0, (int(proc.UniqueProcessId), f"{root_address:#x}", count, private_count, file_count, f"{lowest:#x}" if lowest is not None else "", f"{highest:#x}" if highest is not None else "", status))
            except (exceptions.InvalidAddressException, ValueError, TypeError, AttributeError) as exc:
                yield (0, (int(proc.UniqueProcessId), "", 0, 0, 0, "", "", f"{type(exc).__name__}: {exc}"))

    def run(self):
        return renderers.TreeGrid(
            [("PID", int), ("VAD root", str), ("VADs", int), ("Private", int), ("Files", int), ("Lowest VA", str), ("Highest VA", str), ("Status", str)],
            self._generator(),
        )
