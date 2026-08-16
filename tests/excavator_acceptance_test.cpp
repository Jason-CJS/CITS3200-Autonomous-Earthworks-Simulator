#include <array>
#include <cmath>
#include <iostream>

#include "chrono/physics/ChBody.h"
#include "chrono/physics/ChSystemNSC.h"
#include "vehicles/excavator/articulation/ExcavatorModel.h"

int main() {
    chrono::ChSystemNSC system;
    system.SetGravitationalAcceleration({0, 0, -9.81});
    system.Add(chrono_types::make_shared<chrono::ChBody>());
    aes::ExcavatorModel excavator(system);

    if (excavator.GetBodyCount() != 8) {
        std::cerr << "Expected 8 excavator bodies, got " << excavator.GetBodyCount() << '\n';
        return 1;
    }
    if (excavator.GetImportedVertexCount() < 1000) {
        std::cerr << "MathScavator9000 base/boom/stick/bucket assets did not load; imported vertex count "
                  << excavator.GetImportedVertexCount() << '\n';
        return 3;
    }

    const auto start = excavator.GetChassisPosition();
    const std::array<double, 4> targets{0.2, 0.3, -0.4, 0.5};
    excavator.SetDriveSpeeds(0.60, 0.90);
    excavator.SetArticulationTargets(targets[0], targets[1], targets[2], targets[3]);

    constexpr double step = 1e-3;
    for (double time = 0; time < 1.0; time += step)
        system.DoStepDynamics(step);

    const double displacement = (excavator.GetChassisPosition() - start).Length();
    if (displacement < 0.5) {
        std::cerr << "Excavator did not move far enough: " << displacement << " m\n";
        return 2;
    }

    const double heading = excavator.GetChassisHeading();
    const double lateral_displacement = std::abs(excavator.GetChassisPosition().y() - start.y());
    if (std::abs(heading) < 0.05 || lateral_displacement < 0.02) {
        std::cerr << "Unequal track commands did not steer the excavator; heading " << heading
                  << " rad, lateral displacement " << lateral_displacement << " m\n";
        return 4;
    }

    const auto actual = excavator.GetJointAngles();
    for (std::size_t i = 0; i < targets.size(); ++i) {
        if (std::abs(actual[i] - targets[i]) > 1e-3) {
            std::cerr << "Joint " << i << " did not reach target; expected " << targets[i] << ", got "
                      << actual[i] << '\n';
            return 5;
        }
    }

    const auto track_angles = excavator.GetTrackAngles();
    if (std::abs(track_angles[0] - track_angles[1]) < 0.1) {
        std::cerr << "Independent track commands did not produce different track motion\n";
        return 6;
    }

    const auto before_stop = excavator.GetChassisPosition();
    const double heading_before_stop = excavator.GetChassisHeading();
    excavator.SetDriveSpeeds(0.0, 0.0);
    system.DoStepDynamics(step);
    if ((excavator.GetChassisPosition() - before_stop).Length() > 1e-3 ||
        std::abs(excavator.GetChassisHeading() - heading_before_stop) > 1e-3) {
        std::cerr << "Stopping the excavator introduced a pose jump\n";
        return 7;
    }

    std::cout << "PASS: loaded " << excavator.GetImportedVertexCount()
              << " MathScavator9000 base/boom/stick/bucket vertices across 8 bodies, moved " << displacement
              << " m, steered to " << heading
              << " rad from independent tracks, and articulated swing/boom/arm/bucket.\n";
    return 0;
}
