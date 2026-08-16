#pragma once

#include <array>
#include <cstddef>

#include <irrlicht.h>

namespace aes {

/// Minimal press-and-hold keyboard state for the Irrlicht demos.
class KeyboardInput : public irr::IEventReceiver {
  public:
    bool OnEvent(const irr::SEvent& event) override {
        if (event.EventType != irr::EET_KEY_INPUT_EVENT)
            return false;

        const auto key = static_cast<std::size_t>(event.KeyInput.Key);
        if (key < down_.size())
            down_[key] = event.KeyInput.PressedDown;
        return false;
    }

    bool IsDown(irr::EKEY_CODE key) const { return down_[static_cast<std::size_t>(key)]; }

  private:
    std::array<bool, irr::KEY_KEY_CODES_COUNT> down_{};
};

}  // namespace aes
