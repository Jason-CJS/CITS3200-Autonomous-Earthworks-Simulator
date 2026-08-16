#include <algorithm>
#include <array>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <memory>
#include <sstream>
#include <string_view>

#include "chrono/physics/ChSystemNSC.h"
#ifdef AES_ENABLE_IRRLICHT
#include "chrono/core/ChDataPath.h"
#include "chrono/core/ChRealtimeStep.h"
#include "chrono_irrlicht/ChVisualSystemIrrlicht.h"
#include "src/KeyboardInput.h"
#endif
#ifdef AES_ENABLE_SCM
#include "chrono/collision/ChCollisionSystem.h"
#include "src/SCMDemoTerrain.h"
#endif
#include "vehicles/excavator/articulation/ExcavatorModel.h"

#ifdef AES_ENABLE_IRRLICHT
namespace {

void PressForSmokeTest(aes::KeyboardInput& keyboard, irr::EKEY_CODE key) {
    irr::SEvent event{};
    event.EventType = irr::EET_KEY_INPUT_EVENT;
    event.KeyInput.Key = key;
    event.KeyInput.PressedDown = true;
    keyboard.OnEvent(event);
}

class ExcavatorKeyboardController {
  public:
    ExcavatorKeyboardController(aes::ExcavatorModel& excavator,
                                aes::KeyboardInput& keyboard,
                                irr::gui::IGUIStaticText* overlay,
                                bool calibration_mode)
        : excavator_(excavator),
          keyboard_(keyboard),
          overlay_(overlay),
          calibration_mode_(calibration_mode),
          targets_(calibration_mode ? std::array<double, 4>{0.0, 0.0, 0.0, 0.0}
                                    : std::array<double, 4>{0.0, 0.25, -0.45, 0.45}) {}

    void Update(double frame_time) {
        const double forward = (keyboard_.IsDown(irr::KEY_KEY_W) ? 1.0 : 0.0) -
                               (keyboard_.IsDown(irr::KEY_KEY_S) ? 1.0 : 0.0);
        const double turn = (keyboard_.IsDown(irr::KEY_KEY_A) ? 1.0 : 0.0) -
                            (keyboard_.IsDown(irr::KEY_KEY_D) ? 1.0 : 0.0);
        double left = 0.75 * forward - 0.50 * turn;
        double right = 0.75 * forward + 0.50 * turn;
        if (keyboard_.IsDown(irr::KEY_SPACE))
            left = right = 0.0;
        if (calibration_mode_)
            left = right = 0.0;
        excavator_.SetDriveSpeeds(std::clamp(left, -1.0, 1.0), std::clamp(right, -1.0, 1.0));

        targets_[0] += Axis(irr::KEY_KEY_Q, irr::KEY_KEY_E) * 0.70 * frame_time;
        targets_[1] += Axis(irr::KEY_KEY_R, irr::KEY_KEY_F) * 0.55 * frame_time;
        targets_[2] += Axis(irr::KEY_KEY_T, irr::KEY_KEY_G) * 0.65 * frame_time;
        targets_[3] += Axis(irr::KEY_KEY_Y, irr::KEY_KEY_H) * 0.85 * frame_time;

        if (keyboard_.IsDown(irr::KEY_KEY_X))
            targets_ = calibration_mode_ ? std::array<double, 4>{0.0, 0.0, 0.0, 0.0}
                                         : std::array<double, 4>{0.0, 0.25, -0.45, 0.45};

        targets_[0] = std::clamp(targets_[0], -1.50, 1.50);
        targets_[1] = std::clamp(targets_[1], -0.70, 0.80);
        targets_[2] = std::clamp(targets_[2], -1.25, 0.80);
        targets_[3] = std::clamp(targets_[3], -1.30, 1.30);
        excavator_.SetArticulationTargets(targets_[0], targets_[1], targets_[2], targets_[3]);

        std::wostringstream text;
        if (calibration_mode_) {
            text << L"VISUAL CALIBRATION MODE\n"
                 << L"Magenta: boom hinge   Green: arm hinge   Cyan: bucket hinge\n"
                 << L"Edit visual_calibration.cfg, save, close this window, then rerun.\n"
                 << L"Change one value at a time; no rebuild is needed.\n\n";
        }
        text << L"EXCAVATOR CONTROLS\n"
             << (calibration_mode_ ? L"Driving disabled while calibrating\n"
                                   : L"W/S drive    A/D steer    Space stop\n")
             << L"Q/E swing    R/F boom     T/G arm\n"
             << L"Y/H bucket   X reset pose\n\n"
             << std::fixed << std::setprecision(2) << L"tracks: " << left << L" / " << right << L" m/s\n"
             << L"swing " << targets_[0] << L"   boom " << targets_[1] << L"\n"
             << L"arm " << targets_[2] << L"   bucket " << targets_[3];
        overlay_->setText(text.str().c_str());
    }

  private:
    double Axis(irr::EKEY_CODE positive, irr::EKEY_CODE negative) const {
        return (keyboard_.IsDown(positive) ? 1.0 : 0.0) - (keyboard_.IsDown(negative) ? 1.0 : 0.0);
    }

    aes::ExcavatorModel& excavator_;
    aes::KeyboardInput& keyboard_;
    irr::gui::IGUIStaticText* overlay_;
    bool calibration_mode_;
    std::array<double, 4> targets_;
};

irr::gui::IGUIStaticText* AddControlOverlay(chrono::irrlicht::ChVisualSystemIrrlicht& visual,
                                            bool calibration_mode) {
    auto* overlay = visual.GetGUIEnvironment()->addStaticText(
        L"", irr::core::rect<irr::s32>(15, 15, calibration_mode ? 650 : 390, calibration_mode ? 285 : 190),
        true, true);
    overlay->setBackgroundColor(irr::video::SColor(205, 245, 240, 220));
    overlay->setOverrideColor(irr::video::SColor(255, 25, 25, 25));
    return overlay;
}

}  // namespace
#endif

int main(int argc, char* argv[]) {
    bool calibration_mode = false;
#ifdef AES_ENABLE_IRRLICHT
    chrono::SetChronoDataPath(CHRONO_DATA_DIR);
    const bool smoke_test = argc > 1 && std::string_view(argv[1]) == "--smoke-test";
    const bool calibration_capture = argc == 3 && std::string_view(argv[1]) == "--capture-calibration";
    const bool capture_image = argc == 3 &&
                               (std::string_view(argv[1]) == "--capture" || calibration_capture);
    calibration_mode = (argc == 2 && std::string_view(argv[1]) == "--calibrate") || calibration_capture;
    if (argc > 1 && !smoke_test && !capture_image && !calibration_mode) {
        std::cerr << "Usage: " << argv[0]
                  << " [--smoke-test | --capture OUTPUT.png | --calibrate | --capture-calibration OUTPUT.png]\n";
        return 2;
    }
#endif

    chrono::ChSystemNSC system;
    system.SetGravitationalAcceleration({0, 0, -9.81});
#ifdef AES_ENABLE_SCM
    system.SetCollisionSystemType(chrono::ChCollisionSystem::Type::BULLET);
    aes::ExcavatorModel excavator(system, calibration_mode, calibration_mode);
    std::unique_ptr<aes::SCMDemoTerrain> terrain;
    if (!calibration_mode)
        terrain = std::make_unique<aes::SCMDemoTerrain>(system);
#else
    aes::ExcavatorModel excavator(system, true, calibration_mode);
#endif
    if (calibration_mode)
        excavator.SetArticulationTargets(0.0, 0.0, 0.0, 0.0);
    else
        excavator.SetArticulationTargets(0.0, 0.25, -0.45, 0.45);

    const auto start = excavator.GetChassisPosition();

#ifdef AES_ENABLE_IRRLICHT
    if (capture_image && !calibration_mode)
        excavator.SetDriveSpeeds(0.45, 0.45);
    else
        excavator.SetDriveSpeeds(0.0, 0.0);

    auto visual = chrono_types::make_shared<chrono::irrlicht::ChVisualSystemIrrlicht>();
    visual->AttachSystem(&system);
    if (smoke_test)
        visual->SetDriverType(irr::video::EDT_NULL);
    visual->SetWindowSize(1280, 720);
    visual->SetWindowTitle("Autonomous Earthworks Simulator - Interactive Excavator");
    visual->SetCameraVertical(chrono::CameraVerticalDir::Z);
    visual->Initialize();
    visual->AddLogo();
    visual->AddSkyBox();
    visual->AddCamera({8.5, -11.0, 6.0}, {1.8, 0, 1.2});
    visual->AddTypicalLights();

    aes::KeyboardInput keyboard;
    std::unique_ptr<ExcavatorKeyboardController> controller;
    if (!capture_image) {
        if (!smoke_test)
            visual->AddUserEventReceiver(&keyboard);
        controller = std::make_unique<ExcavatorKeyboardController>(
            excavator, keyboard, AddControlOverlay(*visual, calibration_mode), calibration_mode);
        if (smoke_test) {
            PressForSmokeTest(keyboard, irr::KEY_KEY_W);
            PressForSmokeTest(keyboard, irr::KEY_KEY_Q);
            PressForSmokeTest(keyboard, irr::KEY_KEY_R);
            PressForSmokeTest(keyboard, irr::KEY_KEY_T);
            PressForSmokeTest(keyboard, irr::KEY_KEY_Y);
        }
        controller->Update(0.0);
    }

    if (smoke_test)
        std::cout << "Running off-screen excavator keyboard, graphics, and SCM smoke test.\n";
    else if (calibration_capture)
        std::cout << "Capturing the source-aligned excavator pose with colored joint markers.\n";
    else if (capture_image)
        std::cout << "Capturing an excavator SCM demonstration frame.\n";
    else if (calibration_mode)
        std::cout << "Excavator visual calibration mode. Edit " << excavator.GetVisualCalibrationPath()
                  << ", then close and rerun; recompiling is not required.\n";
    else
        std::cout << "Interactive 3D excavator running. Use the on-screen keys; close the window to stop.\n";

    constexpr double physics_step = 2e-3;
    constexpr int physics_steps_per_frame = 8;
    constexpr double frame_time = physics_step * physics_steps_per_frame;
    bool scripted_drive_stopped = false;
    chrono::ChRealtimeStepTimer realtime_timer;
    const auto render_frame = [&] {
        if (controller)
            controller->Update(frame_time);

        visual->SetCameraTarget(excavator.GetChassisPosition() + chrono::ChVector3d{1.5, 0.0, 1.2});
        visual->BeginScene();
        visual->Render();
        visual->EndScene();

        for (int substep = 0; substep < physics_steps_per_frame; ++substep)
            system.DoStepDynamics(physics_step);

        if (!controller && !scripted_drive_stopped && system.GetChTime() >= 1.25) {
            excavator.SetDriveSpeeds(0.0, 0.0);
            scripted_drive_stopped = true;
        }
    };

    if (smoke_test || capture_image) {
        const int frames = capture_image ? 100 : 12;
        for (int frame = 0; frame < frames; ++frame)
            render_frame();
        if (capture_image) {
            visual->WriteImageToFile(argv[2]);
            std::cout << "Excavator screenshot written to " << argv[2] << '\n';
        } else {
            std::cout << "Excavator graphics smoke test passed.\n";
        }
    } else {
        while (visual->Run()) {
            render_frame();
            realtime_timer.Spin(frame_time);
        }
    }
#else
    (void)argc;
    (void)argv;
    excavator.SetDriveSpeeds(0.8, 0.8);
    constexpr double step = 1e-3;
    constexpr double duration = 3.0;
    for (double time = 0; time < duration; time += step)
        system.DoStepDynamics(step);
#endif

    const auto finish = excavator.GetChassisPosition();
    const auto joints = excavator.GetJointAngles();
    const auto link_positions = excavator.GetArticulationBodyPositions();
    std::cout << std::fixed << std::setprecision(3)
              << "Excavator loaded with " << excavator.GetBodyCount() << " bodies\n"
              << "Imported MathScavator9000 vertices: " << excavator.GetImportedVertexCount() << '\n'
              << "Chassis displacement: " << (finish - start).Length() << " m\n"
              << "Joint angles [swing boom arm bucket]: " << joints[0] << ' ' << joints[1] << ' '
              << joints[2] << ' ' << joints[3] << '\n';
    if (calibration_mode) {
        std::cout << "Link origins [boom | arm | bucket]: "
                  << link_positions[0].x() << ' ' << link_positions[0].y() << ' ' << link_positions[0].z() << " | "
                  << link_positions[1].x() << ' ' << link_positions[1].y() << ' ' << link_positions[1].z() << " | "
                  << link_positions[2].x() << ' ' << link_positions[2].y() << ' ' << link_positions[2].z() << '\n';
    }
#ifdef AES_ENABLE_SCM
    const auto modified_nodes = terrain ? terrain->GetModifiedNodeCount() : 0;
    std::cout << "SCM modified soil nodes: " << modified_nodes << '\n';
    if (smoke_test && terrain && modified_nodes == 0) {
        std::cerr << "SCM smoke test failed: the excavator did not deform any soil nodes.\n";
        return 3;
    }
    if (smoke_test && ((finish - start).Length() < 0.02 || std::abs(joints[0]) < 0.01)) {
        std::cerr << "Keyboard smoke test failed: drive or articulation input had no measured effect.\n";
        return 4;
    }
#endif
    return 0;
}
