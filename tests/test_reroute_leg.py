import reroute_leg as reroute


def test_sampled_route_indices_match_leg_route_point_spacing():
    cumulative_m = [mile * 1609.344 for mile in (0, 10, 20, 30, 40, 50)]

    assert reroute.sampled_route_indices(cumulative_m, 50.0) == [
        (0, 0.0),
        (3, 30.0),
        (5, 50.0),
    ]
