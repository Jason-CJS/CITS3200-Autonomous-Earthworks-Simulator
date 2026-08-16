#pragma once

#include <array>
#include <cstddef>
#include <memory>
#include <string>

#include "chrono/core/ChVector3.h"

namespace chrono {
class ChBody;
class ChLinkMotionImposed;
class ChLinkMotorRotationAngle;
class ChLinkMotorRotationSpeed;
class ChSystem;
}

namespace aes {
namespace detail {
class DifferentialDriveState;
}

/// A MathScavator9000 asset-backed excavator control baseline for Chrono.
/// Imported link visuals are driven by deterministic Chrono motor constraints.
class ExcavatorModel {
  public:
    explicit ExcavatorModel(chrono::ChSystem& system,
                            bool show_rigid_ground = true,
                            bool show_calibration_markers = false);

    /// Track commands in m/s. Their average drives forward; their difference steers the chassis.
    void SetDriveSpeeds(double left, double right);

    /// Set cabin swing, boom, arm and bucket angles in radians.
    void SetArticulationTargets(double swing, double boom, double arm, double bucket);

    chrono::ChVector3d GetChassisPosition() const;
    double GetChassisHeading() const;
    std::array<double, 4> GetJointAngles() const;
    std::array<double, 2> GetTrackAngles() const;
    std::array<chrono::ChVector3d, 3> GetArticulationBodyPositions() const;
    std::shared_ptr<chrono::ChBody> GetLeftTrackBody() const;
    std::shared_ptr<chrono::ChBody> GetRightTrackBody() const;
    std::shared_ptr<chrono::ChBody> GetBucketBody() const;
    std::size_t GetBodyCount() const;
    std::size_t GetImportedVertexCount() const;
    const std::string& GetVisualCalibrationPath() const;

  private:
    chrono::ChSystem& system_;
    std::shared_ptr<chrono::ChBody> ground_;
    std::shared_ptr<chrono::ChBody> chassis_;
    std::shared_ptr<chrono::ChBody> cabin_;
    std::shared_ptr<chrono::ChBody> boom_;
    std::shared_ptr<chrono::ChBody> arm_;
    std::shared_ptr<chrono::ChBody> bucket_;
    std::shared_ptr<chrono::ChBody> left_track_;
    std::shared_ptr<chrono::ChBody> right_track_;

    std::shared_ptr<chrono::ChLinkMotionImposed> drive_;
    std::shared_ptr<detail::DifferentialDriveState> drive_state_;
    std::shared_ptr<chrono::ChLinkMotorRotationSpeed> left_track_drive_;
    std::shared_ptr<chrono::ChLinkMotorRotationSpeed> right_track_drive_;
    std::array<std::shared_ptr<chrono::ChLinkMotorRotationAngle>, 4> joints_;
    std::size_t body_count_ = 0;
    std::size_t imported_vertex_count_ = 0;
    std::string visual_calibration_path_;
};

}  // namespace aes
