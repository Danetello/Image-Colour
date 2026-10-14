"""
Python version policy and processor detection, used by the install scripts, the CLI and the GUI.

Kept dependency-free and in conservative syntax, so it gives a clear message on an older Python
instead of failing on an import. Run it directly to check the current Python:
exit code 0 = supported, 1 = too old.
"""
import os
import sys

MINIMUM_PYTHON = (3, 12)

# Used when the number of processor threads can't be detected
FALLBACK_THREADS = 4


def formatVersion(version):
    return ".".join(str(part) for part in version)


def pythonSupported():
    return tuple(sys.version_info[:2]) >= MINIMUM_PYTHON


def pythonMessage():
    running = formatVersion(sys.version_info[:2])
    if pythonSupported():
        return "Python %s - supported (minimum %s)." % (running, formatVersion(MINIMUM_PYTHON))
    return "Python %s is too old: this project needs Python %s or newer. Install a newer Python and run the install script again." % (
        running, formatVersion(MINIMUM_PYTHON))


def requireSupportedPython():
    if not pythonSupported():
        sys.exit(pythonMessage())


def detectThreads():
    """
    The number of processor threads this program may use, or None if it can't be determined.
    Respects CPU affinity limits where the OS reports them, so it works on any processor.
    """
    counter = getattr(os, "process_cpu_count", None)  # Python 3.13+
    if counter is not None:
        count = counter()
        if count:
            return count
    if hasattr(os, "sched_getaffinity"):
        try:
            return len(os.sched_getaffinity(0)) or None
        except OSError:
            pass
    return os.cpu_count()


if __name__ == "__main__":
    print(pythonMessage())
    sys.exit(0 if pythonSupported() else 1)
