{
  description = "Pomodoro timer";
  inputs = {
    pyproject-nix = {
      url = "github:nix-community/pyproject.nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };
  outputs =
    {
      nixpkgs,
      pyproject-nix,
      ...
    }:
    let
      project = pyproject-nix.lib.project.loadPyproject {
        projectRoot = ./.;
      };
      pkgs = nixpkgs.legacyPackages.x86_64-linux;
      python = pkgs.python3;
    in
    {
      devShells.x86_64-linux.default =
        let
          arg = project.renderers.mkPythonEditablePackage { inherit python; };
          myPython = python.override {
            packageOverrides = final: prev: {
              pymodoro = final.mkPythonEditablePackage arg;
            };
          };
          pythonEnv = myPython.withPackages (ps: [ ps.pymodoro ]);
        in
        pkgs.mkShell { packages = [ pythonEnv ]; };
      packages.x86_64-linux.default =
        let
          attrs = project.renderers.buildPythonPackage { inherit python; };
        in
        python.pkgs.buildPythonPackage attrs;
    };
}
