"""Frozen and source entry points share the same worker protocol."""

import os
import sys


def main():
    import multiprocessing

    # Frozen resource-tracker children must not start another GUI. On macOS,
    # the worker otherwise waits for that child forever during interpreter exit.
    multiprocessing.freeze_support()
    if len(sys.argv) > 1 and sys.argv[1] == "--worker":
        if os.environ.get("CUEFLOW_DIAGNOSTICS") == "1":
            import faulthandler

            faulthandler.dump_traceback_later(30, repeat=True)
        from cueflow.engine import worker

        return worker(sys.argv[2])
    if len(sys.argv) > 1 and sys.argv[1] == "--sync":
        from cueflow.engine import cli

        return cli(sys.argv[2:])
    if "--self-test-google" in sys.argv:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from cueflow.google_smoke import run

        return run()
    if "--self-test" in sys.argv:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from cueflow.smoke import self_test

        return self_test()
    if sys.platform == "win32" and getattr(sys, "frozen", False):
        import ctypes

        processes = (ctypes.c_ulong * 2)()
        # Hide only our own launch console, never the user's existing terminal.
        if ctypes.windll.kernel32.GetConsoleProcessList(processes, 2) == 1:
            ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)
    from cueflow.app import launch

    return launch()


if __name__ == "__main__":
    raise SystemExit(main())
