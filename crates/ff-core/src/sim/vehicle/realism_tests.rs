use super::*;

#[test]
fn realism_fuel_changes_gross_without_double_counting_reference_tank() {
    let mut truck = TruckState::default();
    assert!((truck.gross_mass_kg() - truck.specs.mass_kg).abs() < 1e-6);
    let full = truck.gross_mass_kg();
    truck.fuel_gal = 0.0;
    let tank_mass = truck.specs.fuel_tank_gal * DIESEL_KG_PER_GAL;
    assert!((full - truck.gross_mass_kg() - tank_mass).abs() < 1e-6);
    assert!((truck.gross_mass_after_fuel_kg(truck.specs.fuel_tank_gal) - full).abs() < 1e-6);
    truck.refuel(Some(10.0));
    assert!((truck.fuel_mass_kg() - 10.0 * DIESEL_KG_PER_GAL).abs() < 1e-6);
}

#[test]
fn realism_weight_projections_replace_only_the_quantity_being_planned() {
    let truck = TruckState {
        fuel_gal: 40.0,
        cargo_kg: 12_000.0,
        ..Default::default()
    };

    let cargo = 18_000.0;
    let cargo_margin = LEGAL_GVW_KG - (truck.tare_kg() + cargo);
    assert!((truck.gross_weight_margin_with_cargo_kg(cargo) - cargo_margin).abs() < 1e-6);

    let fuel = 90.0;
    let fuel_margin =
        LEGAL_GVW_KG - (truck.dry_tare_kg() + fuel * DIESEL_KG_PER_GAL + truck.cargo_kg);
    assert!((truck.gross_weight_margin_after_fuel_kg(fuel) - fuel_margin).abs() < 1e-6);
}

#[test]
fn realism_refueling_can_cross_legal_limit_without_capping_purchase() {
    let mut truck = TruckState::default();
    truck.fuel_gal = 0.0;
    truck.cargo_kg = LEGAL_GVW_KG - truck.tare_kg() - 5.0 * DIESEL_KG_PER_GAL;
    assert!(!truck.is_over_legal_gvw());
    assert_eq!(truck.refuel(Some(10.0)), 10.0);
    assert!(truck.is_over_legal_gvw());
    assert!(truck.gross_weight_margin_kg() < 0.0);
}

#[test]
fn realism_chosen_braking_matches_force_for_heat_grip_and_load() {
    for (grade, grip, heat, cargo) in [
        (0.0, 1.0, 20.0, 0.0),
        (-0.06, 0.5, 350.0, 25_000.0),
        (0.06, 0.2, 500.0, 21_500.0),
    ] {
        let mut truck = TruckState {
            velocity_mps: 25.0,
            parking_brake: false,
            grade,
            grip,
            brake_temp_c: heat,
            cargo_kg: cargo,
            ..Default::default()
        };
        for (application, pedal, emergency) in [
            (BrakeApplication::Service(0.4), 0.4, false),
            (BrakeApplication::Service(1.0), 1.0, false),
            (BrakeApplication::Emergency, 0.0, true),
        ] {
            truck.brake = pedal;
            truck.emergency_brake = emergency;
            let estimated = truck.braking_decel_mps2(application);
            let delivered = truck.service_brake_force() / truck.gross_mass_kg();
            assert!((estimated - delivered).abs() < 1e-9);
        }
        assert_eq!(
            truck.full_service_decel_mps2(),
            truck.braking_decel_mps2(BrakeApplication::Service(1.0))
        );
        assert!(
            truck.stopping_distance_for_m(None, 1.0, true, BrakeApplication::Emergency)
                < truck.stopping_distance_m(None, 1.0, true)
        );
    }
}

#[test]
fn realism_stopping_estimates_change_with_load_grade_grip_and_heat() {
    let base = TruckState {
        velocity_mps: 29.0,
        parking_brake: false,
        cargo_kg: 0.0,
        ..Default::default()
    };
    let base_stop = base.stopping_distance_m(None, 1.5, true);

    let mut heavy = base.clone();
    heavy.cargo_kg = 30_000.0;
    assert!(heavy.stopping_distance_m(None, 1.5, true) > base_stop);

    let mut downhill = base.clone();
    downhill.grade = -0.06;
    assert!(downhill.stopping_distance_m(None, 1.5, true) > base_stop);

    let mut slick = base.clone();
    slick.grip = 0.4;
    assert!(slick.stopping_distance_m(None, 1.5, true) > base_stop);

    let mut hot = base.clone();
    hot.brake_temp_c = hot.specs.brake_fade_temp_c + 150.0;
    assert!(hot.stopping_distance_m(None, 1.5, true) > base_stop);

    let reaction_only = base.velocity_mps * 1.5;
    assert!(base_stop > reaction_only);
}
