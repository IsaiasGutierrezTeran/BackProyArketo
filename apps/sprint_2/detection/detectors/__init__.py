"""Pluggable detectors behind a single interface."""

from .base import DetectorBase
from .maskrcnn import MaskRCNNDetector
from .mock import MockDetector
from .vision import VisionLLMDetector

__all__ = ["DetectorBase", "MockDetector", "MaskRCNNDetector", "VisionLLMDetector"]
