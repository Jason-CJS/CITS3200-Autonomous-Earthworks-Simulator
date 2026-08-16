#pragma once

#include <cstddef>

#include "chrono_vehicle/terrain/SCMTerrain.h"

namespace chrono {
class ChSystem;
}

namespace aes {

/// Small, visibly deformable SCM patch for the interactive vehicle demos.
class SCMDemoTerrain {
  public:
    explicit SCMDemoTerrain(chrono::ChSystem& system);

    std::size_t GetModifiedNodeCount() const;

  private:
    chrono::vehicle::SCMTerrain terrain_;
};

}  // namespace aes
