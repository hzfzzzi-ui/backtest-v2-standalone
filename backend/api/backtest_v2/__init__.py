"""backtest_v2 API package.

Keep package init side-effect free so service imports can depend on compiler and
implementation submodules without triggering the entire router tree.
"""

__all__: list[str] = []
