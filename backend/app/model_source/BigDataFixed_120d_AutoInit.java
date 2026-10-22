/*
 * BigDataFixed_120d_ConservedMethaneStable.java
 *
 * Long-time convergence-oriented COMSOL 5.6 model.
 *
 * Main correction relative to the methane-fraction version:
 * 1) Do not solve methane fraction y directly. The long-time y equation contains
 *    qp/q and a nonconservative gradient product, which becomes ill-conditioned
 *    after long drainage and was the likely cause of failure at the final time.
 * 2) Solve three dimensionless conserved variables instead:
 *       q     = total fracture pressure / Pscale
 *       zch4  = fracture methane partial pressure / Pscale
 *       qp    = matrix methane pressure / Pscale
 *    Methane concentration is only a postprocessed ratio zch4/q.
 * 3) The borehole prescribes total pressure only; methane uses natural outflow.
 *    The roadway prescribes total pressure and methane partial pressure.
 * 4) Use one continuous 0-120 d solve with adaptive first-order BDF,
 *    damped fully coupled Newton, and a direct linear solver. The former
 *    0.005 d maximum step forced at least 24000 steps and made the 3-D run
 *    practically impossible to finish; the boundary ramp is resolved finely
 *    at the beginning and the later solution is allowed to take 1 d steps.
 *
 * IMPORTANT: boundary IDs are inherited from the original exported model.
 * Verify borehole and roadway boundary selections in COMSOL before trusting results.
 */

import com.comsol.model.*;
import com.comsol.model.util.*;
public class BigDataFixed_120d_AutoInit {

  private static void setTimeControls(Model model, String solTag, String maxStep,
                                      String initialStep, int maxOrder, double rtol) {
    model.sol(solTag).feature("t1").set("timemethod", "bdf");
    model.sol(solTag).feature("t1").set("maxorder", maxOrder);
    model.sol(solTag).feature("t1").set("rtol", rtol);
    model.sol(solTag).feature("t1").feature("aDef").set("cachepattern", false);
    try {
      model.sol(solTag).feature("t1").set("initialstepbdf", initialStep);
      model.sol(solTag).feature("t1").set("maxstepconstraintbdf", "const");
      model.sol(solTag).feature("t1").set("maxstepbdf", maxStep);
      // Initial values and boundary values are constructed to be consistent.
      // Use a consistent initialization because all three conserved variables are solved together.
      model.sol(solTag).feature("t1").set("consistent", "on");
    } catch (Exception ex) {
      System.out.println("Some BDF options are unavailable in this COMSOL 5.6 build; defaults are retained.");
    }
  }

  private static void addGasFullyCoupledSolver(Model model, String solTag) {
    model.sol(solTag).feature("t1").create("d1", "Direct");
    model.sol(solTag).feature("t1").feature("d1").set("linsolver", "pardiso");
    model.sol(solTag).feature("t1").feature("d1").set("pivotperturb", 1.0e-8);

    try {
      model.sol(solTag).feature("t1").feature("fcDef").set("linsolver", "d1");
      model.sol(solTag).feature("t1").feature("fcDef").set("dtech", "const");
      model.sol(solTag).feature("t1").feature("fcDef").set("damp", 0.55);
      model.sol(solTag).feature("t1").feature("fcDef").set("maxiter", 30);
    } catch (Exception ex) {
      System.out.println("Some fully coupled damping options are unavailable; COMSOL defaults are retained.");
    }
  }

  public static Model run() {
    Model model = ModelUtil.create("Model");
    model.modelPath("D:\\COMSOL56");
    model.label("BigDataFixed_120d_AutoInit.mph");

    // ------------------------------------------------------------------
    // Parameters
    // ------------------------------------------------------------------
    model.param().set("Lx", "40[m]");
    model.param().set("Ly", "105[m]");
    model.param().set("Lz", "15[m]");
    model.param().set("road_w", "5[m]");
    model.param().set("rbh", "0.048[m]");
    model.param().set("dbh", "0.096[m]");
    model.param().set("Sbh", "5[m]");

    model.param().set("Ecoal", "2.63[GPa]");
    model.param().set("Ep", "4.5[GPa]");
    model.param().set("nu1", "0.32");
    model.param().set("rho_c", "1300[kg/m^3]");
    model.param().set("sigma_top", "19.5[MPa]");

    model.param().set("aL", "20[m^3]/(1000[kg])");
    model.param().set("bL", "3[1/MPa]");
    model.param().set("phi_f0", "0.05");
    model.param().set("phi_p0", "0.06");
    model.param().set("kf0", "4.68e-17[m^2]");
    model.param().set("D0", "5.48e-12[m^2/s]");
    model.param().set("Lfrac", "0.005[m]");
    model.param().set("lambdaD", "0[1/s]");
    model.param().set("mu_gas", "1.08e-5[Pa*s]");

    model.param().set("Mch4", "0.016[kg/mol]");
    model.param().set("Mair", "0.029[kg/mol]");
    model.param().set("Rgas", "8.314[J/(mol*K)]");
    model.param().set("T0", "293.15[K]");
    model.param().set("Vm", "0.0224[m^3/mol]");

    model.param().set("Patm", "101325[Pa]");
    model.param().set("pf10", "1.527[MPa]");
    model.param().set("Pneg", "20[kPa]");
    model.param().set("Pbh", "Patm-Pneg");

    model.param().set("Pscale", "1[MPa]");
    model.param().set("pmin", "1000[Pa]");
    model.param().set("pf2_init", "pmin");
    model.param().set("qfloor", "pmin/Pscale");
    model.param().set("epsZ", "1e-8");

    model.param().set("KY", "3*(1-2*nu1)/Ecoal");
    model.param().set("tau_bc", "0.5[d]");

    // Small numerical diffusion for the methane partial-pressure equation.
    // It suppresses coarse-mesh oscillations while only smoothing over a short local length scale.
    model.param().set("Dart", "5e-8[m^2/s]");

    final String gasTimes = "range(0,0.01,0.1) range(0.2,0.1,2) range(3,1,120)";

    // ------------------------------------------------------------------
    // Component, geometry, and mesh
    // ------------------------------------------------------------------
    model.component().create("comp1", true);
    model.component("comp1").geom().create("geom1", 3);
    model.component("comp1").mesh().create("mesh1");

    model.component("comp1").geom("geom1").create("blk1", "Block");
    model.component("comp1").geom("geom1").feature("blk1")
         .set("size", new int[]{105, 40, 15});

    for (int i = 1; i <= 5; i++) {
      String tag = "cyl" + i;
      model.component("comp1").geom("geom1").create(tag, "Cylinder");
      model.component("comp1").geom("geom1").feature(tag)
           .set("pos", new double[]{0, 20.0 + 5.0 * (i - 3), 7.5});
      model.component("comp1").geom("geom1").feature(tag).set("rot", 90);
      model.component("comp1").geom("geom1").feature(tag)
           .set("axis", new int[]{1, 0, 0});
      model.component("comp1").geom("geom1").feature(tag).set("r", 0.048);
      model.component("comp1").geom("geom1").feature(tag).set("h", 80);
    }
    model.component("comp1").geom("geom1").run();

    // ------------------------------------------------------------------
    // Variables and reconstructed physical quantities
    // ------------------------------------------------------------------
    model.component("comp1").variable().create("var2");

    // Conserved unknowns: q (total fracture pressure), zch4 (methane partial pressure),
    // and qp (matrix methane pressure), all divided by Pscale.
    model.component("comp1").variable("var2").set("q0", "(pf10+pf2_init)/Pscale");
    model.component("comp1").variable("var2").set("z0", "pf10/Pscale");

    // Smooth positive regularization. It is only active if Newton temporarily proposes
    // a slightly negative pressure during an iteration.
    model.component("comp1").variable("var2").set(
        "qsafe", "0.5*(q+qfloor+sqrt((q-qfloor)^2+(0.1*qfloor)^2))");
    model.component("comp1").variable("var2").set(
        "zpos", "0.5*(zch4+sqrt(zch4^2+epsZ^2))");

    // A smooth min(zpos, qsafe) is used for physical postprocessing and source terms.
    // The solved variable remains zch4, so no hard inequality projection is introduced.
    model.component("comp1").variable("var2").set(
        "zsafe", "0.5*(zpos+qsafe-sqrt((zpos-qsafe)^2+epsZ^2))");

    model.component("comp1").variable("var2").set("pf", "Pscale*qsafe");
    model.component("comp1").variable("var2").set("pf1", "Pscale*zsafe");
    model.component("comp1").variable("var2").set("pf2", "Pscale*(qsafe-zsafe)");
    model.component("comp1").variable("var2").set("pp", "Pscale*qp");

    model.component("comp1").variable("var2").set("epsv", "0");
    model.component("comp1").variable("var2").set("alpha_f", "1-Ecoal/Ep");
    model.component("comp1").variable("var2").set(
        "alpha_p", "Ecoal/Ep*3*phi_p0*(1-nu1)/(2*(1-2*nu1))");
    model.component("comp1").variable("var2").set("sigma_a", "0[Pa]");
    model.component("comp1").variable("var2").set(
        "peff", "alpha_f*pf+alpha_p*pp+sigma_a");

    model.component("comp1").variable("var2").set("Dt", "D0*exp(-lambdaD*t)");
    model.component("comp1").variable("var2").set("phif", "phi_f0");
    model.component("comp1").variable("var2").set("phip", "phi_p0");
    model.component("comp1").variable("var2").set("kf", "kf0");
    model.component("comp1").variable("var2").set(
        "Sx", "3*pi^2*Dt*(1-phif)/Lfrac^2");

    // Normalized matrix-pressure ODE source. pf1 is reconstructed from zsafe.
    model.component("comp1").variable("var2").set(
        "dqpdt",
        "-3*pi^2*Vm*(1+bL*pp)^2*(pp-pf1)*Dt/"
        + "(Pscale*Lfrac^2*(aL*bL*rho_c*Rgas*T0+phip*Vm*(1+bL*pp)^2))");

    // Zero-slope ramp: both the value and first derivative match the initial state.
    model.component("comp1").variable("var2").set(
        "ramp_bc", "1-exp(-(t/tau_bc)^2)");
    model.component("comp1").variable("var2").set(
        "qbh", "q0+((Patm-Pneg)/Pscale-q0)*ramp_bc");
    model.component("comp1").variable("var2").set(
        "qroad", "q0+(Patm/Pscale-q0)*ramp_bc");
    model.component("comp1").variable("var2").set(
        "zroad", "z0+(pmin/Pscale-z0)*ramp_bc");

    model.component("comp1").variable("var2").set("pf1M", "pf1/1e6");
    model.component("comp1").variable("var2").set("pf2M", "pf2/1e6");
    model.component("comp1").variable("var2").set("ppM", "pp/1e6");
    model.component("comp1").variable("var2").set("Cch4", "zsafe/qsafe");
    model.component("comp1").variable("var2").set("Cch4_pct", "100*zsafe/qsafe");

    // ------------------------------------------------------------------
    // Material and solid mechanics
    // ------------------------------------------------------------------
    model.component("comp1").material().create("mat1", "Common");
    model.component("comp1").material("mat1").propertyGroup("def")
         .set("density", "rho_c");
    model.component("comp1").material("mat1").propertyGroup("def")
         .set("poissonsratio", "nu1");
    model.component("comp1").material("mat1").propertyGroup("def")
         .set("youngsmodulus", "Ecoal");

    model.component("comp1").physics().create("solid", "SolidMechanics", "geom1");
    model.component("comp1").physics("solid").selection().set(1);
    model.component("comp1").physics("solid").create("bndl1", "BoundaryLoad", 2);
    model.component("comp1").physics("solid").feature("bndl1").selection().set(4);
    model.component("comp1").physics("solid").feature("bndl1")
         .set("LoadType", "FollowerPressure");
    model.component("comp1").physics("solid").feature("bndl1")
         .set("FollowerPressure", "sigma_top");

    model.component("comp1").physics("solid").create("disp1", "Displacement2", 2);
    model.component("comp1").physics("solid").feature("disp1").selection().set(3);
    model.component("comp1").physics("solid").feature("disp1")
         .set("Direction", new int[][]{{0}, {0}, {1}});

    model.component("comp1").physics("solid").create("disp2", "Displacement2", 2);
    model.component("comp1").physics("solid").feature("disp2").selection().set(2, 30);
    model.component("comp1").physics("solid").feature("disp2")
         .set("Direction", new int[][]{{0}, {1}, {0}});

    model.component("comp1").physics("solid").create("disp3", "Displacement2", 2);
    model.component("comp1").physics("solid").feature("disp3").selection().set(1, 36);
    model.component("comp1").physics("solid").feature("disp3")
         .set("Direction", new int[][]{{1}, {0}, {0}});

    // ------------------------------------------------------------------
    // PDE 1: normalized fracture total pressure q
    // ------------------------------------------------------------------
    model.component("comp1").physics().create("gp", "GeneralFormPDE", "geom1");
    model.component("comp1").physics("gp").field("dimensionless")
         .component(new String[]{"q"});
    model.component("comp1").physics("gp").selection().set(1);
    model.component("comp1").physics("gp").prop("Units")
         .set("CustomSourceTermUnit", "1/s");
    model.component("comp1").physics("gp").feature("gfeq1")
         .set("f", "Sx*(qp-zsafe)");
    model.component("comp1").physics("gp").feature("gfeq1").set(
        "Ga", new String[][]{{
          "-kf/mu_gas*Pscale*qsafe*d(q,x)",
          "-kf/mu_gas*Pscale*qsafe*d(q,y)",
          "-kf/mu_gas*Pscale*qsafe*d(q,z)"
        }});
    model.component("comp1").physics("gp").feature("gfeq1").set("da", "phif");
    model.component("comp1").physics("gp").feature("init1").set("q", "q0");

    model.component("comp1").physics("gp").create("dir1", "DirichletBoundary", 2);
    model.component("comp1").physics("gp").feature("dir1").selection().set(
        6, 7, 8, 9, 11, 12, 13, 14, 16, 17,
        18, 19, 21, 22, 23, 24, 26, 27, 28, 29);
    model.component("comp1").physics("gp").feature("dir1").set("r", "qbh");

    model.component("comp1").physics("gp").create("dir2", "DirichletBoundary", 2);
    model.component("comp1").physics("gp").feature("dir2").selection().set(1);
    model.component("comp1").physics("gp").feature("dir2").set("r", "qroad");

    // ------------------------------------------------------------------
    // PDE 2: normalized fracture methane partial pressure zch4
    // Boreholes use natural outflow; only the roadway prescribes methane pressure.
    // ------------------------------------------------------------------
    model.component("comp1").physics().create("gz", "GeneralFormPDE", "geom1");
    model.component("comp1").physics("gz").field("dimensionless")
         .component(new String[]{"zch4"});
    model.component("comp1").physics("gz").selection().set(1);
    model.component("comp1").physics("gz").prop("Units")
         .set("CustomSourceTermUnit", "1/s");
    model.component("comp1").physics("gz").feature("gfeq1").set(
        "f", "Sx*(qp-zsafe)");
    model.component("comp1").physics("gz").feature("gfeq1").set(
        "Ga", new String[][]{{
          "-kf/mu_gas*Pscale*zsafe*d(q,x)-Dart*d(zch4,x)",
          "-kf/mu_gas*Pscale*zsafe*d(q,y)-Dart*d(zch4,y)",
          "-kf/mu_gas*Pscale*zsafe*d(q,z)-Dart*d(zch4,z)"
        }});
    model.component("comp1").physics("gz").feature("gfeq1").set("da", "phif");
    model.component("comp1").physics("gz").feature("init1").set("zch4", "z0");

    model.component("comp1").physics("gz").create("dir1", "DirichletBoundary", 2);
    model.component("comp1").physics("gz").feature("dir1").selection().set(1);
    model.component("comp1").physics("gz").feature("dir1").set("r", "zroad");

    // ------------------------------------------------------------------
    // PDE 3: normalized matrix methane pressure qp with zero spatial flux
    // ------------------------------------------------------------------
    model.component("comp1").physics().create("gm", "GeneralFormPDE", "geom1");
    model.component("comp1").physics("gm").field("dimensionless")
         .component(new String[]{"qp"});
    model.component("comp1").physics("gm").selection().set(1);
    model.component("comp1").physics("gm").prop("Units")
         .set("CustomSourceTermUnit", "1/s");
    model.component("comp1").physics("gm").feature("gfeq1").set("f", "dqpdt");
    model.component("comp1").physics("gm").feature("gfeq1").set(
        "Ga", new String[][]{{"0", "0", "0"}});
    model.component("comp1").physics("gm").feature("gfeq1").set("da", "1");
    model.component("comp1").physics("gm").feature("init1").set("qp", "pf10/Pscale");

    try {
      model.component("comp1").physics("gp").prop("ShapeProperty").set("order", "1");
      model.component("comp1").physics("gz").prop("ShapeProperty").set("order", "1");
      model.component("comp1").physics("gm").prop("ShapeProperty").set("order", "1");
      model.component("comp1").physics("solid").prop("ShapeProperty")
           .set("order_displacement", "1");
    } catch (Exception ex) {
      System.out.println("One or more first-order settings were not accepted; COMSOL defaults are used.");
    }

    // ------------------------------------------------------------------
    // Mesh
    // ------------------------------------------------------------------
    model.component("comp1").mesh("mesh1").create("ftet1", "FreeTet");
    model.component("comp1").mesh("mesh1").feature("ftet1").selection()
         .geom("geom1", 3);
    model.component("comp1").mesh("mesh1").feature("ftet1").selection().set(1);

    model.component("comp1").mesh("mesh1").feature("ftet1").create("size1", "Size");
    model.component("comp1").mesh("mesh1").feature("ftet1").feature("size1")
         .selection().geom("geom1", 2);
    model.component("comp1").mesh("mesh1").feature("ftet1").feature("size1")
         .selection().set(
             6, 7, 8, 9, 11, 12, 13, 14, 16, 17,
             18, 19, 21, 22, 23, 24, 26, 27, 28, 29);
    model.component("comp1").mesh("mesh1").feature("ftet1").feature("size1")
         .set("custom", "on");
    model.component("comp1").mesh("mesh1").feature("ftet1").feature("size1")
         .set("hmax", "2.5[m]");
    model.component("comp1").mesh("mesh1").feature("ftet1").feature("size1")
         .set("hmin", "0.04[m]");
    model.component("comp1").mesh("mesh1").feature("ftet1").feature("size1")
         .set("hgrad", 2.5);

    model.component("comp1").mesh("mesh1").feature("size").set("hauto", 9);
    model.component("comp1").mesh("mesh1").feature("size").set("custom", "on");
    model.component("comp1").mesh("mesh1").feature("size").set("hmax", "10[m]");
    model.component("comp1").mesh("mesh1").feature("size").set("hmin", "0.25[m]");
    model.component("comp1").mesh("mesh1").feature("size").set("hgrad", 3.0);
    model.component("comp1").mesh("mesh1").run();

    // ------------------------------------------------------------------
    // Study 1: automatic stationary initialization at the physical t = 0 state
    //
    // IMPORTANT DESIGN:
    //   - This initialization solves ALL dependent variables once:
    //       u, v, w, q, zch4, qp
    //   - The gas ramp satisfies ramp_bc(0)=0, so q=q0, zch4=z0, qp=z0
    //     is an exact uniform gas equilibrium at t=0.
    //   - Solid Mechanics simultaneously finds the static displacement/stress
    //     equilibrium under the 19.5 MPa top load.
    //   - Therefore solInit is a complete, mutually consistent initial solution.
    //
    // The saved MPH will contain solInit.  After opening the MPH, the user can
    // change ONLY Pneg and directly compute stdGas; no manual stationary solve
    // is required for each pressure.
    // ------------------------------------------------------------------
    model.study().create("stdInit");
    model.study("stdInit").create("stat", "Stationary");
    model.study("stdInit").feature("stat").set(
        "activate", new String[]{"solid", "on", "gp", "on", "gz", "on", "gm", "on"});

    model.sol().create("solInit");
    model.sol("solInit").study("stdInit");
    model.sol("solInit").attach("stdInit");
    model.sol("solInit").create("st1", "StudyStep");
    model.sol("solInit").feature("st1").set("study", "stdInit");
    model.sol("solInit").feature("st1").set("studystep", "stat");
    model.sol("solInit").create("v1", "Variables");

    // Stationary studies do not normally advance time.  Force expressions
    // containing t (especially ramp_bc) to use the physical initial time t=0.
    try {
      model.sol("solInit").feature("v1").set("cname", new String[]{"t"});
      model.sol("solInit").feature("v1").set("clist", new String[]{"0"});
    } catch (Exception ex) {
      System.out.println("Could not set t=0 as a solver constant for solInit. "
          + "If needed, set t=0 under solInit > Dependent Variables > Constants.");
    }

    model.sol("solInit").create("s1", "Stationary");
    model.sol("solInit").feature("s1").create("d1", "Direct");
    model.sol("solInit").feature("s1").feature("d1").set("linsolver", "pardiso");
    model.sol("solInit").feature("s1").feature("d1").set("pivotperturb", 1.0e-8);
    try {
      model.sol("solInit").feature("s1").feature("fcDef").set("linsolver", "d1");
      model.sol("solInit").feature("s1").feature("fcDef").set("dtech", "const");
      model.sol("solInit").feature("s1").feature("fcDef").set("damp", 0.70);
      model.sol("solInit").feature("s1").feature("fcDef").set("maxiter", 30);
    } catch (Exception ignored) {
    }
    model.sol("solInit").feature("s1").feature("aDef").set("cachepattern", false);

    // ------------------------------------------------------------------
    // Study 2: 0-120 d gas transient
    //
    // Solid Mechanics is intentionally OFF here, matching the original model's
    // actual mathematics: epsv=0, phif=phi_f0, phip=phi_p0, kf=kf0, so the gas
    // equations do not yet use the solid displacement field.  The stationary
    // solid result remains available in solInit for stress/displacement results.
    //
    // Crucially, the gas transient explicitly takes q,zch4,qp initial values
    // from solInit.  This removes the need for manual initial-value selection.
    // ------------------------------------------------------------------
    model.study().create("stdGas");
    model.study("stdGas").create("time", "Transient");
    model.study("stdGas").feature("time").set(
        "activate", new String[]{"solid", "off", "gp", "on", "gz", "on", "gm", "on"});
    model.study("stdGas").feature("time").set("tunit", "d");
    model.study("stdGas").feature("time").set("tlist", gasTimes);

    model.sol().create("solGas");
    model.sol("solGas").study("stdGas");
    model.sol("solGas").attach("stdGas");
    model.sol("solGas").create("st1", "StudyStep");
    model.sol("solGas").feature("st1").set("study", "stdGas");
    model.sol("solGas").feature("st1").set("studystep", "time");
    model.sol("solGas").create("v1", "Variables");

    // Explicitly inherit the complete t=0 stationary solution.
    try {
      model.sol("solGas").feature("v1").set("useinitsol", "on");
      model.sol("solGas").feature("v1").set("initmethod", "sol");
      model.sol("solGas").feature("v1").set("initsol", "solInit");
      model.sol("solGas").feature("v1").set("solnum", "last");
      model.sol("solGas").feature("v1").set("scalemethod", "init");
    } catch (Exception ex) {
      System.out.println("Could not attach solInit automatically. "
          + "In COMSOL set solGas > Dependent Variables > Initial values = solInit.");
    }

    model.sol("solGas").create("t1", "Time");
    model.sol("solGas").feature("t1").set("control", "user");
    model.sol("solGas").feature("t1").set("tunit", "d");
    model.sol("solGas").feature("t1").set("tlist", gasTimes);

    // Robust long-time settings.  The initial state is already consistent,
    // so disable COMSOL's extra artificial consistent-initialization step.
    setTimeControls(model, "solGas", "0.25[d]", "30[s]", 1, 5.0e-3);
    try {
      model.sol("solGas").feature("t1").set("consistent", "off");
    } catch (Exception ignored) {
    }
    addGasFullyCoupledSolver(model, "solGas");

    // ------------------------------------------------------------------
    // Results
    // ------------------------------------------------------------------
    try {
      model.result().dataset().create("dsetGas", "Solution");
      model.result().dataset("dsetGas").set("solution", "solGas");

      model.result().dataset().create("dsetInit", "Solution");
      model.result().dataset("dsetInit").set("solution", "solInit");

      model.result().create("pgCH4", "PlotGroup3D");
      model.result("pgCH4").label("Methane concentration, 0-120 d");
      model.result("pgCH4").set("data", "dsetGas");
      model.result("pgCH4").create("slc1", "Slice");
      model.result("pgCH4").feature("slc1").set("expr", "Cch4_pct");
      model.result("pgCH4").feature("slc1").set("descr", "Methane concentration");

      model.result().create("pgP", "PlotGroup3D");
      model.result("pgP").label("Fracture total pressure, 0-120 d");
      model.result("pgP").set("data", "dsetGas");
      model.result("pgP").create("slc1", "Slice");
      model.result("pgP").feature("slc1").set("expr", "pf/1e6");
      model.result("pgP").feature("slc1").set("descr", "Fracture total pressure");

      model.result().create("pgSolid", "PlotGroup3D");
      model.result("pgSolid").label("Stationary solid von Mises stress");
      model.result("pgSolid").set("data", "dsetInit");
      model.result("pgSolid").create("slc1", "Slice");
      model.result("pgSolid").feature("slc1").set("expr", "solid.mises/1e6");
      model.result("pgSolid").feature("slc1").set("descr", "von Mises stress (MPa)");
    } catch (Exception ex) {
      System.out.println("Result plot creation was skipped. "
          + "Use Cch4_pct with solGas and solid.mises/1e6 with solInit.");
    }

    return model;
  }

  public static void main(String[] args) {
    Model model = run();

    // Only compute the stationary initialization.
    // The initialized model will be saved by comsolbatch -outputfile.
    model.sol("solInit").runAll();

    System.out.println("solInit finished successfully.");
    System.out.println("Use comsolbatch -outputfile to save the initialized MPH.");
  }
}
