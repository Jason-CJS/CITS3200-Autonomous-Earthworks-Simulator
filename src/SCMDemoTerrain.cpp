#include "src/SCMDemoTerrain.h"

#include "chrono/assets/ChColormap.h"
#include "chrono/core/ChCoordsys.h"
#include "chrono/physics/ChSystem.h"

namespace aes {

SCMDemoTerrain::SCMDemoTerrain(chrono::ChSystem& system) : terrain_(&system) {
    // Centre a 20 x 12 metre patch slightly ahead of the initial vehicle pose.
    // Its 0.15 m level intersects the bottom of the simplified track collision
    // shapes, making deformation immediately visible in a short demonstration.
    terrain_.SetReferenceFrame(chrono::ChCoordsys<>({4.0, 0.0, 0.15}));
    terrain_.Initialize(20.0, 12.0, 0.10);

    // Soft-soil values adapted from Chrono's official SCM examples.
    terrain_.SetSoilParameters(0.2e6,  // Bekker Kphi [N/m^(n+2)]
                               0.0,    // Bekker Kc [N/m^(n+1)]
                               1.1,    // Bekker exponent
                               0.0,    // Mohr cohesion [Pa]
                               30.0,   // Mohr friction angle [degrees]
                               0.01,   // Janosi shear coefficient [m]
                               4e7,    // Elastic stiffness [Pa/m]
                               3e4);   // Damping [Pa s/m]

    terrain_.EnableBulldozing(true);
    terrain_.SetBulldozingParameters(55.0, 1.0, 3, 4);
    terrain_.SetTestHeight(0.20);
    terrain_.SetPlotType(chrono::vehicle::SCMTerrain::PLOT_SINKAGE, 0.0, 0.16);
    terrain_.SetColormap(chrono::ChColormap::Type::BROWN);
    terrain_.SetMeshWireframe(false);
}

std::size_t SCMDemoTerrain::GetModifiedNodeCount() const {
    return terrain_.GetModifiedNodes(true).size();
}

}  // namespace aes
