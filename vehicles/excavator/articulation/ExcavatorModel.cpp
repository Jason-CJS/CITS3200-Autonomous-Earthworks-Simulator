#include "vehicles/excavator/articulation/ExcavatorModel.h"

#include <cmath>
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>

#include "chrono/assets/ChVisualShapeBox.h"
#include "chrono/assets/ChVisualShapeSphere.h"
#include "chrono/assets/ChVisualShapeTriangleMesh.h"
#include "chrono/functions/ChFunctionConst.h"
#include "chrono/geometry/ChTriangleMeshConnected.h"
#include "chrono/collision/ChCollisionShapeBox.h"
#include "chrono/physics/ChBodyEasy.h"
#include "chrono/physics/ChContactMaterialNSC.h"
#include "chrono/physics/ChLinkMotionImposed.h"
#include "chrono/physics/ChLinkMotorRotationAngle.h"
#include "chrono/physics/ChLinkMotorRotationSpeed.h"
#include "chrono/physics/ChSystem.h"
#include "vehicles/common/DifferentialDriveFunctions.h"

namespace aes {
namespace {

using chrono::ChBody;
using chrono::ChBodyEasyBox;
using chrono::ChColor;
using chrono::ChFrame;
using chrono::ChTriangleMeshConnected;
using chrono::ChVector3d;

constexpr double kMathScavatorScale = 2.8 / 6.24;

struct MeshCalibration {
    ChVector3d translation;
    ChVector3d rotation_degrees;
    double scale = 1.0;
};

std::string AssetPath(const std::string& filename) {
    std::string path = AES_EXCAVATOR_ASSET_DIR;
    if (!path.empty() && path.back() != '/' && path.back() != '\\')
        path += '/';
    return path + filename;
}

std::unordered_map<std::string, MeshCalibration> LoadVisualCalibration(const std::string& path) {
    std::ifstream input(path);
    if (!input)
        throw std::runtime_error("Could not open excavator visual calibration file: " + path);

    std::unordered_map<std::string, MeshCalibration> result;
    std::string line;
    std::size_t line_number = 0;
    while (std::getline(input, line)) {
        ++line_number;
        if (const auto comment = line.find('#'); comment != std::string::npos)
            line.erase(comment);

        std::istringstream values(line);
        std::string part;
        MeshCalibration calibration;
        if (!(values >> part))
            continue;
        if (!(values >> calibration.translation.x() >> calibration.translation.y() >> calibration.translation.z() >>
              calibration.rotation_degrees.x() >> calibration.rotation_degrees.y() >>
              calibration.rotation_degrees.z() >> calibration.scale)) {
            throw std::runtime_error("Invalid excavator visual calibration at " + path + ":" +
                                     std::to_string(line_number));
        }
        std::string unexpected;
        if (values >> unexpected)
            throw std::runtime_error("Unexpected value in excavator visual calibration at " + path + ":" +
                                     std::to_string(line_number));
        if (part != "base" && part != "boom" && part != "arm" && part != "bucket")
            throw std::runtime_error("Unknown excavator part '" + part + "' in " + path + ":" +
                                     std::to_string(line_number));
        if (!std::isfinite(calibration.scale) || calibration.scale <= 0.0)
            throw std::runtime_error("Excavator visual scale must be positive at " + path + ":" +
                                     std::to_string(line_number));
        if (!result.emplace(part, calibration).second)
            throw std::runtime_error("Duplicate excavator part '" + part + "' in " + path);
    }

    for (const std::string part : {"base", "boom", "arm", "bucket"}) {
        if (result.count(part) == 0)
            throw std::runtime_error("Missing excavator part '" + part + "' in " + path);
    }
    return result;
}

ChFrame<> CalibrationFrame(const MeshCalibration& calibration) {
    const auto radians = calibration.rotation_degrees * (chrono::CH_PI / 180.0);
    const auto rotation = chrono::QuatFromAngleZ(radians.z()) * chrono::QuatFromAngleY(radians.y()) *
                          chrono::QuatFromAngleX(radians.x());
    return {calibration.translation, rotation};
}

std::shared_ptr<ChBody> Box(chrono::ChSystem& system,
                            const ChVector3d& size,
                            const ChVector3d& position,
                            const ChColor& color,
                            bool visible = true,
                            bool collidable = false) {
    std::shared_ptr<chrono::ChContactMaterialNSC> material;
    if (collidable) {
        material = chrono_types::make_shared<chrono::ChContactMaterialNSC>();
        material->SetFriction(0.8f);
    }
    auto body = chrono_types::make_shared<ChBodyEasyBox>(size.x(), size.y(), size.z(), 780.0, visible,
                                                         collidable, material);
    body->SetPos(position);
    if (visible)
        body->GetVisualShape(0)->SetColor(color);
    system.Add(body);
    return body;
}

void AddBoxVisual(const std::shared_ptr<ChBody>& body,
                  const ChVector3d& size,
                  const ChVector3d& position,
                  const ChColor& color) {
    auto shape = chrono_types::make_shared<chrono::ChVisualShapeBox>(size.x(), size.y(), size.z());
    shape->SetColor(color);
    body->AddVisualShape(shape, ChFrame<>(position));
}

void StyleExcavatorCab(const std::shared_ptr<ChBody>& cabin) {
    const ChColor glass{0.08f, 0.18f, 0.22f};
    AddBoxVisual(cabin, {0.035, 1.35, 0.72}, {1.01, 0.0, 0.18}, glass);
    AddBoxVisual(cabin, {1.20, 0.035, 0.72}, {0.20, 0.91, 0.18}, glass);
    AddBoxVisual(cabin, {1.20, 0.035, 0.72}, {0.20, -0.91, 0.18}, glass);
    AddBoxVisual(cabin, {2.15, 1.95, 0.12}, {0.0, 0.0, 0.80}, {0.92f, 0.58f, 0.02f});
}

void StyleExcavatorTrack(const std::shared_ptr<ChBody>& chassis, const ChVector3d& center) {
    // Add inexpensive individual grouser plates so the tracks read as tracks
    // even at presentation distance, while retaining a simple collision box.
    AddBoxVisual(chassis, {3.8, 0.55, 0.65}, center, {0.12f, 0.12f, 0.12f});
    constexpr int shoes = 13;
    for (int index = 0; index < shoes; ++index) {
        const double x = -1.72 + 3.44 * index / (shoes - 1);
        AddBoxVisual(chassis, {0.20, 0.60, 0.07}, center + ChVector3d{x, 0.0, -0.36},
                     {0.20f, 0.20f, 0.19f});
        AddBoxVisual(chassis, {0.20, 0.60, 0.07}, center + ChVector3d{x, 0.0, 0.36},
                     {0.20f, 0.20f, 0.19f});
    }
}

void AddTrackCollision(const std::shared_ptr<ChBody>& chassis, const ChVector3d& center) {
    auto material = chrono_types::make_shared<chrono::ChContactMaterialNSC>();
    material->SetFriction(0.8f);
    chassis->AddCollisionShape(
        chrono_types::make_shared<chrono::ChCollisionShapeBox>(material, 3.8, 0.55, 0.72), ChFrame<>(center));
    chassis->EnableCollision(true);
}

void StyleTrackRotor(const std::shared_ptr<ChBody>& rotor) {
    AddBoxVisual(rotor, {0.45, 0.50, 0.45}, {0, 0, 0}, {0.18f, 0.18f, 0.17f});
    AddBoxVisual(rotor, {0.12, 0.58, 0.10}, {0, 0, 0.25}, {0.95f, 0.65f, 0.05f});
}

std::shared_ptr<ChTriangleMeshConnected> LoadMathScavatorMesh(const std::string& filename, double scale) {
    const auto path = AssetPath(filename);
    const auto mesh = ChTriangleMeshConnected::CreateFromSTLFile(path);
    if (!mesh || mesh->GetNumVertices() == 0)
        throw std::runtime_error("Could not load MathScavator9000 vehicle asset: " + path);
    // Chrono 10's Irrlicht triangle-mesh path copies raw vertices and does not
    // apply ChVisualShapeTriangleMesh::SetScale().  Bake the user calibration
    // scale into this private mesh instance so every renderer sees it.
    mesh->Transform(ChVector3d{0, 0, 0}, chrono::ChMatrix33d(scale));
    return mesh;
}

void SetImportedVisual(const std::shared_ptr<ChBody>& body,
                       const std::shared_ptr<ChTriangleMeshConnected>& mesh,
                       const std::string& name,
                       const ChFrame<>& frame,
                       const ChColor& color) {
    body->GetVisualModel()->Clear();
    auto shape = chrono_types::make_shared<chrono::ChVisualShapeTriangleMesh>(mesh, false);
    shape->SetName(name);
    shape->SetColor(color);
    body->AddVisualShape(shape, frame);
}

void AddJointMarker(const std::shared_ptr<ChBody>& body, const ChColor& color) {
    auto marker = chrono_types::make_shared<chrono::ChVisualShapeSphere>(0.16);
    marker->SetColor(color);
    // Put the marker just outside the near face of the link so the imported
    // mesh cannot hide it.  The actual hinge centre is directly behind it.
    body->AddVisualShape(marker, ChFrame<>(ChVector3d{0.0, -0.42, 0.0}));
}

void AddBucketCollision(const std::shared_ptr<ChBody>& bucket) {
    auto material = chrono_types::make_shared<chrono::ChContactMaterialNSC>();
    material->SetFriction(0.8f);
    // Bounding box of stick_bucket_link.STL after the common source-to-simulator rotation and scale.
    bucket->AddCollisionShape(
        chrono_types::make_shared<chrono::ChCollisionShapeBox>(material, 0.88, 0.52, 1.00),
        ChFrame<>(ChVector3d{-0.384, -0.002, 0.044}));
    bucket->EnableCollision(true);
}

std::shared_ptr<chrono::ChLinkMotorRotationAngle> AngleMotor(
    chrono::ChSystem& system,
    const std::shared_ptr<ChBody>& child,
    const std::shared_ptr<ChBody>& parent,
    const ChVector3d& pivot,
    const chrono::ChQuaternion<>& orientation = chrono::QUNIT) {
    auto motor = chrono_types::make_shared<chrono::ChLinkMotorRotationAngle>();
    motor->Initialize(child, parent, ChFrame<>(pivot, orientation));
    motor->SetAngleFunction(chrono_types::make_shared<chrono::ChFunctionConst>(0.0));
    system.Add(motor);
    return motor;
}

}  // namespace

ExcavatorModel::ExcavatorModel(chrono::ChSystem& system,
                               bool show_rigid_ground,
                               bool show_calibration_markers)
    : system_(system), visual_calibration_path_(AssetPath("visual_calibration.cfg")) {
    const auto initial_body_count = system_.GetBodies().size();
    const auto calibration = LoadVisualCalibration(visual_calibration_path_);
    ground_ = Box(system_, {30, 20, 0.1}, {4, 0, -0.05}, {0.38f, 0.30f, 0.18f}, show_rigid_ground);
    ground_->SetFixed(true);

    chassis_ = Box(system_, {3.6, 2.4, 0.45}, {0, 0, 0.75}, {0.22f, 0.22f, 0.20f});
    cabin_ = Box(system_, {2.0, 1.8, 1.5}, {0, 0, 1.75}, {0.95f, 0.65f, 0.05f});
    // Small visible rotors prove independent track commands without rotating the
    // entire track loop as if it were a rigid wheel.
    left_track_ = Box(system_, {0.20, 0.20, 0.20}, {0, 1.35, 0.48}, {0.12f, 0.12f, 0.12f}, false);
    right_track_ = Box(system_, {0.20, 0.20, 0.20}, {0, -1.35, 0.48}, {0.12f, 0.12f, 0.12f}, false);
    StyleTrackRotor(left_track_);
    StyleTrackRotor(right_track_);
    // Use the scaled upstream URDF link origins as the body frames.  This makes
    // every imported mesh origin coincide with its actual Chrono hinge instead
    // of requiring unrelated per-part guesses.
    const ChVector3d boom_pivot{0.75, 0, 2.25};
    const ChVector3d arm_pivot = boom_pivot + ChVector3d{6.24 * kMathScavatorScale, 0, 0};
    const ChVector3d bucket_pivot =
        arm_pivot + ChVector3d{-0.0091425 * kMathScavatorScale, 0, -2.9796 * kMathScavatorScale};
    boom_ = Box(system_, {2.8, 0.35, 0.35}, boom_pivot, {0.95f, 0.65f, 0.05f});
    arm_ = Box(system_, {2.2, 0.30, 0.30}, arm_pivot, {0.95f, 0.65f, 0.05f});
    bucket_ = Box(system_, {0.9, 0.52, 1.0}, bucket_pivot, {0.90f, 0.55f, 0.03f});
    StyleExcavatorCab(cabin_);

    const auto& base_calibration = calibration.at("base");
    const auto& boom_calibration = calibration.at("boom");
    const auto& arm_calibration = calibration.at("arm");
    const auto& bucket_calibration = calibration.at("bucket");
    const auto base_mesh = LoadMathScavatorMesh("base_link.STL", base_calibration.scale);
    const auto boom_mesh = LoadMathScavatorMesh("chassis_boom_link.STL", boom_calibration.scale);
    const auto arm_mesh = LoadMathScavatorMesh("boom_stick_link.STL", arm_calibration.scale);
    const auto bucket_mesh = LoadMathScavatorMesh("stick_bucket_link.STL", bucket_calibration.scale);
    imported_vertex_count_ = base_mesh->GetNumVertices() + boom_mesh->GetNumVertices() +
                             arm_mesh->GetNumVertices() + bucket_mesh->GetNumVertices();

    SetImportedVisual(chassis_, base_mesh, "MathScavator9000 undercarriage",
                      CalibrationFrame(base_calibration),
                      {0.20f, 0.20f, 0.20f});
    SetImportedVisual(boom_, boom_mesh, "MathScavator9000 boom",
                      CalibrationFrame(boom_calibration),
                      {0.95f, 0.65f, 0.05f});
    SetImportedVisual(arm_, arm_mesh, "MathScavator9000 stick",
                      CalibrationFrame(arm_calibration),
                      {0.95f, 0.65f, 0.05f});
    SetImportedVisual(bucket_, bucket_mesh, "MathScavator9000 bucket",
                      CalibrationFrame(bucket_calibration),
                      {0.90f, 0.55f, 0.03f});
    AddBucketCollision(bucket_);
    if (show_calibration_markers) {
        AddJointMarker(boom_, {1.0f, 0.0f, 0.8f});
        AddJointMarker(arm_, {0.1f, 1.0f, 0.1f});
        AddJointMarker(bucket_, {0.0f, 0.9f, 1.0f});
    }
    const ChVector3d left_track_center{0.0, 1.35, -0.27};
    const ChVector3d right_track_center{0.0, -1.35, -0.27};
    StyleExcavatorTrack(chassis_, left_track_center);
    StyleExcavatorTrack(chassis_, right_track_center);
    AddTrackCollision(chassis_, left_track_center);
    AddTrackCollision(chassis_, right_track_center);

    // Impose continuous differential-drive motion from separate left/right track commands.
    drive_state_ = std::make_shared<detail::DifferentialDriveState>(2.7);
    drive_ = chrono_types::make_shared<chrono::ChLinkMotionImposed>();
    drive_->Initialize(chassis_, ground_, ChFrame<>(chassis_->GetPos()));
    drive_->SetPositionFunction(
        chrono_types::make_shared<detail::DifferentialDrivePositionFunction>(drive_state_));
    drive_->SetRotationFunction(
        chrono_types::make_shared<detail::DifferentialDriveRotationFunction>(drive_state_));
    system_.Add(drive_);

    // Swing uses world Z; implement attachment joints as motors so every required DOF is commandable.
    joints_[0] = AngleMotor(system_, cabin_, chassis_, {0, 0, 1.0});
    const auto hinge_y = chrono::QuatFromAngleX(chrono::CH_PI_2);
    joints_[1] = AngleMotor(system_, boom_, cabin_, boom_pivot, hinge_y);
    joints_[2] = AngleMotor(system_, arm_, boom_, arm_pivot, hinge_y);
    joints_[3] = AngleMotor(system_, bucket_, arm_, bucket_pivot, hinge_y);

    left_track_drive_ = chrono_types::make_shared<chrono::ChLinkMotorRotationSpeed>();
    left_track_drive_->Initialize(left_track_, chassis_, ChFrame<>({0, 1.35, 0.48}, hinge_y));
    left_track_drive_->SetSpeedFunction(chrono_types::make_shared<chrono::ChFunctionConst>(0.0));
    system_.Add(left_track_drive_);

    right_track_drive_ = chrono_types::make_shared<chrono::ChLinkMotorRotationSpeed>();
    right_track_drive_->Initialize(right_track_, chassis_, ChFrame<>({0, -1.35, 0.48}, hinge_y));
    right_track_drive_->SetSpeedFunction(chrono_types::make_shared<chrono::ChFunctionConst>(0.0));
    system_.Add(right_track_drive_);

    body_count_ = system_.GetBodies().size() - initial_body_count;
}

void ExcavatorModel::SetDriveSpeeds(double left, double right) {
    drive_state_->SetSpeeds(system_.GetChTime(), left, right);
    left_track_drive_->SetSpeedFunction(chrono_types::make_shared<chrono::ChFunctionConst>(left));
    right_track_drive_->SetSpeedFunction(chrono_types::make_shared<chrono::ChFunctionConst>(right));
}

void ExcavatorModel::SetArticulationTargets(double swing, double boom, double arm, double bucket) {
    const std::array<double, 4> targets{swing, boom, arm, bucket};
    for (std::size_t i = 0; i < joints_.size(); ++i)
        joints_[i]->SetAngleFunction(chrono_types::make_shared<chrono::ChFunctionConst>(targets[i]));
}

chrono::ChVector3d ExcavatorModel::GetChassisPosition() const { return chassis_->GetPos(); }

double ExcavatorModel::GetChassisHeading() const { return chassis_->GetRot().GetCardanAnglesXYZ().z(); }

std::array<double, 4> ExcavatorModel::GetJointAngles() const {
    return {joints_[0]->GetMotorAngle(), joints_[1]->GetMotorAngle(), joints_[2]->GetMotorAngle(),
            joints_[3]->GetMotorAngle()};
}

std::array<double, 2> ExcavatorModel::GetTrackAngles() const {
    return {left_track_drive_->GetMotorAngle(), right_track_drive_->GetMotorAngle()};
}

std::array<chrono::ChVector3d, 3> ExcavatorModel::GetArticulationBodyPositions() const {
    return {boom_->GetPos(), arm_->GetPos(), bucket_->GetPos()};
}

std::shared_ptr<chrono::ChBody> ExcavatorModel::GetLeftTrackBody() const { return chassis_; }

std::shared_ptr<chrono::ChBody> ExcavatorModel::GetRightTrackBody() const { return chassis_; }

std::shared_ptr<chrono::ChBody> ExcavatorModel::GetBucketBody() const { return bucket_; }

std::size_t ExcavatorModel::GetBodyCount() const { return body_count_; }

std::size_t ExcavatorModel::GetImportedVertexCount() const { return imported_vertex_count_; }

const std::string& ExcavatorModel::GetVisualCalibrationPath() const { return visual_calibration_path_; }

}  // namespace aes
