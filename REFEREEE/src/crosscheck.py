"""
Cross-check referee assignments between the two sources.

Basketbal Vlaanderen (VBL) is the authoritative source: if it has a referee
assigned, that wins. Twizzit only fills in the gap when VBL doesn't have an
assignment yet, and a mismatch is flagged when both sources have an
assignment but disagree (rare, but worth a human look).

Matched on (DT, thuisploeg) — the same fixture can't have two different
home teams starting at the same instant, so that pair is a safe join key
even though neither source shares a common match ID here.
"""
import pandas as pd


def _ref_set(ref1, ref2):
    return {r for r in (ref1, ref2) if isinstance(r, str) and r.strip()}


def cross_check_referees(vbl_calendar: pd.DataFrame, twizzit: pd.DataFrame) -> pd.DataFrame:
    left = vbl_calendar[
        ["wedguid", "DT", "thuisploeg", "tegenstander", "locatie", "reeks", "isHome", "ref1", "ref2"]
    ].rename(columns={"ref1": "vbl_ref1", "ref2": "vbl_ref2"})

    right = twizzit[["DT", "thuisploeg", "tegenstander", "ref1", "ref2"]].rename(
        columns={"tegenstander": "tegenstander_tw", "ref1": "tw_ref1", "ref2": "tw_ref2"}
    )

    merged = left.merge(right, on=["DT", "thuisploeg"], how="outer")

    # tegenstander should agree between sources for a correctly matched fixture;
    # fall back to whichever side has it when one side is missing the row entirely.
    merged["tegenstander"] = merged["tegenstander"].fillna(merged["tegenstander_tw"])
    merged = merged.drop(columns=["tegenstander_tw"])

    def resolve(row):
        vbl_refs = _ref_set(row["vbl_ref1"], row["vbl_ref2"])
        tw_refs = _ref_set(row["tw_ref1"], row["tw_ref2"])

        if vbl_refs:
            source = "VBL"
            final = vbl_refs
        elif tw_refs:
            source = "Twizzit"
            final = tw_refs
        else:
            source = "geen"
            final = set()

        mismatch = bool(vbl_refs) and bool(tw_refs) and vbl_refs != tw_refs

        final = sorted(final)
        return pd.Series(
            {
                "refFinal1": final[0] if len(final) > 0 else "",
                "refFinal2": final[1] if len(final) > 1 else "",
                "refSource": source,
                "refMismatch": mismatch,
            }
        )

    resolved = merged.apply(resolve, axis=1)
    out = pd.concat([merged, resolved], axis=1)
    return out.sort_values("DT").reset_index(drop=True)


if __name__ == "__main__":
    import os

    from . import twizzit_source, vbl_source

    guid = os.environ.get("VBL_CLUB_GUID", "BVBL1037")
    prefix = os.environ.get("VBL_OWN_TEAM_PREFIX", "BBC Haantjes ")

    vbl = vbl_source.get_club_calendar(guid, prefix)
    tw = twizzit_source.load_twizzit_export("data/twizzit_export.csv", prefix)
    result = cross_check_referees(vbl, tw)

    print(f"{len(result)} wedstrijden na cross-check")
    print(f"  bron VBL:     {(result['refSource'] == 'VBL').sum()}")
    print(f"  bron Twizzit: {(result['refSource'] == 'Twizzit').sum()}")
    print(f"  geen ref:     {(result['refSource'] == 'geen').sum()}")
    print(f"  mismatches:   {result['refMismatch'].sum()}")
    if result["refMismatch"].any():
        print(result.loc[result["refMismatch"], ["DT", "thuisploeg", "tegenstander", "vbl_ref1", "vbl_ref2", "tw_ref1", "tw_ref2"]])
