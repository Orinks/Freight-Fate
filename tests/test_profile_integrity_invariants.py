from freight_fate.profile_integrity_invariants import invariant_data, rendered_invariants


def test_integrity_invariants_include_public_projection_labels():
    data = invariant_data()
    assert data["sourceSaveVersion"] >= 1
    assert data["cityLabels"]["new_york_ny_us"] == "New York, New York"
    assert data["truckLabels"]["rig"] == "standard rig"
    assert data["levelXp"][0] == 0
    assert rendered_invariants().endswith("\n")
