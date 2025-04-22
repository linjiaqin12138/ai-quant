# -*- coding: utf-8 -*-
class AppError(Exception):
    """Base class for all exceptions in the app."""
    code: str
    status: int