class PatchError(RuntimeError):
    """A user-facing failure that leaves the input APK untouched."""


class ReportedPatchError(PatchError):
    """A failure carrying a structured compatibility report for JSON output."""

    def __init__(self, message: str, report: dict):
        super().__init__(message)
        self.report = report


class UnsupportedApkError(PatchError):
    """The APK is recognized, but its required patch targets are unsupported."""


class AmbiguousTargetError(PatchError):
    """More than one plausible patch target was found."""
