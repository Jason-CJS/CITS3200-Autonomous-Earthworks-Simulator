#pragma once

#include <algorithm>
#include <cmath>
#include <memory>
#include <utility>

#include "chrono/functions/ChFunctionPosition.h"
#include "chrono/functions/ChFunctionRotation.h"

namespace aes::detail {

struct DifferentialDrivePose {
    chrono::ChVector3d position;
    double heading;
};

/// Shared piecewise-constant differential-drive command state.
/// Position is relative to the chassis pose at model construction.
class DifferentialDriveState {
  public:
    explicit DifferentialDriveState(double track_width) : track_width_(track_width) {}

    void SetSpeeds(double time, double left, double right) {
        const auto current = Evaluate(time);
        start_time_ = time;
        start_position_ = current.position;
        start_heading_ = current.heading;
        linear_speed_ = 0.5 * (left + right);
        angular_speed_ = (right - left) / track_width_;
    }

    DifferentialDrivePose Evaluate(double time) const {
        const double elapsed = std::max(0.0, time - start_time_);
        const double heading = start_heading_ + angular_speed_ * elapsed;
        auto position = start_position_;

        if (std::abs(angular_speed_) < 1e-12) {
            position.x() += linear_speed_ * std::cos(start_heading_) * elapsed;
            position.y() += linear_speed_ * std::sin(start_heading_) * elapsed;
        } else {
            const double radius = linear_speed_ / angular_speed_;
            position.x() += radius * (std::sin(heading) - std::sin(start_heading_));
            position.y() -= radius * (std::cos(heading) - std::cos(start_heading_));
        }

        return {position, heading};
    }

    chrono::ChVector3d EvaluateVelocity(double time) const {
        const double heading = Evaluate(time).heading;
        return {linear_speed_ * std::cos(heading), linear_speed_ * std::sin(heading), 0.0};
    }

    chrono::ChVector3d EvaluateAcceleration(double time) const {
        const double heading = Evaluate(time).heading;
        return {-linear_speed_ * angular_speed_ * std::sin(heading),
                linear_speed_ * angular_speed_ * std::cos(heading), 0.0};
    }

    double GetAngularSpeed() const { return angular_speed_; }

  private:
    double track_width_;
    double start_time_ = 0.0;
    chrono::ChVector3d start_position_ = chrono::VNULL;
    double start_heading_ = 0.0;
    double linear_speed_ = 0.0;
    double angular_speed_ = 0.0;
};

class DifferentialDrivePositionFunction : public chrono::ChFunctionPosition {
  public:
    explicit DifferentialDrivePositionFunction(std::shared_ptr<DifferentialDriveState> state)
        : state_(std::move(state)) {}

    DifferentialDrivePositionFunction* Clone() const override {
        return new DifferentialDrivePositionFunction(*this);
    }

    chrono::ChVector3d GetPos(double time) const override { return state_->Evaluate(time).position; }
    chrono::ChVector3d GetLinVel(double time) const override { return state_->EvaluateVelocity(time); }
    chrono::ChVector3d GetLinAcc(double time) const override { return state_->EvaluateAcceleration(time); }

  private:
    std::shared_ptr<DifferentialDriveState> state_;
};

class DifferentialDriveRotationFunction : public chrono::ChFunctionRotation {
  public:
    explicit DifferentialDriveRotationFunction(std::shared_ptr<DifferentialDriveState> state)
        : state_(std::move(state)) {}

    DifferentialDriveRotationFunction* Clone() const override {
        return new DifferentialDriveRotationFunction(*this);
    }

    chrono::ChQuaternion<> GetQuat(double time) const override {
        return chrono::QuatFromAngleZ(state_->Evaluate(time).heading);
    }

    chrono::ChVector3d GetAngVel(double) const override { return {0.0, 0.0, state_->GetAngularSpeed()}; }
    chrono::ChVector3d GetAngAcc(double) const override { return chrono::VNULL; }

  private:
    std::shared_ptr<DifferentialDriveState> state_;
};

}  // namespace aes::detail
