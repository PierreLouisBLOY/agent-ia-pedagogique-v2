"""Exact public-source admission, approved by the owner on 5 October 2026.

This admits the documents and their stated scope, not every annotation,
pedagogical production, provider call or release.
"""
OWNER_ADMISSION_SHA256 = "534a0de28e740e18a460ef107add7efe083c0c099ecb76204f30ed5f5fb1a94c"
ADMITTED_DOCUMENTS = {
    "A01": "30b4721c959817d5735143c8ae1819c16e1e8f30822629f2b5594f96099e554f",
    "A02": "0958329b557aacc8db928ee4b6751da1f3b02e8aa507fe3f00b2efad8b09e5c8",
    "A03": "d3a8ffdba6b96080b0866bc2290406ea81c420dff56b042987c9604fdf022fd7",
    "A04B": "7d742bb45c32c38061f48a208bb2c0e983ec098f4551d4749186d672a286856e",
}
DOCUMENT_FRAMES = {
    "A01": frozenset({"1STMG_MAN"}), "A02": frozenset({"1STMG_SGN"}),
    "A03": frozenset({"TSTMG_MSGN_COMMON", "TSTMG_GESTION_FINANCE", "TSTMG_MERCATIQUE", "TSTMG_RHC", "TSTMG_SIG"}),
    "A04B": frozenset({"BTS CG - Annexe I"}),
}
