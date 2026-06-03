"""Pluggable detectors behind a single interface."""

from .base import DetectorBase
from .maskrcnn import MaskRCNNDetector
from .mock import MockDetector

__all__ = ["DetectorBase", "MockDetector", "MaskRCNNDetector"]
