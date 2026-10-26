# Stage 1: SemiBlock Junior concept

Start with **[SemiBlock-Junior-Design.md](SemiBlock-Junior-Design.md)**. It sets out the whole design in one file: the TwistLock lock system, every part, every sensor, the electronics, how it beats LEGO Technic, and the stage-2 plan.

| Open | What you get |
|---|---|
| [`viewer/index.html`](viewer/index.html) | Interactive 3D. Rotate every part and assembly, lock/unlock the TwistLocks, explode the rover, cut sections. Double-click to open in Chrome, Edge or Safari; it works offline. |
| [`renders/`](renders/) | Hero renders and labelled diagrams. `renders/parts/` has a picture of every part; `renders/sheets/` has contact sheets per family. |
| [`drawings/`](drawings/) | 2D manufacturing drawings for the factory: one PDF per part (EN / 简体中文, A3, first-angle), the combined drawing pack and an RFQ parts list (CSV). |
| [`cad/fcstd/`](cad/fcstd/) | FreeCAD files, one per part: coloured 3D bodies, part data and the drawing sheets as TechDraw pages. |
| [`cad/step/`](cad/step/) | STEP files for suppliers and CAD tools (Fusion 360, SolidWorks, Onshape), in mm. |
| [`cad/stl/`](cad/stl/) | STL files for 3D-printing prototypes (TwistLock pins: resin printer, tough resin). |
| [`cad/`](cad/) | Parametric source. Change a number in `params.py` and rebuild (see the end of the design doc). |
